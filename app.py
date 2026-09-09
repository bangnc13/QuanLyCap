import json
import re
import folium
import numpy as np
import pandas as pd
import streamlit as st
from geopy.distance import geodesic
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation

# ----------------------------------------------------
# 1. Cấu hình giao diện Streamlit
# ----------------------------------------------------
st.set_page_config(
    page_title="Tối ưu đường đi kỹ thuật", layout="wide"
)
st.title("🚗 Tối ưu hóa quãng đường di chuyển")


# ----------------------------------------------------
# 2. Thuật toán giải quyết bài toán TSP (Gần nhất - Nearest Neighbor)
# ----------------------------------------------------
def solve_tsp(start_coords, points_coords):
    """
    start_coords: (lat, lon) vị trí xuất phát
    points_coords: danh sách dict [{'name': str, 'lat': float, 'lon': float}]
    """
    unvisited = points_coords.copy()
    current_pos = start_coords
    route = []

    while unvisited:
        # Tìm điểm gần vị trí hiện tại nhất
        nearest = min(
            unvisited,
            key=lambda p: geodesic(current_pos, (p["lat"], p["lon"])).km,
        )
        route.append(nearest)
        current_pos = (nearest["lat"], nearest["lon"])
        unvisited.remove(nearest)

    return route


# ----------------------------------------------------
# 3. Tải và xử lý dữ liệu GeoJSON
# ----------------------------------------------------
@st.cache_data
def load_geojson(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    points = {}
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})

        name = props.get("name", "")
        # Lọc danh sách tập điểm có dạng TQGP... hoặc TQGM...
        if name and geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                points[name] = {
                    "lat": coords[1],
                    "lon": coords[0],
                    "id": props.get("id"),
                }
    return points


# Nhập đường dẫn file GeoJSON gốc trên hệ thống
GEOJSON_FILE = "data.geojson"
try:
    all_points = load_geojson(GEOJSON_FILE)
except Exception as e:
    st.error(f"Chưa tìm thấy file {GEOJSON_FILE} hoặc lỗi đọc file GeoJSON!")
    all_points = {}

# ----------------------------------------------------
# 4. Giao diện Sidebar: Lấy vị trí GPS & Chọn danh sách điểm
# ----------------------------------------------------
st.sidebar.header("📍 Vị trí GPS xuất phát")
location = get_geolocation()

start_lat, start_lon = None, None
if location and "coords" in location:
    start_lat = location["coords"]["latitude"]
    start_lon = location["coords"]["longitude"]
    st.sidebar.success(f"GPS: {start_lat:.5f}, {start_lon:.5f}")
else:
    st.sidebar.warning(
        "Chưa nhận được vị trí GPS từ điện thoại. Vui lòng bật định vị trình duyệt."
    )
    # Vị trí mặc định (Ví dụ Tuyên Quang)
    start_lat = st.sidebar.number_input("Nhập Lat xuất phát", value=21.8181)
    start_lon = st.sidebar.number_input("Nhập Lon xuất phát", value=105.2073)

st.sidebar.header("📋 Danh sách tập điểm cần đến")

# Mục 1: Chọn từ ô Dropdown/Multiselect
selected_from_list = st.sidebar.multiselect(
    "Chọn điểm từ tập dữ liệu:", options=list(all_points.keys())
)

# Mục 2: Import file Excel danh sách cần chọn
uploaded_file = st.sidebar.file_uploader(
    "Hoặc Upload file Excel chứa cột danh sách điểm:", type=["xlsx", "xls"]
)
excel_points = []
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        # Lấy toàn bộ giá trị text trong file Excel có định dạng dạng TQ...
        raw_text = " ".join(df.astype(str).values.flatten())
        # Tìm các mã dạng TQGP... hoặc TQGM... bằng Regex
        matched_names = re.findall(r"TQ[A-Z0-9\.\/]+", raw_text)
        excel_points = [p for p in matched_names if p in all_points]
        st.sidebar.info(f"Tìm thấy {len(excel_points)} điểm hợp lệ từ Excel.")
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc file Excel: {e}")

# Tổng hợp danh sách điểm cần di chuyển
final_selected_names = list(set(selected_from_list + excel_points))

# ----------------------------------------------------
# 5. Xử lý tối ưu hóa lộ trình và Hiển thị
# ----------------------------------------------------
if st.sidebar.button("🚀 Tối ưu đường đi"):
    if not final_selected_names:
        st.warning("Vui lòng chọn hoặc upload ít nhất 1 tập điểm!")
    else:
        # Chuẩn bị dữ liệu danh sách điểm chọn
        target_points = [
            {
                "name": name,
                "lat": all_points[name]["lat"],
                "lon": all_points[name]["lon"],
            }
            for name in final_selected_names
        ]

        # Giải bài toán lộ trình
        start_coords = (start_lat, start_lon)
        optimized_route = solve_tsp(start_coords, target_points)

        # Tính tổng quãng đường
        total_dist = 0
        current_p = start_coords
        for p in optimized_route:
            next_p = (p["lat"], p["lon"])
            total_dist += geodesic(current_p, next_p).km
            current_p = next_p

        st.subheader(f"📊 Kết quả lộ trình (Tổng chiều dài ~ {total_dist:.2f} km)")

        # Tạo bản đồ Folium
        m = folium.Map(location=[start_lat, start_lon], zoom_start=14)

        # Đánh dấu vị trí xuất phát
        folium.Marker(
            [start_lat, start_lon],
            popup="Vị trí xuất phát (GPS)",
            icon=folium.Icon(color="red", icon="user"),
        ).add_to(m)

        # Tạo danh sách tọa độ vẽ đường polyline
        route_coords = [[start_lat, start_lon]]

        # Đánh dấu từng điểm theo thứ tự tối ưu
        for idx, point in enumerate(optimized_route, start=1):
            p_lat, p_lon = point["lat"], point["lon"]
            route_coords.append([p_lat, p_lon])

            folium.Marker(
                [p_lat, p_lon],
                popup=f"Thứ tự {idx}: {point['name']}",
                tooltip=f"{idx}. {point['name']}",
                icon=folium.DivIcon(
                    html=f'<div style="font-size: 12pt; color: white; background-color: blue; border-radius: 50%; width: 24px; height: 24px; text-align: center; line-height: 24px;">{idx}</div>'
                ),
            ).add_to(m)

        # Vẽ đường nối các điểm
        folium.PolyLine(
            route_coords, color="blue", weight=4, opacity=0.7
        ).add_to(m)

        # Display Map
        st_folium(m, width=900, height=500)

        # Hiển thị bảng thứ tự di chuyển
        st.write("### Thứ tự danh sách điểm cần đến:")
        route_df = pd.DataFrame(optimized_route)[["name", "lat", "lon"]]
        route_df.index = np.arange(1, len(route_df) + 1)
        st.dataframe(route_df)
