import json
import os
import re
import folium
import numpy as np
import pandas as pd
import requests
import streamlit as st
from folium.plugins import LocateControl
from geopy.distance import geodesic
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Tối ưu đường di chuyển xe máy", layout="wide"
)

# Thêm tiêu đề chính vào thanh Menu bên trái
st.sidebar.title("🏍️ Tối ưu hóa quãng đường di chuyển (Xe máy)")


# 1. Đọc file GeoJSON và chỉ lọc các điểm định dạng TQGP0xx
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
                    # Lọc chỉ lấy các tên có định dạng TQGP0...
                    if p_name and "TQGP0" in p_name.upper():
                        points[p_name] = {"lat": coords[1], "lon": coords[0]}
    return points


GEOJSON_FILE = "data.geojson"
all_points = load_geojson(GEOJSON_FILE)

if not all_points:
    st.sidebar.error(
        f"⚠️ Không tìm thấy điểm nào dạng 'TQGP0xx' trong '{GEOJSON_FILE}'!"
    )

unique_keys = sorted(list(all_points.keys()))

# 2. Vị trí xuất phát: Chọn từ danh sách GeoJSON (đã lọc TQGP0)
st.sidebar.header("📍 Chọn điểm xuất phát")
start_point_name = st.sidebar.selectbox(
    "Chọn điểm xuất phát:",
    options=unique_keys,
    index=0 if unique_keys else None,
)

if start_point_name:
    start_lat = all_points[start_point_name]["lat"]
    start_lon = all_points[start_point_name]["lon"]
else:
    start_lat, start_lon = 21.82714, 105.19952

st.sidebar.header("📋 Danh sách tập điểm cần đến")

selected_from_list = st.sidebar.multiselect(
    "Chọn các điểm cần đến (TQGP0xx):", options=unique_keys
)

uploaded_file = st.sidebar.file_uploader(
    "Hoặc Upload file Excel chứa danh sách điểm:", type=["xlsx", "xls"]
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

            # Chỉ giữ lại giá trị phù hợp định dạng TQGP0
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

        st.sidebar.info(
            f"Tìm thấy {len(excel_points)} điểm TQGP0xx hợp lệ từ file Excel."
        )
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc file Excel: {e}")

final_selected_names = list(set(selected_from_list + excel_points))
# Loại bỏ điểm xuất phát khỏi danh sách điểm đến nếu bị trùng
if start_point_name in final_selected_names:
    final_selected_names.remove(start_point_name)


# 3. Hàm OSRM chỉ đường xe máy
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


def solve_tsp(start_coords, points):
    unvisited = points.copy()
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

    return route


# 4. Quản lý trạng thái Session State
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None

if st.sidebar.button("🚀 Tối ưu đường đi XE MÁY"):
    if not final_selected_names:
        st.sidebar.warning("Vui lòng chọn hoặc upload ít nhất 1 điểm!")
    else:
        with st.spinner("Đang tính toán lộ trình xe máy..."):
            target_points = [
                {
                    "name": name,
                    "lat": all_points[name]["lat"],
                    "lon": all_points[name]["lon"],
                }
                for name in final_selected_names
            ]
            start_coords = (start_lat, start_lon)
            st.session_state.calculated_route = solve_tsp(
                start_coords, target_points
            )
            st.session_state.start_coords = start_coords
            st.session_state.start_name = start_point_name

# Tính toán & Hiển thị thông số kết quả sang Sidebar
if st.session_state.calculated_route is not None:
    optimized_route = st.session_state.calculated_route
    s_lat, s_lon = st.session_state.start_coords
    s_name = st.session_state.get("start_name", "Xuất phát")

    stopping_coords = [(s_lat, s_lon)] + [
        (p["lat"], p["lon"]) for p in optimized_route
    ]
    detailed_path, real_distance = get_route_osrm(stopping_coords)

    # Đưa kết quả lộ trình vào sidebar trái
    st.sidebar.markdown("---")
    st.sidebar.success(
        f"📊 **Lộ trình xe máy tối ưu**\n\nQuãng đường thực tế: **~ {real_distance:.2f} km**"
    )

    # Khởi tạo bản đồ Google Maps Đường phố
    m = folium.Map(
        location=[s_lat, s_lon],
        zoom_start=14,
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

    # Marker xuất phát (Màu đỏ)
    folium.Marker(
        [s_lat, s_lon],
        popup=f"Xuất phát: {s_name}",
        tooltip=f"Xuất phát: {s_name}",
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)

    # Marker điểm đến theo thứ tự (Xanh)
    for idx, point in enumerate(optimized_route, start=1):
        p_lat, p_lon = point["lat"], point["lon"]
        folium.Marker(
            [p_lat, p_lon],
            popup=f"Bước {idx}: {point['name']}",
            tooltip=f"{idx}. {point['name']}",
            icon=folium.DivIcon(
                html=f'<div style="font-size: 10pt; font-weight: bold; color: white; background-color: #0078ff; border: 2px solid white; border-radius: 50%; width: 26px; height: 26px; text-align: center; line-height: 22px;">{idx}</div>'
            ),
        ).add_to(m)

    # Đường chỉ dẫn xe máy
    folium.PolyLine(
        detailed_path, color="#e63946", weight=5, opacity=0.85
    ).add_to(m)

    m.fit_bounds(stopping_coords)

    # Hiển thị View Map tràn viền góc phải màn hình
    st_folium(m, use_container_width=True, height=850, returned_objects=[])
else:
    # Màn hình chờ mặc định khi chưa bấm tính toán
    m_default = folium.Map(
        location=[start_lat, start_lon],
        zoom_start=13,
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google Maps",
    )
    st_folium(
        m_default, use_container_width=True, height=850, returned_objects=[]
    )
