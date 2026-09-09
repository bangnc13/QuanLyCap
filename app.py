import json
import os
import folium
import pandas as pd
import requests
import streamlit as st
from folium.plugins import LocateControl
from geopy.distance import geodesic
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Tối ưu đường di chuyển xe máy", layout="wide"
)

# Sidebar Title
st.sidebar.title("🏍️ Tối ưu hóa quãng đường di chuyển (Xe máy)")


# 1. Đọc file GeoJSON & lọc điểm TQGP0xx
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

# 2. Tìm kiếm Địa điểm (Giới hạn mặc định thuộc tỉnh Tuyên Quang)
st.sidebar.header("🔍 Tìm kiếm Đích đến (Tuyên Quang)")
search_query = st.sidebar.text_input(
    "Nhập tên địa điểm tại Tuyên Quang:",
    placeholder="Ví dụ: Bệnh viện đa khoa, Chợ Tam Cờ...",
)

end_location = None
if search_query:
    headers = {"User-Agent": "Streamlit_TuyenQuang_Route_App"}
    # Tự động gắn kèm 'Tuyên Quang' vào từ khóa & dùng viewbox giới hạn tọa độ Tuyên Quang
    full_query = f"{search_query}, Tuyên Quang, Việt Nam"

    # Tọa độ khung viền giới hạn tỉnh Tuyên Quang (lon_min, lat_max, lon_max, lat_min)
    tuyen_quang_box = "104.80,22.70,105.70,21.50"
    url = f"https://nominatim.openstreetmap.org/search?q={full_query}&format=json&limit=5&viewbox={tuyen_quang_box}&bounded=1"

    try:
        response = requests.get(url, headers=headers, timeout=5)
        results = response.json()

        # Nếu không tìm thấy kết quả giới hạn, thử tìm rộng hơn với từ khóa + Tuyên Quang
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
            st.sidebar.success(f"📍 Đã chọn đích tại TQ: {search_query}")
        else:
            st.sidebar.error("Không tìm thấy địa điểm này ở Tuyên Quang!")
    except Exception as e:
        st.sidebar.error(f"Lỗi tìm kiếm: {e}")

# 3. Chọn Danh sách tập điểm cần ghé qua (TQGP0xx)
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


# 4. Thuật toán OSRM & Tối ưu lộ trình
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


def solve_tsp_with_end(start_coords, intermediate_points, end_point=None):
    unvisited = intermediate_points.copy()
    current_pos = start_coords
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


# 5. Xử lý nút bấm Tính toán
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None

if st.sidebar.button("🚀 Tối ưu đường đi XE MÁY"):
    if not final_selected_names and not end_location:
        st.sidebar.warning(
            "Vui lòng chọn điểm TQGP0xx hoặc nhập Điểm Kết Thúc!"
        )
    else:
        with st.spinner("Đang tính toán lộ trình xe máy tại Tuyên Quang..."):
            if final_selected_names:
                start_name = final_selected_names[0]
                start_coords = (
                    all_points[start_name]["lat"],
                    all_points[start_name]["lon"],
                )
                intermediate_names = final_selected_names[1:]
            else:
                start_coords = (21.82714, 105.19952)
                start_name = "Xuất phát"
                intermediate_names = []

            intermediate_points = [
                {
                    "name": name,
                    "lat": all_points[name]["lat"],
                    "lon": all_points[name]["lon"],
                }
                for name in intermediate_names
            ]

            st.session_state.calculated_route = solve_tsp_with_end(
                start_coords, intermediate_points, end_location
            )
            st.session_state.start_coords = start_coords
            st.session_state.start_name = start_name

# 6. Display View Map
if st.session_state.calculated_route is not None:
    optimized_route = st.session_state.calculated_route
    s_lat, s_lon = st.session_state.start_coords
    s_name = st.session_state.get("start_name", "Xuất phát")

    stopping_coords = [(s_lat, s_lon)] + [
        (p["lat"], p["lon"]) for p in optimized_route
    ]
    detailed_path, real_distance = get_route_osrm(stopping_coords)

    st.sidebar.markdown("---")
    st.sidebar.success(
        f"📊 **Lộ trình xe máy Tuyên Quang**\n\nTổng quãng đường: **~ {real_distance:.2f} km**"
    )

    m = folium.Map(
        location=[s_lat, s_lon],
        zoom_start=14,
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google Maps",
    )

    LocateControl(
        auto_start=False,
        flyTo=True,
        keepCurrentZoomLevel=True,
        strings={"title": "Định vị vị trí của tôi"},
    ).add_to(m)

    # Xuất phát
    folium.Marker(
        [s_lat, s_lon],
        popup=f"Xuất phát: {s_name}",
        tooltip=f"Xuất phát: {s_name}",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    # Các điểm dừng & Đích đến
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
    # Mặc định mở trung tâm Tuyên Quang
    m_default = folium.Map(
        location=[21.82714, 105.19952],
        zoom_start=13,
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google Maps",
    )
    st_folium(
        m_default, use_container_width=True, height=850, returned_objects=[]
    )
