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

st.set_page_config(
    page_title="Tối ưu đường di chuyển xe máy", layout="wide"
)

# -------------------------------------------------------------
# CSS TÙY CHỈNH NÚT TOGGLE CÓ SẴN (BO TRÒN, MÀU XANH NEON)
# -------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Nút ẩn/mở Sidebar có sẵn của Streamlit - Bo tròn & Màu Xanh Neon */
    button[aria-label="Close sidebar"], 
    button[aria-label="Open sidebar"],
    [data-testid="collapsedControl"] {
        background-color: #00ffcc !important;
        color: #000000 !important;
        border-radius: 50% !important;
        border: 2px solid #00ffcc !important;
        box-shadow: 0 0 12px #00ffcc, 0 0 20px rgba(0, 255, 204, 0.6) !important;
        transition: all 0.3s ease-in-out !important;
        width: 42px !important;
        height: 42px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        z-index: 999999 !important;
    }

    button[aria-label="Close sidebar"]:hover, 
    button[aria-label="Open sidebar"]:hover,
    [data-testid="collapsedControl"]:hover {
        background-color: #00e6b8 !important;
        transform: scale(1.1) !important;
        box-shadow: 0 0 18px #00ffcc, 0 0 28px rgba(0, 255, 204, 0.9) !important;
    }

    /* Đảm bảo nút nổi rõ nét trên giao diện */
    [data-testid="collapsedControl"] svg {
        fill: #000000 !important;
        color: #000000 !important;
        stroke: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar Title
st.sidebar.title("🏍️ Tối ưu hóa quãng đường di chuyển (Xe máy)")

# -------------------------------------------------------------
# 1. BỘ LẤY TỌA ĐỘ GPS REALTIME TỪ ĐIỆN THOẠI/TRÌNH DUYỆT
# -------------------------------------------------------------
st.sidebar.header("📍 Điểm xuất phát (GPS Điện thoại)")

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
        (error) => {
            console.error("Lỗi GPS:", error);
        },
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

st.sidebar.success(
    f"📡 **Đã định vị GPS điện thoại:**\n\nLat: `{curr_lat:.5f}` | Lon: `{curr_lon:.5f}`"
)


# -------------------------------------------------------------
# 2. ĐỌC GEOJSON LỌC TQGP0xx
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
# 3. TÌM KIẾM ĐẮM ĐẾN (TUYÊN QUANG)
# -------------------------------------------------------------
st.sidebar.header("🔍 Tìm kiếm Đích đến (Tuyên Quang)")
search_query = st.sidebar.text_input(
    "Nhập địa điểm đích đến:",
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
# 4. DANH SÁCH ĐIỂM CẦN GHÉ QUA (TQGP0xx)
# -------------------------------------------------------------
st.sidebar.header("📋 Danh sách điểm ghé (TQGP0xx)")
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
# 5. THUẬT TOÁN ĐIỀU HƯỚNG OSRM VÀ SẮP XẾP LỘ TRÌNH
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
# 6. HÀM TẠO BẢN ĐỒ KÈM NÚT MENU TẮT/MỞ SIDEBAR TRÊN MAP
# -------------------------------------------------------------
def create_map_with_menu_button(location, zoom=14):
    m = folium.Map(
        location=location,
        zoom_start=zoom,
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google Maps",
    )

    # Nút định vị GPS Realtime
    LocateControl(
        auto_start=False,
        flyTo=True,
        keepCurrentZoomLevel=True,
        strings={"title": "Định vị vị trí của tôi"},
    ).add_to(m)

    # Nút Custom HTML/JS Menu Tắt/Mở Sidebar ngay trên Màn hình Map
    menu_button_html = """
    <div style="position: fixed; top: 80px; left: 12px; z-index: 9999;">
        <button onclick="toggleSidebar()" style="
            background-color: #00ffcc;
            color: #000000;
            border: 2px solid #00ffcc;
            border-radius: 50%;
            width: 44px;
            height: 44px;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 0 12px #00ffcc, 0 0 20px rgba(0,255,204,0.6);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s;
        " onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1.0)'" title="Tắt / Mở Thanh Menu">
            ☰
        </button>
    </div>
    <script>
    function toggleSidebar() {
        var sidebarCloseBtn = window.parent.document.querySelector('button[aria-label="Close sidebar"]');
        var sidebarOpenBtn = window.parent.document.querySelector('button[aria-label="Open sidebar"]');
        
        if (sidebarCloseBtn) {
            sidebarCloseBtn.click();
        } else if (sidebarOpenBtn) {
            sidebarOpenBtn.click();
        }
    }
    </script>
    """
    m.get_root().html.add_child(folium.Element(menu_button_html))
    return m


# -------------------------------------------------------------
# 7. XỬ LÝ SỰ KIỆN TÍNH TOÁN
# -------------------------------------------------------------
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None

if st.sidebar.button("🚀 Tối ưu đường đi XE MÁY"):
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
# 8. HIỂN THỊ BẢN ĐỒ VIEW MAP
# -------------------------------------------------------------
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

    m = create_map_with_menu_button([s_lat, s_lon], zoom=14)

    # Xuất phát GPS
    folium.Marker(
        [s_lat, s_lon],
        popup="Vị trí GPS của bạn (Xuất phát)",
        tooltip="📍 Xuất phát (GPS Vị trí của bạn)",
        icon=folium.Icon(color="green", icon="user", prefix="fa"),
    ).add_to(m)

    # Các điểm ghé & đích đến
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
    st_folium(m, use_container_width=True, height=850, returned_objects=[])
else:
    # Màn hình chờ mặc định
    m_default = create_map_with_menu_button([curr_lat, curr_lon], zoom=14)
    folium.Marker(
        [curr_lat, curr_lon],
        popup="Vị trí hiện tại của bạn",
        tooltip="📍 GPS Vị trí của bạn",
        icon=folium.Icon(color="green", icon="user", prefix="fa"),
    ).add_to(m_default)

    st_folium(
        m_default, use_container_width=True, height=850, returned_objects=[]
    )
