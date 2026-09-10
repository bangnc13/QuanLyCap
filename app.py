import json
import os
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import folium
from folium.plugins import LocateControl
from streamlit_folium import st_folium

# Cấu hình trang
st.set_page_config(
    page_title="Tối ưu đường di chuyển xe máy - Exact Target Snap",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------
# 1. LOGO & CSS
# -------------------------------------------------------------
logo_path = "FPT_Telecom_logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_container_width=True)

st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        padding: 0 !important; margin: 0 !important; height: 100vh !important; overflow: hidden !important;
    }
    [data-testid="stVerticalBlock"] { gap: 0rem !important; }
    header[data-testid="stHeader"] { height: 0px !important; background: transparent !important; z-index: 99999 !important; }
    @keyframes neonBlinkGlow {
        0% { background-color: #00ffcc !important; box-shadow: 0 0 10px #00ffcc; border: 2px solid #00ffcc; transform: scale(1); }
        50% { background-color: #00b386 !important; box-shadow: 0 0 25px #00ffcc, 0 0 45px #00ffcc; border: 2px solid #ffffff; transform: scale(1.15); }
        100% { background-color: #00ffcc !important; box-shadow: 0 0 10px #00ffcc; border: 2px solid #00ffcc; transform: scale(1); }
    }
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"], button[aria-label="Open sidebar"], button[aria-label="Close sidebar"] {
        position: fixed !important; top: 14px !important; left: 14px !important; z-index: 99999999 !important;
        background-color: #00ffcc !important; border-radius: 50% !important; width: 44px !important; height: 44px !important;
        display: flex !important; align-items: center !important; justify-content: center !important;
        animation: neonBlinkGlow 1.2s infinite ease-in-out !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------
# 2. GPS REALTIME
# -------------------------------------------------------------
gps_code = """
<script>
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            window.parent.postMessage({
                type: "streamlit:setComponentValue",
                value: {lat: pos.coords.latitude, lon: pos.coords.longitude}
            }, "*");
        },
        (err) => console.error(err),
        { enableHighAccuracy: true }
    );
}
</script>
"""
gps_data = components.html(gps_code, height=0)

if "user_gps" not in st.session_state:
    st.session_state.user_gps = {"lat": 21.82714, "lon": 105.19952}
if gps_data and isinstance(gps_data, dict) and "lat" in gps_data:
    st.session_state.user_gps = gps_data

curr_lat = st.session_state.user_gps["lat"]
curr_lon = st.session_state.user_gps["lon"]

# -------------------------------------------------------------
# 3. LOAD DATA (OPTIMIZED)
# -------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_geojson(file_path):
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    points = {}
    for feature in data.get("features", []):
        if feature.get("geometry", {}).get("type") == "Point":
            coords = feature["geometry"]["coordinates"]
            for val in feature.get("properties", {}).values():
                val_str = str(val).strip()
                if "TQGP0" in val_str.upper():
                    points[val_str] = {"lat": coords[1], "lon": coords[0]}
    return points

all_points = load_geojson("data.geojson")
unique_keys = sorted(list(all_points.keys()))

# -------------------------------------------------------------
# 4. SIDEBAR & INPUTS
# -------------------------------------------------------------
st.sidebar.header("Make by BangNC13")
search_query = st.sidebar.text_input("Nhập điểm cuối hành trình (nếu muốn)", placeholder="Chợ Tam Cờ...")
end_location = None

if search_query:
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={search_query}, Tuyên Quang, Việt Nam&format=json&limit=3"
        res = requests.get(url, headers={"User-Agent": "TQ_App"}, timeout=3).json()
        if res:
            end_location = {
                "name": f"ĐÍCH ĐẾN: {search_query}",
                "lat": float(res[0]["lat"]),
                "lon": float(res[0]["lon"])
            }
            st.sidebar.success(f"📍 Đã chọn đích: {search_query}")
    except Exception:
        pass

st.sidebar.header("📋 Chọn lộ trình di chuyển")
selected_from_list = st.sidebar.multiselect("Chọn điểm TQGP0xx:", options=unique_keys)
uploaded_file = st.sidebar.file_uploader("Hoặc Upload file Excel:", type=["xlsx", "xls"])

excel_points = []
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, header=None).astype(str)
        flat_series = df.values.flatten()
        matched = [val.strip() for val in flat_series if "TQGP0" in val.upper() and val.strip() in all_points]
        excel_points.extend(matched)
        st.sidebar.info(f"Tìm thấy {len(set(excel_points))} điểm từ Excel.")
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc file: {e}")

final_selected_names = list(set(selected_from_list + excel_points))

st.sidebar.markdown("---")
show_labels = st.sidebar.checkbox("🏷️ Hiện tên điểm", value=True)
show_route_line = st.sidebar.checkbox("🛣️ Hiện đường vẽ lộ trình", value=True)

if st.sidebar.button("🔄 Làm mới bản đồ"):
    st.session_state.calculated_route = None
    st.rerun()

# -------------------------------------------------------------
# 5. THUẬT TOÁN TỐI ƯU HÓA LỘ TRÌNH (OSRM MATRIX + 2-OPT)
# -------------------------------------------------------------
def get_distance_matrix(coords):
    """Lấy ma trận khoảng cách đường bộ bằng 1 request duy nhất."""
    loc_str = ";".join([f"{lon},{lat}" for lat, lon in coords])
    url = f"http://router.project-osrm.org/table/v1/driving/{loc_str}?annotations=distance"
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("code") == "Ok":
            return res["distances"]
    except Exception:
        pass
    return None

def two_opt(route, dist_matrix):
    """Thuật toán 2-Opt gỡ nút thắt, tối ưu chiều dài tuyến đường."""
    best = route
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best) - (0 if route[-1] != route[0] else 1)):
                if j - i == 1: continue
                # Tính khoảng cách cũ vs mới
                old_dist = dist_matrix[best[i-1]][best[i]] + dist_matrix[best[j]][best[j+1 if j+1 < len(best) else 0]]
                new_dist = dist_matrix[best[i-1]][best[j]] + dist_matrix[best[i]][best[j+1 if j+1 < len(best) else 0]]
                if new_dist < old_dist:
                    best[i:j+1] = reversed(best[i:j+1])
                    improved = True
    return best

