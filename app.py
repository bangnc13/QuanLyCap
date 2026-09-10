import json
import math
import os

from concurrent.futures import ThreadPoolExecutor
import folium
from folium.plugins import LocateControl
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

# -------------------------------------------------------------
# CẤU HÌNH TRANG & GOOGLE API KEY
# -------------------------------------------------------------
st.set_page_config(
    page_title="Tối ưu đường di chuyển xe máy - Tuyên Quang",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Nhập Google Maps API Key trong sidebar hoặc cấu hình trong Secrets (.streamlit/secrets.toml)
GOOGLE_API_KEY = st.sidebar.text_input(
    "🔑 Google Maps API Key",
    type="password",
    help="Dùng Google Directions API để bám sát đường xe máy chính xác 100%",
)


# -------------------------------------------------------------
# 1. HÀM GỌI GOOGLE MAPS ROUTING (DÀNH CHO XE MÁY)
# -------------------------------------------------------------
def get_google_motorbike_route(p1, p2, api_key):
    """
    Sử dụng Google Directions API với chế độ tránh đường cao tốc (highways),
    bám theo đường xe máy / ô tô thực tế.
    """
    origin = f"{p1[0]},{p1[1]}"
    destination = f"{p2[0]},{p2[1]}"

    # mode=driving & avoid=highways giúp tìm tuyến đường tối ưu nhất cho xe máy
    url = (
        f"https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={origin}&destination={destination}&mode=driving&avoid=highways&key={api_key}"
    )

    try:
        res = requests.get(url, timeout=5).json()
        if res.get("status") == "OK":
            route = res["routes"][0]
            leg = route["legs"][0]
            dist_km = leg["distance"]["value"] / 1000.0

            # Decode Google Polyline format sang [lat, lon]
            encoded_polyline = route["overview_polyline"]["points"]
            decoded_coords = decode_polyline(encoded_polyline)

            return decoded_coords, dist_km
    except Exception as e:
        pass

    # Dự phòng nếu lỗi API Key
    return fetch_osrm_motorbike_segment((p1, p2))


def decode_polyline(polyline_str):
    """Giải mã chuỗi Polyline mã hóa của Google thành danh sách tọa độ [lat, lon]"""
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {"latitude": 0, "longitude": 0}

    while index < len(polyline_str):
        for unit in ["latitude", "longitude"]:
            shift, result = 0, 0
            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if not byte >= 0x20:
                    break
            if result & 1:
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = result >> 1

        lat += changes["latitude"]
        lng += changes["longitude"]
        coordinates.append([lat / 100000.0, lng / 100000.0])

    return coordinates


# -------------------------------------------------------------
# 2. HÀM FALLBACK OSRM NÂNG CẤP (NẾU KHÔNG CÓ GOOGLE API KEY)
# -------------------------------------------------------------
def fetch_osrm_motorbike_segment(pair):
    p1, p2 = pair
    # Tăng bán kính tìm đường lên 2000m để nhận diện đúng đường gom nhỏ nông thôn
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{p1[1]},{p1[0]};{p2[1]},{p2[0]}"
        f"?overview=full&geometries=geojson&radiuses=2000;2000&continue_straight=true"
    )

    try:
        res = requests.get(url, timeout=5).json()
        if res.get("code") == "Ok":
            route_data = res["routes"][0]
            osrm_dist = route_data["distance"] / 1000.0
            geom = [
                [lat, lon]
                for lon, lat in route_data["geometry"]["coordinates"]
            ]
            return geom, osrm_dist
    except Exception:
        pass

    # Nếu hoàn toàn không kết nối được đường bộ, nối trực tiếp
    direct_dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
    return [[p1[0], p1[1]], [p2[0], p2[1]]], direct_dist


def fetch_segment_dispatch(pair):
    p1, p2 = pair
    if GOOGLE_API_KEY:
        return get_google_motorbike_route(p1, p2, GOOGLE_API_KEY)
    else:
        return fetch_osrm_motorbike_segment((p1, p2))


def get_accurate_route_geometry_parallel(coords_list):
    pairs = [
        (coords_list[i], coords_list[i + 1])
        for i in range(len(coords_list) - 1)
    ]
    road_lines = []
    total_dist = 0.0

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_segment_dispatch, pairs))

    for geom, dist in results:
        road_lines.append(geom)
        total_dist += dist

    return road_lines, total_dist


# -------------------------------------------------------------
# 3. THUẬT TOÁN TỐI ƯU THỨ TỰ ĐIỂM (TSP)
# -------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def solve_tsp_google_style(start_coord, points, end_coord=None):
    all_coords = [start_coord] + [(p["lat"], p["lon"]) for p in points]
    if end_coord:
        all_coords.append((end_coord["lat"], end_coord["lon"]))

    n = len(all_coords)
    dist_matrix = [[0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            dist_matrix[i][j] = haversine_distance(
                all_coords[i][0],
                all_coords[i][1],
                all_coords[j][0],
                all_coords[j][1],
            )

    unvisited = set(range(1, len(points) + 1))
    curr = 0
    path = [0]
    while unvisited:
        nxt = min(unvisited, key=lambda x: dist_matrix[curr][x])
        path.append(nxt)
        unvisited.remove(nxt)
        curr = nxt

    if end_coord:
        path.append(n - 1)

    # Thuật toán 2-opt tối ưu đường đi ngắn nhất
    improved = True
    while improved:
        improved = False
        for i in range(1, len(path) - 2):
            for j in range(i + 1, len(path) - (0 if end_coord else 1)):
                if j - i == 1:
                    continue
                new_path = path[:i] + path[i : j + 1][::-1] + path[j + 1 :]
                old_d = sum(
                    dist_matrix[path[k]][path[k + 1]]
                    for k in range(len(path) - 1)
                )
                new_d = sum(
                    dist_matrix[new_path[k]][new_path[k + 1]]
                    for k in range(len(new_path) - 1)
                )
                if new_d < old_d:
                    path = new_path
                    improved = True
                    break
            if improved:
                break

    ordered_points = []
    for idx in path[1:]:
        if end_coord and idx == n - 1:
            ordered_points.append(end_coord)
        else:
            ordered_points.append(points[idx - 1])

    return ordered_points
