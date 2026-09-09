import json
import os
import folium
import numpy as np
import pandas as pd
import streamlit as st
from geopy.distance import geodesic
from streamlit_folium import st_folium

st.set_page_config(page_title="Tối ưu đường đi kỹ thuật", layout="wide")
st.title("🚗 Tối ưu hóa quãng đường di chuyển")


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

# 2. Vị trí GPS xuất phát cố định (tránh reset lại trang)
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


# 3. Thuật toán TSP
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


# 4. Quản lý trạng thái bằng Session State
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None

if st.sidebar.button("🚀 Tối ưu đường đi"):
    if not final_selected_names:
        st.warning("Vui lòng chọn hoặc upload ít nhất 1 tập điểm hợp lệ!")
    else:
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

# Hiển thị kết quả lưu trong Session State
if st.session_state.calculated_route is not None:
    optimized_route = st.session_state.calculated_route
    s_lat, s_lon = st.session_state.start_coords

    total_dist = 0
    current_p = (s_lat, s_lon)
    for p in optimized_route:
        next_p = (p["lat"], p["lon"])
        total_dist += geodesic(current_p, next_p).km
        current_p = next_p

    st.subheader(f"📊 Kết quả lộ trình (Tổng chiều dài ~ {total_dist:.2f} km)")

    m = folium.Map(location=[s_lat, s_lon], zoom_start=13)
    folium.Marker(
        [s_lat, s_lon],
        popup="Vị trí xuất phát",
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)

    route_coords = [[s_lat, s_lon]]
    for idx, point in enumerate(optimized_route, start=1):
        p_lat, p_lon = point["lat"], point["lon"]
        route_coords.append([p_lat, p_lon])

        folium.Marker(
            [p_lat, p_lon],
            popup=f"Bước {idx}: {point['name']}",
            tooltip=f"{idx}. {point['name']}",
            icon=folium.DivIcon(
                html=f'<div style="font-size: 10pt; color: white; background-color: blue; border-radius: 50%; width: 22px; height: 22px; text-align: center; line-height: 22px;">{idx}</div>'
            ),
        ).add_to(m)

    folium.PolyLine(
        route_coords, color="blue", weight=3, opacity=0.8
    ).add_to(m)

    # Đảm bảo bản đồ giữ nguyên kích thước không giật lag
    st_folium(m, width=900, height=500, returned_objects=[])

    route_df = pd.DataFrame(optimized_route)[["name", "lat", "lon"]]
    route_df.index = np.arange(1, len(route_df) + 1)
    st.dataframe(route_df)
