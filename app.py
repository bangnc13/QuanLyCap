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


# 1. Đọc dữ liệu GeoJSON an toàn
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

        # Tên điểm trong file GeoJSON
        name = str(props.get("name", "")).strip()

        if name and geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                points[name] = {
                    "lat": coords[1],
                    "lon": coords[0],
                    "id": props.get("id"),
                }
    return points


# Đảm bảo file data.geojson được đặt cùng thư mục với app.py trên GitHub
GEOJSON_FILE = "data.geojson"
all_points = load_geojson(GEOJSON_FILE)

if not all_points:
    st.error(
        f"⚠️ Không tìm thấy file '{GEOJSON_FILE}' trong thư mục ứng dụng! Vui lòng upload file '{GEOJSON_FILE}' lên GitHub."
    )

# 2. Vị trí GPS
st.sidebar.header("📍 Vị trí GPS xuất phát")
location = get_geolocation()

start_lat, start_lon = 21.82714, 105.19952  # Giá trị mặc định từ GPS của bạn
if location and "coords" in location:
    start_lat = location["coords"]["latitude"]
    start_lon = location["coords"]["longitude"]
    st.sidebar.success(f"GPS: {start_lat:.5f}, {start_lon:.5f}")
else:
    st.sidebar.info(f"Sử dụng vị trí GPS mặc định: {start_lat}, {start_lon}")

st.sidebar.header("📋 Danh sách tập điểm cần đến")

# Chọn từ danh sách
selected_from_list = st.sidebar.multiselect(
    "Chọn điểm từ tập dữ liệu:", options=list(all_points.keys())
)

# Upload File Excel
uploaded_file = st.sidebar.file_uploader(
    "Hoặc Upload file Excel chứa cột danh sách điểm:", type=["xlsx", "xls"]
)
excel_points = []

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, header=None)
        # Chuyển toàn bộ nội dung file excel thành chuỗi
        raw_codes = df.astype(str).values.flatten()

        for code in raw_codes:
            clean_code = code.strip()
            # Đối chiếu trực tiếp với danh sách GeoJSON
            if clean_code in all_points:
                excel_points.append(clean_code)
            else:
                # Xử lý trường hợp chữ HO/HƠ bị lệch ký tự
                alt_code = clean_code.replace("/HO", "/HƠ").replace(
                    "/HƠ", "/HO"
                )
                if alt_code in all_points:
                    excel_points.append(alt_code)

        st.sidebar.info(
            f"Tìm thấy {len(excel_points)} điểm hợp lệ từ file Excel."
        )
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc file Excel: {e}")

# Tổng hợp các điểm được chọn
final_selected_names = list(set(selected_from_list + excel_points))


# 3. Thuật toán tối ưu (Nearest Neighbor)
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


# 4. Hiển thị kết quả & Bản đồ
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

        # Tính khoảng cách
        total_dist = 0
        current_p = start_coords
        for p in optimized_route:
            next_p = (p["lat"], p["lon"])
            total_dist += geodesic(current_p, next_p).km
            current_p = next_p

        st.subheader(f"📊 Kết quả lộ trình (Tổng chiều dài ~ {total_dist:.2f} km)")

        # Vẽ bản đồ
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

        # Bảng chi tiết
        route_df = pd.DataFrame(optimized_route)[["name", "lat", "lon"]]
        route_df.index = np.arange(1, len(route_df) + 1)
        st.dataframe(route_df)