def solve_tsp_advanced(start_coord, points, end_coord=None):
    all_coords = [start_coord] + [(p["lat"], p["lon"]) for p in points]
    if end_coord:
        all_coords.append((end_coord["lat"], end_coord["lon"]))

    dist_matrix = get_distance_matrix(all_coords)
    n = len(all_coords)
    
    if not dist_matrix: # Fallback sang Greedy nếu mất mạng
        unvisited = list(range(1, len(points) + 1))
        curr = 0
        path = [0]
        while unvisited:
            nxt = min(unvisited, key=lambda x: ((all_coords[curr][0]-all_coords[x][0])**2 + (all_coords[curr][1]-all_coords[x][1])**2))
            path.append(nxt)
            unvisited.remove(nxt)
            curr = nxt
        if end_coord: path.append(n - 1)
    else:
        # 1. Greedy khởi tạo
        unvisited = list(range(1, len(points) + 1))
        curr = 0
        path = [0]
        while unvisited:
            nxt = min(unvisited, key=lambda x: dist_matrix[curr][x])
            path.append(nxt)
            unvisited.remove(nxt)
            curr = nxt
        if end_coord: path.append(n - 1)
        
        # 2. Áp dụng 2-Opt tối ưu
        if len(path) > 3:
            path = two_opt(path, dist_matrix)

    ordered_points = []
    for idx in path[1:]:
        if end_coord and idx == n - 1:
            ordered_points.append(end_coord)
        else:
            ordered_points.append(points[idx - 1])
            
    return ordered_points

