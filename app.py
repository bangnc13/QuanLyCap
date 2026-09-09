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

# Thiết lập cấu hình trang tràn viền
st.set_page_config(
    page_title="Tối ưu đường di chuyển xe máy",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------
# 1. BỔ SUNG LOGO VÀO ĐẦU SIDEBAR (TRÊN CÙNG MENU)
# -------------------------------------------------------------
logo_path = "FPT_Telecom_logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_container_width=True)

# -------------------------------------------------------------
# 2. CSS ÉP BẢN ĐỒ TRÀN MÀN HÌNH & HIỆU ỨNG BLINK CHO CẢ 2 TRẠNG THÁI (ĐÓNG/MỞ)
# -------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Xóa sạch padding, margin thừa của Streamlit */
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        padding: 0 !important;
        margin: 0 !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    
    /* Mở rộng container chứa bản đồ full 100% chiều cao */
    [data-testid="stVerticalBlock"] {
        gap: 0rem !important;
    }
    
    /* Hide Header mặc định của Streamlit */
    header[data-testid="stHeader"] {
        height: 0px !important;
        background: transparent !important;
        z-index: 99999 !important;
    }

    /* KEYFRAMES TẠO HIỆU ỨNG BLINK PHÁT SÁNG NEON */
    @keyframes blinkGlow {
        0% {
            background-color: #00ffcc !important;
            box-shadow: 0 0 8px #00ffcc, 0 0 15px #00ffcc !important;
            border-color: #00ffcc !important;
            transform: scale(1);
        }
        50% {
            background-color: #00e6b8 !important;
            box-shadow: 0 0 25px #00ffcc, 0 0 40px #00ffcc, 0 0 60px #00ffcc !important;
            border-color: #ffffff !important;
            transform: scale(1.1);
        }
        100% {
            background-color: #00ffcc !important;
            box-shadow: 0 0 8px #00ffcc, 0 0 15px #00ffcc !important;
            border-color: #00ffcc !important;
            transform: scale(1);
        }
    }

    /* 1. HIỆU ỨNG CHO NÚT KHI MENU ĐANG ĐÓNG (NÚT >> TRÊN BẢN ĐỒ) */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapsedControl"] button,
    div[data-testid="collapsedControl"] {
        position: fixed !important;
        top: 15px !important;
        left: 15px !important;
        z-index: 9999999 !important;
        background-color: #00ffcc !important;
        border: 2px solid #00ffcc !important;
        border-radius: 50% !important;
        width: 46px !important;
        height: 46px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        animation: blinkGlow 1.2s infinite ease-in-out !important;
    }

    /* 2. HIỆU ỨNG CHO NÚT KHI MENU ĐANG MỞ (NÚT << TRONG SIDEBAR) */
    div[data-testid="stSidebarCollapseButton"] button,
    button[aria-label="Close sidebar"],
    button[aria-label="Open sidebar"] {
        background-color: #00ffcc !important;
        border: 2px solid #00ffcc !important;
        border-radius: 50% !important;
        width: 46px !important;
        height: 46px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        animation: blinkGlow 1.2s infinite ease-in-out !important;
    }

    /* BẮT BÚOC ICON BÊN TRONG NÚT LÀ MÀU ĐEN VÀ CÓ KÍCH THƯỚC CHUẨN */
    [data-testid="stSidebarCollapsedControl"] svg,
    div[data-testid="stSidebarCollapseButton"] svg,
    button[aria-label="Close sidebar"] svg,
    button[aria-label="Open sidebar"] svg {
        fill: #000000 !important;
        color: #000000 !important;
        stroke: #000000 !important;
        width: 24px !important;
        height: 24px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------
# 3. BỘ LẤY TỌA ĐỘ GPS REALTIME TỪ ĐIỆN THOẠI (CHẠY NGẦM)
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
# 4. ĐỌC GEOJSON LỌC TQGP0xx
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
# 5. TÌM KIẾM ĐÍCH ĐẾN (TUYÊN QUANG)
# -------------------------------------------------------------
st.sidebar.header(" Make by BangNC13")
search_query = st.sidebar.text_input(
    "Nhập điểm cuối hành trình",
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
# 6. DANH SÁCH ĐIỂM CẦN GHÉ QUA (TQGP0xx)
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
# 7. THUẬT TOÁN OSRM VÀ ĐIỀU HƯỚNG
# -------------------------------------------------------------
def get_route_osrm(coords_list):
    formatted_coords = ";".join([f"{lon},{lat}" for lat, lon in coords_list])
    url = f"http://router.project-osrm.org/route/v1/bike/{formatted_coords}?overview=full&geometries=geojson"

    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("code") == "Ok":
            route_geometry = data["routes"][0]["geometry"]["coordinates"]
            path = [[lat, lon] for lon, lat in route_geometry]
            distance_km = data["routes"][0]["distance"] / 1000.0
            return path, distance_km
    except Exception:
        pass

    total_dist = 0
    for i in range(len(coords_list) - 1):
        total_dist += geodesic(coords_list[i], coords_list[i + 1]).km
    return [[lat, lon] for lat, lon in coords_list], total_dist


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
# 8. XỬ LÝ NÚT TÍNH TOÁN
# -------------------------------------------------------------
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None

if st.sidebar.button("🚀 Lộ trình "):
    if not final_selected_names and not end_location:
        st.sidebar.warning(
            "Vui lòng chọn điểm TQGP0xx hoặc nhập Điểm Kết Thúc!"
        )
    else:
        with st.spinner("Đang tính toán lộ trình xe máy..."):
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
# 9. HIỂN THỊ BẢN ĐỒ VIEW MAP
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

    custom_css = """
    <style>
    .leaflet-top.leaflet-left {
        top: 75px !important;
    }
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
    """
    m.get_root().html.add_child(folium.Element(custom_css))

    return m


if st.session_state.calculated_route is not None:
    optimized_route = st.session_state.calculated_route
    s_lat, s_lon = st.session_state.start_coords

    stopping_coords = [(s_lat, s_lon)] + [
        (p["lat"], p["lon"]) for p in optimized_route
    ]
    detailed_path, real_distance = get_route_osrm(stopping_coords)

    st.sidebar.markdown("---")
    st.sidebar.success(
        f"📊 **Lộ trình xuất phát từ GPS của bạn**\n\nTổng quãng đường xe máy: **~ {real_distance:.2f} km**"
    )

    m = build_map([s_lat, s_lon], zoom=14)

    folium.Marker(
        [s_lat, s_lon],
        popup="Vị trí GPS của bạn (Xuất phát)",
        icon=folium.Icon(color="green", icon="user", prefix="fa"),
    ).add_to(m)

    for idx, point in enumerate(optimized_route, start=1):
        p_lat, p_lon = point["lat"], point["lon"]
        is_end = idx == len(optimized_route) and end_location is not None
        bg_color = "#e63946" if is_end else "#0078ff"

        folium.Marker(
            [p_lat, p_lon],
            popup=f"Bước {idx}: {point['name']}",
            tooltip=f"{idx}. {point['name']}",
            icon=folium.DivIcon(
                html=f'<div style="font-size: 10pt; font-weight: bold; color: white; background-color: {bg_color}; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 24px;">{idx}</div>'
            ),
        ).add_to(m)

    folium.PolyLine(
        detailed_path, color="#e63946", weight=5, opacity=0.85
    ).add_to(m)

    m.fit_bounds(stopping_coords)
    st_folium(m, use_container_width=True, height=1000, returned_objects=[])
else:
    m_default = build_map([curr_lat, curr_lon], zoom=14)

    folium.Marker(
        [curr_lat, curr_lon],
        popup="Vị trí hiện tại của bạn",
        icon=folium.Icon(color="green", icon="user", prefix="fa"),
    ).add_to(m_default)

    st_folium(
        m_default, use_container_width=True, height=1000, returned_objects=[]
    )
