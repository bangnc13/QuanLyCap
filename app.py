import json
import os
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="Tối ưu lộ trình - Google Maps Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------
# 1. CẤU HÌNH GOOGLE MAPS API KEY
# -------------------------------------------------------------
# Thay API Key của bạn vào đây (Cần bật Directions API và Maps JavaScript API)
GOOGLE_MAPS_API_KEY = st.sidebar.text_input(
    "🔑 Nhập Google Maps API Key:", type="password"
)

# -------------------------------------------------------------
# 2. LOGO & CSS GIAO DIỆN
# -------------------------------------------------------------
logo_path = "FPT_Telecom_logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_container_width=True)

st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        padding: 0 !important;
        margin: 0 !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    header[data-testid="stHeader"] { height: 0px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------------------------------------------------
# 3. LOAD GEOJSON
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
                for val in props.values():
                    val_str = str(val).strip()
                    if "TQGP0" in val_str.upper():
                        points[val_str] = {"lat": coords[1], "lon": coords[0]}
    return points


GEOJSON_FILE = "data.geojson"
all_points = load_geojson(GEOJSON_FILE)
unique_keys = sorted(list(all_points.keys()))

# -------------------------------------------------------------
# 4. CHỌN ĐIỂM TRÊN SIDEBAR
# -------------------------------------------------------------
st.sidebar.header("📋 Chọn danh sách điểm dừng")
selected_from_list = st.sidebar.multiselect(
    "Chọn điểm TQGP0xx:", options=unique_keys
)

uploaded_file = st.sidebar.file_uploader(
    "Upload file Excel:", type=["xlsx", "xls"]
)
excel_points = []

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, header=None)
        raw_values = df.astype(str).values.flatten()
        for val in raw_values:
            val_clean = val.strip()
            if "TQGP0" in val_clean.upper() and val_clean in all_points:
                excel_points.append(val_clean)
        st.sidebar.info(f"Tìm thấy {len(excel_points)} điểm từ Excel.")
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc file: {e}")

final_selected_names = list(set(selected_from_list + excel_points))

# -------------------------------------------------------------
# 5. TẠO BẢN ĐỒ BẰNG GOOGLE MAPS JS API (TỰ ĐỘNG TỐI ƯU BẰNG GOOGLE)
# -------------------------------------------------------------
def render_google_map(points_data, api_key):
    locations_js = json.dumps(points_data)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            #map {{ height: 100vh; width: 100%; }}
            html, body {{ height: 100%; margin: 0; padding: 0; }}
            #panel {{
                position: absolute; top: 10px; left: 10px; z-index: 5;
                background: white; padding: 10px; border-radius: 8px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-family: sans-serif;
            }}
        </style>
        <script src="https://maps.googleapis.com/maps/api/js?key={api_key}&libraries=places"></script>
    </head>
    <body>
        <div id="panel">
            <b>📍 Trạng thái:</b> <span id="status">Đang lấy GPS...</span><br>
            <b>📏 Tổng quãng đường:</b> <span id="distance">-</span>
        </div>
        <div id="map"></div>

        <script>
            let map, directionsService, directionsRenderer;
            const rawPoints = {locations_js};

            function initMap() {{
                map = new google.maps.Map(document.getElementById("map"), {{
                    zoom: 14,
                    center: {{ lat: 21.82714, lng: 105.19952 }},
                    mapTypeControl: false,
                }});

                directionsService = new google.maps.DirectionsService();
                directionsRenderer = new google.maps.DirectionsRenderer({{
                    map: map,
                    suppressMarkers: false,
                    polylineOptions: {{
                        strokeColor: "#1A73E8",
                        strokeOpacity: 0.9,
                        strokeWeight: 6
                    }}
                }});

                // Lấy GPS Realtime làm điểm xuất phát
                if (navigator.geolocation) {{
                    navigator.geolocation.getCurrentPosition(
                        (position) => {{
                            const origin = {{
                                lat: position.coords.latitude,
                                lng: position.coords.longitude
                            }};
                            document.getElementById("status").innerText = "Đã lấy GPS. Đang tối ưu lộ trình Google...";
                            calculateGoogleRoute(origin);
                        }},
                        () => {{
                            // Mặc định nếu lỗi GPS
                            const defaultOrigin = {{ lat: 21.82714, lng: 105.19952 }};
                            calculateGoogleRoute(defaultOrigin);
                        }},
                        {{ enableHighAccuracy: true }}
                    );
                }} else {{
                    calculateGoogleRoute({{ lat: 21.82714, lng: 105.19952 }});
                }}
            }}

            function calculateGoogleRoute(origin) {{
                if (rawPoints.length === 0) {{
                    document.getElementById("status").innerText = "Chưa chọn điểm nào!";
                    map.setCenter(origin);
                    new google.maps.Marker({{ position: origin, map: map, title: "Vị trí của bạn" }});
                    return;
                }}

                // Tạo danh sách waypoints cho Google
                const waypoints = rawPoints.map(pt => ({{
                    location: new google.maps.LatLng(pt.lat, pt.lon),
                    stopover: true
                }}));

                // Điểm cuối cùng trong danh sách chọn làm điểm kết thúc tạm thời
                const destination = waypoints.pop().location;

                const request = {{
                    origin: origin,
                    destination: destination,
                    waypoints: waypoints,
                    optimizeWaypoints: true, // THUẬT TOÁN TỐI ƯU ĐIỂM DỪNG CỦA GOOGLE MAPS
                    travelMode: google.maps.TravelMode.TWO_WHEELER // CHẾ ĐỘ XE MÁY
                }};

                directionsService.route(request, (result, status) => {{
                    if (status === google.maps.DirectionsStatus.OK) {{
                        directionsRenderer.setDirections(result);
                        
                        // Tính tổng quãng đường
                        let totalDist = 0;
                        const route = result.routes[0];
                        for (let i = 0; i < route.legs.length; i++) {{
                            totalDist += route.legs[i].distance.value;
                        }}
                        document.getElementById("distance").innerText = (totalDist / 1000).toFixed(2) + " km";
                        document.getElementById("status").innerText = "Đã tối ưu xong!";
                    }} else {{
                        document.getElementById("status").innerText = "Lỗi tính lộ trình: " + status;
                    }}
                }});
            }}

            window.onload = initMap;
        </script>
    </body>
    </html>
    """
    return components.html(html_code, height=1000)

# -------------------------------------------------------------
# 6. HIỂN THỊ
# -------------------------------------------------------------
if not GOOGLE_MAPS_API_KEY:
    st.warning("⚠️ Vui lòng nhập **Google Maps API Key** ở menu bên trái để kích hoạt thuật toán định tuyến chính xác của Google.")
else:
    points_to_send = [
        {"name": name, "lat": all_points[name]["lat"], "lon": all_points[name]["lon"]}
        for name in final_selected_names if name in all_points
    ]
    render_google_map(points_to_send, GOOGLE_MAPS_API_KEY)
