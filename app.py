import json
import os
import math
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import folium
from folium.plugins import LocateControl
from streamlit_folium import st_folium

# -------------------------------------------------------------
# CẤU HÌNH TRANG STREAMLIT
# -------------------------------------------------------------
st.set_page_config(
    page_title="Tối ưu đường di chuyển xe máy - Exact Target Snap",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------
# 1. LOGO & CSS HIỆU ỨNG
# -------------------------------------------------------------
logo_path = "FPT_Telecom_logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_container_width=True)

st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        padding: 0 !important; 
        margin: 0 !important; 
        height: 100vh !important; 
        overflow: hidden !important;
    }
    [data-testid="stVerticalBlock"] { gap: 0rem !important; }
    header[data-testid="stHeader"] { 
        height: 0px !important; 
        background: transparent !important; 
        z-index: 99999 !important; 
    }
    @keyframes neonBlinkGlow {
        0% { background-color: #00ffcc !important; box-shadow: 0 0 10px #00ffcc; border: 2px solid #00ffcc; transform: scale(1); }
        50% { background-color: #00b386 !important; box-shadow: 0 0 25px #00ffcc, 0 0 45px #00ffcc; border: 2px solid #ffffff; transform: scale(1.15); }
        100% { background-color: #00ffcc !important; box-shadow: 0 0 10px #00ffcc; border: 2px solid #00ffcc; transform: scale(1); }
    }
    [data-testid="collapsedControl"], 
    [data-testid="stSidebarCollapsedControl"], 
    button[aria-label="Open sidebar"], 
    button[aria-label="Close sidebar"] {
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
# 2. GPS REALTIME (CHỈ CHẠY 1 LẦN NẾU CHƯA CÓ)
# -------------------------------------------------------------
if "user_gps" not in st.session_state:
    st.session_state.user_gps = {"lat": 21.82714, "lon": 105.19952}
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
            (err) => console.error("Lỗi GPS:", err),
            { enableHighAccuracy: true }
        );
    }
    </script>
    """
    gps_data = components.html(gps_code, height=0)
    if gps_data and isinstance(gps_data, dict) and "lat" in gps_data:
        st.session_state.user_gps = gps_data

curr_lat = st.session_state.user_gps["lat"]
curr_lon = st.session_state.user_gps["lon"]

# -------------------------------------------------------------
# 3. LOAD DATA GEOJSON (OPTIMIZED CACHE)
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
# 4. SIDEBAR & ĐỊA ĐIỂM
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
        else:
            st.sidebar.error("Không tìm thấy địa điểm này ở Tuyên Quang!")
    except Exception as e:
        st.sidebar.error(f"Lỗi tìm kiếm: {e}")

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
        st.sidebar.error(f"Lỗi đọc file Excel: {e}")

final_selected_names = list(set(selected_from_list + excel_points))

st.sidebar.markdown("---")
show_labels = st.sidebar.checkbox("🏷️ Hiện tên điểm (Label)", value=True)
show_route_line = st.sidebar.checkbox("🛣️ Hiện đường vẽ lộ trình", value=True)

if st.sidebar.button("🔄 Làm mới bản đồ"):
    st.session_state.calculated_route = None
    st.session_state.route_cache = None
    st.rerun()

# -------------------------------------------------------------
# 5. THUẬT TOÁN TỐI ƯU & LOAD TỌA ĐỘ SIÊU TỐC
# -------------------------------------------------------------
def get_distance_matrix(coords):
    """Lấy Ma trận khoảng cách qua 1 Request OSRM."""
    loc_str = ";".join([f"{lon},{lat}" for lat, lon in coords])
    url = f"http://router.project-osrm.org/table/v1/driving/{loc_str}?annotations=distance"
    try:
        res = requests.get(url, timeout=4).json()
        if res.get("code") == "Ok":
            return res["distances"]
    except Exception:
        pass
    return None

def solve_tsp_google_style(start_coord, points, end_coord=None):
    """Chạy 2-Opt tối ưu thứ tự lộ trình."""
    all_coords = [start_coord] + [(p["lat"], p["lon"]) for p in points]
    if end_coord:
        all_coords.append((end_coord["lat"], end_coord["lon"]))

    n = len(all_coords)
    dist_matrix = get_distance_matrix(all_coords)

    if not dist_matrix:
        dist_matrix = [[0]*n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                dist_matrix[i][j] = math.hypot(all_coords[i][0] - all_coords[j][0], all_coords[i][1] - all_coords[j][1])

    unvisited = set(range(1, len(points) + 1))
    curr = 0
    path = [0]
    while unvisited:
        nxt = min(unvisited, key=lambda x: dist_matrix[curr][x])
        path.append(nxt)
        unvisited.remove(nxt)
        curr = nxt

    if end_coord:
        path.append(n - 1)

    def get_total_distance(p_route):
        return sum(dist_matrix[p_route[k]][p_route[k+1]] for k in range(len(p_route) - 1))

    improved = True
    best_path = path
    best_dist = get_total_distance(best_path)

    while improved:
        improved = False
        for i in range(1, len(best_path) - 2):
            for j in range(i + 1, len(best_path) - (0 if end_coord else 1)):
                if j - i == 1:
                    continue
                new_path = best_path[:i] + best_path[i:j+1][::-1] + best_path[j+1:]
                new_dist = get_total_distance(new_path)
                if new_dist < best_dist:
                    best_dist = new_dist
                    best_path = new_path
                    improved = True
                    break
            if improved:
                break

    ordered_points = []
    for idx in best_path[1:]:
        if end_coord and idx == n - 1:
            ordered_points.append(end_coord)
        else:
            ordered_points.append(points[idx - 1])

    return ordered_points

def get_single_batch_route(coords_list):
    """
    TỐI ƯU SIÊU TỐC:
    Gộp toàn bộ các điểm cần đi vào BATCH ROUTE API duy nhất của OSRM.
    Chỉ thực hiện 1 HTTP Request thay vì N HTTP Requests.
    """
    loc_str = ";".join([f"{lon},{lat}" for lat, lon in coords_list])
    url = f"http://router.project-osrm.org/route/v1/driving/{loc_str}?overview=simplified&geometries=geojson"
    
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("code") == "Ok":
            route_data = res["routes"][0]
            geom = [[lat, lon] for lon, lat in route_data["geometry"]["coordinates"]]
            total_dist = route_data["distance"] / 1000.0
            return [geom], total_dist
    except Exception:
        pass

    # Dự phòng nếu mạng yếu
    road_line = [[lat, lon] for lat, lon in coords_list]
    return [road_line], 0.0

# -------------------------------------------------------------
# 6. TÍNH TOÁN & DỰNG BẢN ĐỒ
# -------------------------------------------------------------
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None
if "route_cache" not in st.session_state:
    st.session_state.route_cache = None

if st.sidebar.button("🚀 Lộ trình"):
    if not final_selected_names and not end_location:
        st.sidebar.warning("Vui lòng chọn điểm TQGP0xx hoặc nhập Điểm Kết Thúc!")
    else:
        with st.spinner("Tối ưu & Tải lộ trình siêu tốc..."):
            gps_start = (curr_lat, curr_lon)
            pts = [{"name": name, "lat": all_points[name]["lat"], "lon": all_points[name]["lon"]} for name in final_selected_names]
            
            # Tính lộ trình
            opt_route = solve_tsp_google_style(gps_start, pts, end_location)
            stop_coords = [gps_start] + [(p["lat"], p["lon"]) for p in opt_route]
            
            # Tải đường vẽ dạng Batch 1 lần
            road_lines, real_dist = get_single_batch_route(stop_coords)
            
            # Cất vào Session State
            st.session_state.calculated_route = opt_route
            st.session_state.start_coords = gps_start
            st.session_state.route_cache = {
                "road_lines": road_lines,
                "real_dist": real_dist,
                "stop_coords": stop_coords
            }

def build_map(center):
    m = folium.Map(
        location=center, 
        zoom_start=14, 
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", 
        attr="Google Maps"
    )
    LocateControl(auto_start=False, flyTo=True, strings={"title": "Vị trí của tôi"}).add_to(m)
    return m

if st.session_state.calculated_route and st.session_state.route_cache:
    route = st.session_state.calculated_route
    s_lat, s_lon = st.session_state.start_coords
    
    cache = st.session_state.route_cache
    road_lines = cache["road_lines"]
    real_dist = cache["real_dist"]
    stop_coords = cache["stop_coords"]

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
            folium.PolyLine(line, color="#1A73E8", weight=5, opacity=0.8).add_to(m)

    m.fit_bounds(stop_coords)
    st_folium(m, use_container_width=True, height=1000, key="optimized_map")
else:
    m_default = build_map([curr_lat, curr_lon])
    folium.Marker([curr_lat, curr_lon], popup="Vị trí hiện tại", icon=folium.Icon(color="green", icon="user", prefix="fa")).add_to(m_default)
    st_folium(m_default, use_container_width=True, height=1000, key="default_map")