def get_route_geometry(coords_list):
    """Lấy geometry tổng lộ trình để giảm thời gian render."""
    road_lines, target_connectors = [], []
    total_dist = 0.0
    
    for i in range(len(coords_list) - 1):
        p1, p2 = coords_list[i], coords_list[i+1]
        url = f"http://router.project-osrm.org/route/v1/driving/{p1[1]},{p1[0]};{p2[1]},{p2[0]}?overview=simplified&geometries=geojson"
        try:
            res = requests.get(url, timeout=3).json()
            if res.get("code") == "Ok":
                route_data = res["routes"][0]
                geom = [[lat, lon] for lon, lat in route_data["geometry"]["coordinates"]]
                total_dist += route_data["distance"] / 1000.0
                road_lines.append(geom)
                target_connectors.append([[p1[0], p1[1]], geom[0]])
                target_connectors.append([geom[-1], [p2[0], p2[1]]])
                continue
        except Exception:
            pass
        road_lines.append([[p1[0], p1[1]], [p2[0], p2[1]]])
        
    return road_lines, target_connectors, total_dist

# -------------------------------------------------------------
# 6. THỰC THI TÍNH TOÁN & HIỂN THỊ
# -------------------------------------------------------------
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None

if st.sidebar.button("🚀 Lộ trình"):
    if not final_selected_names and not end_location:
        st.sidebar.warning("Vui lòng chọn điểm TQGP0xx hoặc nhập Điểm Kết Thúc!")
    else:
        with st.spinner("Đang tính toán tuyến đường tối ưu nhất..."):
            gps_start = (curr_lat, curr_lon)
            pts = [{"name": name, "lat": all_points[name]["lat"], "lon": all_points[name]["lon"]} for name in final_selected_names]
            
            st.session_state.calculated_route = solve_tsp_advanced(gps_start, pts, end_location)
            st.session_state.start_coords = gps_start

def build_map(center):
    m = folium.Map(location=center, zoom_start=14, tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", attr="Google Maps")
    LocateControl(auto_start=False, flyTo=True, strings={"title": "Vị trí của tôi"}).add_to(m)
    return m

if st.session_state.calculated_route:
    route = st.session_state.calculated_route
    s_lat, s_lon = st.session_state.start_coords
    stop_coords = [(s_lat, s_lon)] + [(p["lat"], p["lon"]) for p in route]

    road_lines, connectors, real_dist = get_route_geometry(stop_coords)
    st.sidebar.success(f"📊 Tổng quãng đường: **~ {real_dist:.2f} km**")

    m = build_map([s_lat, s_lon])
    folium.Marker([s_lat, s_lon], popup="Xuất phát", icon=folium.Icon(color="green", icon="user", prefix="fa")).add_to(m)

    for idx, pt in enumerate(route, start=1):
        is_end = idx == len(route) and end_location is not None
        bg_color = "#e63946" if is_end else "#1A73E8"
        label_html = f"<span style='margin-left: 6px; background: white; color: #333; font-weight: bold; font-size: 11px; padding: 2px 6px; border-radius: 4px; border: 1px solid #ccc;'>{pt['name']}</span>" if show_labels else ""
        
        marker_html = f"""
        <div style="display: flex; align-items: center; white-space: nowrap;">
            <div style="font-size: 10pt; font-weight: bold; color: white; background-color: {bg_color}; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 24px;">{idx}</div>
            {label_html}
        </div>
        """
        folium.Marker([pt["lat"], pt["lon"]], popup=f"{idx}. {pt['name']}", icon=folium.DivIcon(html=marker_html)).add_to(m)

    if show_route_line:
        for line in road_lines:
            folium.PolyLine(line, color="#1A73E8", weight=6, opacity=0.85).add_to(m)
        for conn in connectors:
            folium.PolyLine(conn, color="#1A73E8", weight=4, opacity=0.9).add_to(m)

    m.fit_bounds(stop_coords)
    st_folium(m, use_container_width=True, height=1000, key="optimized_map")
else:
    m_default = build_map([curr_lat, curr_lon])
    folium.Marker([curr_lat, curr_lon], popup="Vị trí hiện tại", icon=folium.Icon(color="green", icon="user", prefix="fa")).add_to(m_default)
    st_folium(m_default, use_container_width=True, height=1000, key="default_map")
