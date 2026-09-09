import json
import os
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
st.title("🏍️ Tối ưu hóa quãng đường di chuyển (Xe máy)")


# 1. Đọc file GeoJSON
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
                    if p_name:
                        points[p_name] = {"lat": coords[1], "lon": coords[0]}
    return points


GEOJSON_FILE = "data.geojson"
all_points = load_geojson(GEOJSON_FILE)

if not all_points:
    st.error(f"⚠️ Không tìm thấy file '{GEOJSON_FILE}' hoặc file bị rỗng!")

# 2. Vị trí GPS xuất phát
st.sidebar.header("📍 Vị trí GPS xuất phát")
start_lat = st.sidebar.number_input(
    "Vĩ độ (Lat):", value=21.82714, format="%.5f"
)
start_lon = st.sidebar.number_input(
    "Kinh độ (Lon):", value=105.19952, format="%.5f"
)

st.sidebar.header("📋 Danh sách tập điểm cần đến")

unique_keys = list(all_points.keys())
selected_from_list = st.sidebar.multiselect(
    "Chọn điểm từ tập dữ liệu:", options=unique_keys
)

uploaded_file = st.sidebar.file_uploader(
    "Hoặc Upload file Excel chứa cột danh sách điểm:", type=["xlsx", "xls"]
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

            if val_clean in all_points:
                excel_points.append(val_clean)
                continue

            alt_val = val_clean.replace("/HO", "/HƠ").replace("/HƠ", "/HO")
            if alt_val in all_points:
                excel_points.append(alt_val)
                continue

            prefix_match = val_clean.split("/")[0]
            if prefix_match in all_points:
                excel_points.append(prefix_match)

        st.sidebar.info(
            f"Tìm thấy {len(excel_points)} điểm hợp lệ từ file Excel."
        )
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc file Excel: {e}")

final_selected_names = list(set(selected_from_list + excel_points))


# 3. Hàm gọi API OSRM tìm đường giao thông thực tế (Bike / Scooter / Driving)
def get_route_osrm(coords_list):
    """coords_list: danh sách tuple [(lat, lon), (lat, lon),

    ...] Trả về: (toàn bộ tọa độ đường đi thực tế, tổng khoảng cách km)
    """
    # OSRM nhận tham số dạng (lon,lat) nối nhau bằng dấu chấm phẩy
    formatted_coords = ";".join([f"{lon},{lat}" for lat, lon in coords_list])
    url = f"http://router.project-osrm.org/route/v1/bike/{formatted_coords}?overview=full&geometries=geojson"

    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("code") == "Ok":
            route_geometry = data["routes"][0]["geometry"]["coordinates"]
            # Chuyển từ (lon, lat) sang (lat, lon) cho Folium
            path = [[lat, lon] for lon, lat in route_geometry]
            distance_km = data["routes"][0]["distance"] / 1000.0
            return path, distance_km
    except Exception:
        pass

    # Nếu OSRM bận/lỗi, quay lại dùng đường thẳng dự phòng
    total_dist = 0
    for i in range(len(coords_list) - 1):
        total_dist += geodesic(coords_list[i], coords_list[i + 1]).km
    return [[lat, lon] for lat, lon in coords_list], total_dist


# Thuật toán TSP thứ tự điểm tối ưu
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
        st.warning("Vui lòng chọn hoặc upload ít nhất 1 tập điểm hợp lệ!")
    else:
        with st.spinner("Đang tính toán lộ trình xe máy qua các con đường..."):
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

# Hiển thị Bản đồ Lộ trình
if st.session_state.calculated_route is not None:
    optimized_route = st.session_state.calculated_route
    s_lat, s_lon = st.session_state.start_coords

    # Tổng hợp danh sách tọa độ dừng
    stopping_coords = [(s_lat, s_lon)] + [
        (p["lat"], p["lon"]) for p in optimized_route
    ]

    # Lấy đường đi thực tế từ OSRM
    detailed_path, real_distance = get_route_osrm(stopping_coords)

    st.subheader(
        f"📊 Lộ trình xe máy tối ưu (Quãng đường thực tế ~ {real_distance:.2f} km)"
    )

    # Khởi tạo bản đồ OpenStreetMap
    m = folium.Map(
        location=[s_lat, s_lon],
        zoom_start=14,
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    )

    # Nút định vị GPS Realtime
    LocateControl(
        auto_start=False,
        flyTo=True,
        keepCurrentZoomLevel=True,
        strings={"title": "Định vị vị trí của tôi"},
    ).add_to(m)

    # Marker Xuất phát
    folium.Marker(
        [s_lat, s_lon],
        popup="Vị trí xuất phát",
        tooltip="Xuất phát",
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)

    # Marker các điểm dừng theo thứ tự
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

    # Vẽ đường xe máy thực tế (uốn lượn theo các ngã rẽ)
    folium.PolyLine(
        detailed_path, color="#e63946", weight=5, opacity=0.85
    ).add_to(m)

    # Tự động zoom theo toàn bộ tuyến đường
    m.fit_bounds(stopping_coords)

    # Hiển thị bản đồ tràn màn hình
    st_folium(m, use_container_width=True, height=800, returned_objects=[])
