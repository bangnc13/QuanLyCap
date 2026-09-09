import json
import os
import re
import folium
import numpy as np
import pandas as pd
import streamlit as st
from geopy.distance import geodesic
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="Tối ưu đường đi kỹ thuật", layout="wide")
st.title("🚗 Tối ưu hóa quãng đường di chuyển")


# 1. Đọc GeoJSON linh hoạt (quét sạch các thuộc tính name/id/label)
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
                # Gom tất cả thuộc tính dạng chữ thành danh sách định danh
                possible_names = []
                for val in props.values():
                    if isinstance(val, (str, int)):
                        possible_names.append(str(val).strip())

                # Lưu tọa độ cho từng định danh tìm được
                for p_name in possible_names:
                    if p_name:
                        points[p_name] = {"lat": coords[1], "lon": coords[0]}
    return points


GEOJSON_FILE = "data.geojson"
all_points = load_geojson(GEOJSON_FILE)

if not all_points:
    st.error(
        f"⚠️ File '{GEOJSON_FILE}' không có dữ liệu tọa độ hoặc lỗi định dạng!"
    )

# 2. Vị trí GPS
st.sidebar.header("📍 Vị trí GPS xuất phát")
location = get_geolocation()

start_lat, start_lon = 21.82714, 105.19952
if location and "coords" in location:
    start_lat = location["coords"]["latitude"]
    start_lon = location["coords"]["longitude"]
    st.sidebar.success(f"GPS: {start_lat:.5f}, {start_lon:.5f}")
else:
    st.sidebar.info(f"Sử dụng GPS mặc định: {start_lat}, {start_lon}")

st.sidebar.header("📋 Danh sách tập điểm cần đến")

# Multiselect các điểm có trong GeoJSON
unique_keys = list(all_points.keys())
selected_from_list = st.sidebar.multiselect(
    "Chọn điểm từ tập dữ liệu:", options=unique_keys
)

# Upload File Excel
uploaded_file = st.sidebar.file_uploader(
    "Hoặc Upload file Excel chứa cột danh sách điểm:", type=["xlsx", "xls"]
)
excel_points = []

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, header=None)
        # Lấy toàn bộ ô dữ liệu dạng chuỗi
        raw_values = df.astype(str).values.flatten()

        for val in raw_values:
            val_clean = val.strip()
            if not val_clean or val_clean == "nan":
                continue

            # 1. So sánh chính xác
            if val_clean in all_points:
                excel_points.append(val_clean)
                continue

            # 2. So sánh thay thế HO <-> HƠ
            alt_val = val_clean.replace("/HO", "/HƠ").replace("/HƠ", "/HO")
            if alt_val in all_points:
                excel_points.append(alt_val)
                continue

            # 3. So sánh tương đối (Ví dụ Excel là TQGP013.0290/HO nhưng GeoJSON ghi TQGP013.0290)
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


# 4. Hiển thị Kết quả & Bản đồ
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
        optimized_route = solve_tsp(start_coords, target_points)

        total_dist = 0
        current_p = start_coords
        for p in optimized_route:
            next_p = (p["lat"], p["lon"])
            total_dist += geodesic(current_p, next_p).km
            current_p = next_p

        st.subheader(f"📊 Kết quả lộ trình (Tổng chiều dài ~ {total_dist:.2f} km)")

        m = folium.Map(location=[start_lat, start_lon], zoom_start=13)
        folium.Marker(
            [start_lat, start_lon],
            popup="Vị trí xuất phát",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(m)

        route_coords = [[start_lat, start_lon]]
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

        st_folium(m, width=900, height=500)

        route_df = pd.DataFrame(optimized_route)[["name", "lat", "lon"]]
        route_df.index = np.arange(1, len(route_df) + 1)
        st.dataframe(route_df)
