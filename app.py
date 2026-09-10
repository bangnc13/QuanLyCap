import json
import os
import folium
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from folium.plugins import LocateControl
from geopy.distance import geodesic
from streamlit_folium import st_folium

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="Tối ưu đường di chuyển xe máy - Google Blue Style",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------
# 1. LOGO SIDEBAR
# -------------------------------------------------------------
logo_path = "FPT_Telecom_logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_container_width=True)

# -------------------------------------------------------------
# 2. CSS HIỆU ỨNG NÚT SIDEBAR & GIAO DIỆN
# -------------------------------------------------------------
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        padding: 0 !important;
        margin: 0 !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    
    [data-testid="stVerticalBlock"] {
        gap: 0rem !important;
    }
    
    header[data-testid="stHeader"] {
        height: 0px !important;
        background: transparent !important;
        z-index: 99999 !important;
    }

    @keyframes neonBlinkGlow {
        0% {
            background-color: #00ffcc !important;
            box-shadow: 0 0 10px #00ffcc, 0 0 20px #00ffcc !important;
            border: 2px solid #00ffcc !important;
            transform: scale(1);
        }
        50% {
            background-color: #00b386 !important;
            box-shadow: 0 0 25px #00ffcc, 0 0 45px #00ffcc, 0 0 65px #00ffcc !important;
            border: 2px solid #ffffff !important;
            transform: scale(1.15);
        }
        100% {
            background-color: #00ffcc !important;
            box-shadow: 0 0 10px #00ffcc, 0 0 20px #00ffcc !important;
            border: 2px solid #00ffcc !important;
            transform: scale(1);
        }
    }

    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapsedControl"] button,
    button[aria-label="Open sidebar"],
    section[data-testid="stSidebar"] + button,
    div[class*="collapsedControl"] {
        position: fixed !important;
        top: 14px !important;
        left: 14px !important;
        z-index: 99999999 !important;
        background-color: #00ffcc !important;
        border-radius: 50% !important;
        width: 44px !important;
        height: 44px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        animation: neonBlinkGlow 1.2s infinite ease-in-out !important;
    }

    div[data-testid="stSidebarCollapseButton"] button,
    button[aria-label="Close sidebar"] {
        background-color: #00ffcc !important;
        border-radius: 50% !important;
        width: 44px !important;
        height: 44px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        animation: neonBlinkGlow 1.2s infinite ease-in-out !important;
    }

    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapsedControl"] svg,
    button[aria-label="Open sidebar"] svg,
    button[aria-label="Close sidebar"] svg {
        fill: #000000 !important;
        color: #000000 !important;
        stroke: #000000 !important;
        width: 22px !important;
        height: 22px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------
# 3. GPS REALTIME
# -------------------------------------------------------------
gps_code = """
<script>
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            window.parent.postMessage({
                type: "streamlit:setComponentValue",
                value: {lat: lat, lon: lon}
            }, "*");
        },
        (error) => { console.error("Lỗi GPS:", error); },
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
# 4. LOAD GEOJSON
# -------------------------------------------------------------
@st.cache_data
def load_geojson(file_path):
    if not os.path.exists(file_path):
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    points = {}
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})

        if geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                possible_names = [
                    str(val).strip()
                    for val in props.values()
                    if isinstance(val, (str, int))
                ]
                for p_name in possible_names:
                    if p_name and "TQGP0" in p_name.upper():
                        points[p_name] = {"lat": coords[1], "lon": coords[0]}
    return points


GEOJSON_FILE = "data.geojson"
all_points = load_geojson(GEOJSON_FILE)
unique_keys = sorted(list(all_points.keys()))

# -------------------------------------------------------------
# 5. TÌM KIẾM ĐÍCH ĐẾN
# -------------------------------------------------------------
st.sidebar.header(" Make by BangNC13")
search_query = st.sidebar.text_input(
    "Nhập điểm cuối hành trình (nếu muốn)",
    placeholder="Ví dụ: Bệnh viện đa khoa, Chợ Tam Cờ...",
)

end_location = None
if search_query:
    headers = {"User-Agent": "Streamlit_TuyenQuang_Route_App"}
    full_query = f"{search_query}, Tuyên Quang, Việt Nam"
    tuyen_quang_box = "104.80,22.70,105.70,21.50"
    url = f"https://nominatim.openstreetmap.org/search?q={full_query}&format=json&limit=5&viewbox={tuyen_quang_box}&bounded=1"

    try:
        response = requests.get(url, headers=headers, timeout=5)
        results = response.json()

        if not results:
            url_fallback = f"https://nominatim.openstreetmap.org/search?q={search_query}+Tuyên+Quang&format=json&limit=5&countrycodes=vn"
            response = requests.get(url_fallback, headers=headers, timeout=5)
            results = response.json()

        if results:
            options = {
                f"{item['display_name'][:50]}...": (
                    float(item["lat"]),
                    float(item["lon"]),
                    item["display_name"],
                )
                for item in results
            }
            selected_option = st.sidebar.selectbox(
                "Chọn địa điểm chính xác:", list(options.keys())
            )
            lat, lon, full_name = options[selected_option]
            end_location = {
                "name": f"ĐÍCH ĐẾN: {search_query}",
                "lat": lat,
                "lon": lon,
            }
            st.sidebar.success(f"📍 Đã chọn đích: {search_query}")
        else:
            st.sidebar.error("Không tìm thấy địa điểm này ở Tuyên Quang!")
    except Exception as e:
        st.sidebar.error(f"Lỗi tìm kiếm: {e}")

# -------------------------------------------------------------
# 6. DANH SÁCH TẬP ĐIỂM
# -------------------------------------------------------------
st.sidebar.header("📋 Chọn lộ trình di chuyển")
selected_from_list = st.sidebar.multiselect(
    "Chọn điểm TQGP0xx:", options=unique_keys
)

uploaded_file = st.sidebar.file_uploader(
    "Hoặc Upload file Excel:", type=["xlsx", "xls"]
)
excel_points = []

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, header=None)
        raw_values = df.astype(str).values.flatten()

        for val in raw_values:
            val_clean = val.strip()
            if not val_clean or val_clean == "nan":
                continue

            if "TQGP0" in val_clean.upper():
                if val_clean in all_points:
                    excel_points.append(val_clean)
                else:
                    alt_val = val_clean.replace("/HO", "/HƠ").replace(
                        "/HƠ", "/HO"
                    )
                    if alt_val in all_points:
                        excel_points.append(alt_val)
                    else:
                        prefix_match = val_clean.split("/")[0]
                        if prefix_match in all_points:
                            excel_points.append(prefix_match)

        st.sidebar.info(f"Tìm thấy {len(excel_points)} điểm TQGP0xx từ Excel.")
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc file Excel: {e}")

final_selected_names = list(set(selected_from_list + excel_points))

# -------------------------------------------------------------
# 7. KHU VỰC TÙY CHỈNH HIỂN THỊ
# -------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Tùy chỉnh hiển thị BẢN ĐỒ")
show_labels = st.sidebar.checkbox("🏷️ Hiện tên điểm (Label)", value=True)
show_route_line = st.sidebar.checkbox("🛣️ Hiện đường vẽ lộ trình", value=True)

if st.sidebar.button("🔄 Làm mới bản đồ / Xóa lộ trình"):
    st.session_state.calculated_route = None
    st.rerun()

# -------------------------------------------------------------
# 8. THUẬT TOÁN ĐỊNH TUYẾN CHÍNH XÁC VÀO TÂM MARKER (MÀU XANH DƯƠNG)
# -------------------------------------------------------------
def get_accurate_blue_route(coords_list):
    """
    Tạo chuỗi đường đi mượt mà nối thẳng vào tâm Marker bằng màu Xanh Dương Google Maps.
    """
    complete_line = []
    total_dist = 0.0

    for i in range(len(coords_list) - 1):
        p1 = coords_list[i]
        p2 = coords_list[i + 1]

        # Gọi OSRM Foot/Bike để mở rộng lối đi nhỏ dẫn thẳng tới Marker
        url = f"http://router.project-osrm.org/route/v1/foot/{p1[1]},{p1[0]};{p2[1]},{p2[0]}?overview=full&geometries=geojson"

        segment = []
        try:
            res = requests.get(url, timeout=4)
            data = res.json()
            if data.get("code") == "Ok":
                geom = data["routes"][0]["geometry"]["coordinates"]
                segment = [[lat, lon] for lon, lat in geom]
                total_dist += data["routes"][0]["distance"] / 1000.0
        except Exception:
            pass

        if not segment:
            segment = [[p1[0], p1[1]], [p2[0], p2[1]]]
            total_dist += geodesic(p1, p2).km

        # Ép tâm tọa độ Marker vào đầu và cuối mỗi segment
        segment[0] = [p1[0], p1[1]]
        segment[-1] = [p2[0], p2[1]]

        if not complete_line:
            complete_line.extend(segment)
        else:
            complete_line.extend(segment[1:])

    return complete_line, total_dist


def solve_tsp_from_gps(gps_coords, intermediate_points, end_point=None):
    unvisited = intermediate_points.copy()
    current_pos = gps_coords
    route = []

    while unvisited:
        nearest = min(
            unvisited,
            key=lambda p: geodesic(current_pos, (p["lat"], p["lon"])).km,
        )
        route.append(nearest)
        current_pos = (nearest["lat"], nearest["lon"])
        unvisited.remove(nearest)

    if end_point:
        route.append(end_point)

    return route

# -------------------------------------------------------------
# 9. TÍNH TOÁN LỘ TRÌNH
# -------------------------------------------------------------
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None

if st.sidebar.button("🚀 Lộ trình "):
    if not final_selected_names and not end_location:
        st.sidebar.warning(
            "Vui lòng chọn điểm TQGP0xx hoặc nhập Điểm Kết Thúc!"
        )
    else:
        with st.spinner("Đang tối ưu lộ trình xe máy (Màu xanh dương)..."):
            gps_start_coords = (curr_lat, curr_lon)

            intermediate_points = [
                {
                    "name": name,
                    "lat": all_points[name]["lat"],
                    "lon": all_points[name]["lon"],
                }
                for name in final_selected_names
            ]

            st.session_state.calculated_route = solve_tsp_from_gps(
                gps_start_coords, intermediate_points, end_location
            )
            st.session_state.start_coords = gps_start_coords

# -------------------------------------------------------------
# 10. DỰNG BẢN ĐỒ GOOGLE MAPS
# -------------------------------------------------------------
def build_map(location, zoom=14):
    m = folium.Map(
        location=location,
        zoom_start=zoom,
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google Maps",
        zoom_control=True,
    )

    LocateControl(
        auto_start=False,
        flyTo=True,
        keepCurrentZoomLevel=True,
        strings={"title": "Định vị vị trí của tôi"},
    ).add_to(m)

    custom_script = """
    <style>
    .leaflet-top.leaflet-left { top: 75px !important; }
    .leaflet-control-locate a {
        background-color: #00ffcc !important;
        border: 2px solid #00ffcc !important;
        border-radius: 50% !important;
        width: 44px !important;
        height: 44px !important;
        box-shadow: 0 0 12px #00ffcc, 0 0 20px rgba(0, 255, 204, 0.7) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-decoration: none !important;
    }
    .leaflet-control-locate a span { display: none !important; }
    .leaflet-control-locate a::after {
        content: "" !important;
        width: 22px !important;
        height: 22px !important;
        background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="black"><path d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3c-.46-4.17-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z"/></svg>') !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: contain !important;
    }
    </style>
    <script>
    setInterval(function() {
        try {
            var parentDoc = window.parent.document;
            var openBtn = parentDoc.querySelector('[data-testid="collapsedControl"]') || 
                          parentDoc.querySelector('[data-testid="stSidebarCollapsedControl"]') ||
                          parentDoc.querySelector('button[aria-label="Open sidebar"]');
            if (openBtn) {
                openBtn.style.setProperty('animation', 'neonBlinkGlow 1.2s infinite ease-in-out', 'important');
                openBtn.style.setProperty('background-color', '#00ffcc', 'important');
                openBtn.style.setProperty('border-radius', '50%', 'important');
                openBtn.style.setProperty('border', '2px solid #00ffcc', 'important');
            }
        } catch(e) {}
    }, 500);
    </script>
    """
    m.get_root().html.add_child(folium.Element(custom_script))
    return m


if st.session_state.calculated_route is not None:
    optimized_route = st.session_state.calculated_route
    s_lat, s_lon = st.session_state.start_coords

    stopping_coords = [(s_lat, s_lon)] + [
        (p["lat"], p["lon"]) for p in optimized_route
    ]

    blue_path, real_distance = get_accurate_blue_route(stopping_coords)

    st.sidebar.success(
        f"📊 Tổng quãng đường xe máy: **~ {real_distance:.2f} km**"
    )

    m = build_map([s_lat, s_lon], zoom=14)

    # Đặt Marker Xuất phát
    folium.Marker(
        [s_lat, s_lon],
        popup="Vị trí GPS của bạn (Xuất phát)",
        icon=folium.Icon(color="green", icon="user", prefix="fa"),
    ).add_to(m)

    # Đặt các Marker điểm dừng
    for idx, point in enumerate(optimized_route, start=1):
        p_lat, p_lon = point["lat"], point["lon"]
        is_end = idx == len(optimized_route) and end_location is not None
        bg_color = "#e63946" if is_end else "#1A73E8"

        if show_labels:
            marker_html = f"""
            <div style="display: flex; align-items: center; white-space: nowrap;">
                <div style="font-size: 10pt; font-weight: bold; color: white; background-color: {bg_color}; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 24px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">{idx}</div>
                <span style="margin-left: 6px; background-color: white; color: #333; font-weight: bold; font-size: 11px; padding: 2px 6px; border-radius: 4px; border: 1px solid #ccc; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">{point['name']}</span>
            </div>
            """
        else:
            marker_html = f"""
            <div style="font-size: 10pt; font-weight: bold; color: white; background-color: {bg_color}; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 24px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">{idx}</div>
            """

        folium.Marker(
            [p_lat, p_lon],
            popup=f"Điểm dừng {idx}: {point['name']}",
            tooltip=f"{idx}. {point['name']}",
            icon=folium.DivIcon(html=marker_html),
        ).add_to(m)

    # VẼ TUYẾN ĐƯỜNG MÀU XANH DƯƠNG CHÍNH XÁC CỦA GOOGLE MAPS (#1A73E8)
    if show_route_line:
        folium.PolyLine(
            blue_path, color="#1A73E8", weight=6, opacity=0.9
        ).add_to(m)

    m.fit_bounds(stopping_coords)
    st_folium(m, use_container_width=True, height=1000, key="map_route_active")
else:
    m_default = build_map([curr_lat, curr_lon], zoom=14)

    folium.Marker(
        [curr_lat, curr_lon],
        popup="Vị trí hiện tại của bạn",
        icon=folium.Icon(color="green", icon="user", prefix="fa"),
    ).add_to(m_default)

    st_folium(
        m_default,
        use_container_width=True,
        height=1000,
        key="map_default_active",
    )
