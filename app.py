import os 
import streamlit as st 
import pandas as pd 
import networkx as nx 
import streamlit.components.v1 as components
import json

# 1. Cấu hình trang Streamlit 
st.set_page_config(
    page_title="Xác Định Vị Trí Đứt Cáp - BangNC13", 
    layout="wide", 
    initial_sidebar_state="expanded"
) 

# CSS Tùy chỉnh giao diện full screen
st.markdown("""
    <style>
        html, body, [data-testid="stAppViewContainer"], .main, .stApp {
            margin: 0 !important;
            padding: 0 !important;
            height: 100vh !important;
            overflow: hidden !important;
        }

        section[data-testid="stSidebar"] {
            z-index: 999999 !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 1.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        .sidebar-title {
            font-size: 1.15rem !important;
            font-weight: 700 !important;
            color: #1F2937 !important;
            margin-bottom: 2px !important;
        }
        .sidebar-subtitle {
            font-size: 0.8rem !important;
            color: #6B7280 !important;
            margin-bottom: 12px !important;
        }

        header[data-testid="stHeader"] {
            background: transparent !important;
            height: 0px !important;
            z-index: 999999 !important;
        }

        .main .block-container, 
        [data-testid="stMainBlockContainer"],
        [data-testid="stVerticalBlock"],
        [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0 !important;
            margin: 0 !important;
            gap: 0rem !important;
            max-width: 100vw !important;
            height: 100vh !important;
        }

        iframe {
            width: 100vw !important;
            height: 100vh !important;
            border: none !important;
            margin: 0 !important;
            padding: 0 !important;
            display: block !important;
        }
    </style>
""", unsafe_allow_html=True)

# Khởi tạo session state
if "break_result" not in st.session_state: 
    st.session_state.break_result = None 
if "break_gps" not in st.session_state: 
    st.session_state.break_gps = None 

@st.cache_data 
def load_server_data(): 
    possible_files = [ 
        "Danh-Sách-Đoạn-Cáp.xlsx",  
        "Danh_Sach_Doan_Cap.xlsx",  
        "data.xlsx",  
        "Danh-Sách-Đoạn-Cáp.xls" 
    ] 
    
    selected_file = None 
    for f in possible_files: 
        if os.path.exists(f): 
            selected_file = f 
            break 

    if not selected_file: 
        files = [f for f in os.listdir(".") if f.endswith(".xlsx") or f.endswith(".xls")] 
        if files: 
            selected_file = files[0] 

    if selected_file: 
        df = pd.read_excel(selected_file) 
        return df, selected_file 
    return None, None 

df, file_name = load_server_data() 

st.sidebar.markdown('<div class="sidebar-title">⚡ TQG-XÁC ĐỊNH VỊ TRÍ ĐỨT CÁP</div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="sidebar-subtitle">Fiber Optic Break Location Finder - FPT Telecom System</div>', unsafe_allow_html=True)

if df is not None: 
    st.sidebar.success(f"🐒 Make by BangNC13") 
    
    df.columns = [str(col).strip() for col in df.columns] 
    
    lat_col1 = next((c for c in df.columns if 'lat' in c.lower() and '1' in c.lower()), None) 
    lon_col1 = next((c for c in df.columns if 'lng' in c.lower() or ('lon' in c.lower() and '1' in c.lower())), None) 
    lat_col2 = next((c for c in df.columns if 'lat' in c.lower() and '2' in c.lower()), None) 
    lon_col2 = next((c for c in df.columns if 'lng' in c.lower() or ('lon' in c.lower() and '2' in c.lower())), None) 

    if not lat_col1: 
        lat_col1 = next((c for c in df.columns if 'lat' in c.lower() or 'vĩ độ' in c.lower()), None) 
        lon_col1 = next((c for c in df.columns if 'lng' in c.lower() or 'lon' in c.lower() or 'kinh độ' in c.lower()), None) 

    if 'Tên đoạn cáp' in df.columns: 
        df['POP'] = df['Tên đoạn cáp'].apply(lambda x: str(x).split('.')[0] if '.' in str(x) else str(x)) 
        pop_list = sorted(df['POP'].unique()) 
        selected_pop = st.sidebar.selectbox("LỌC DỮ LIỆU POP", pop_list, key="selected_pop") 
        pop_df = df[df['POP'] == selected_pop].copy() 
    else: 
        pop_df = df.copy() 

    G = nx.Graph() 
    node_coords = {} 

    for _, row in pop_df.iterrows(): 
        k1 = str(row.get('Điểm KN1', '')).strip() 
        k2 = str(row.get('Điểm KN2', '')).strip() 
        cable = str(row.get('Tên đoạn cáp', f"{k1}-{k2}")).strip() 
        
        len_val = row.get('Chiều dài thực (m)') 
        length = float(len_val) if pd.notnull(len_val) else 0.0 
        
        try: 
            if lat_col1 and lon_col1 and pd.notnull(row[lat_col1]) and pd.notnull(row[lon_col1]): 
                node_coords[k1] = (float(row[lat_col1]), float(row[lon_col1])) 
            if lat_col2 and lon_col2 and pd.notnull(row[lat_col2]) and pd.notnull(row[lon_col2]): 
                node_coords[k2] = (float(row[lat_col2]), float(row[lon_col2])) 
        except Exception: 
            pass 

        if k1 and k2: 
            G.add_edge(k1, k2, cable=cable, length=length) 

    st.sidebar.markdown("---") 
    st.sidebar.subheader("📍 THÔNG TIN ĐO (OTDR)") 
    
    all_nodes = sorted(list(G.nodes())) 
    if all_nodes: 
        start_node = st.sidebar.selectbox("Điểm đo (Đang đứng)", all_nodes, key="start_node") 
        neighbors = list(G.neighbors(start_node)) if start_node in G else [] 
        direction_node = st.sidebar.selectbox("Hướng đo (Xuôi ngọn / Về ODF)", neighbors, key="direction_node") 
        measured_len = st.sidebar.number_input("Chiều dài đo được (Mét)", min_value=0.0, value=170.0, step=10.0, key="measured_len") 

        col_btn1, col_btn2 = st.sidebar.columns(2) 
        with col_btn1: 
            btn_calc = st.button("🎯 Xác định", type="primary", use_container_width=True) 
        with col_btn2: 
            btn_reset = st.button("🔄 Xóa", use_container_width=True) 

        if btn_reset: 
            st.session_state.break_result = None 
            st.session_state.break_gps = None 
            st.rerun() 

        if btn_calc and start_node and direction_node: 
            current = start_node 
            nxt = direction_node 
            accumulated = 0.0 
            visited = {current} 

            b_res = None 
            b_gps = None 

            while True: 
                edge_data = G[current][nxt] 
                seg_len = edge_data['length'] 
                cable_id = edge_data['cable'] 
                visited.add(nxt) 

                if accumulated + seg_len >= measured_len: 
                    d1 = measured_len - accumulated 
                    d2 = seg_len - d1 
                    b_res = { 
                        "cable": cable_id, 
                        "from": current, 
                        "to": nxt, 
                        "d1": d1, 
                        "d2": d2, 
                        "seg_len": seg_len, 
                        "total": measured_len 
                    } 

                    if current in node_coords and nxt in node_coords and seg_len > 0: 
                        lat1, lon1 = node_coords[current] 
                        lat2, lon2 = node_coords[nxt] 
                        ratio = d1 / seg_len 
                        break_lat = lat1 + (lat2 - lat1) * ratio 
                        break_lon = lon1 + (lon2 - lon1) * ratio 
                        b_gps = (break_lat, break_lon) 
                    break 
                else: 
                    accumulated += seg_len 
                    next_nodes = [n for n in G.neighbors(nxt) if n not in visited] 
                    if not next_nodes: 
                        break 
                    current = nxt 
                    nxt = next_nodes[0] 

            st.session_state.break_result = b_res 
            st.session_state.break_gps = b_gps 
            st.rerun() 

    # Hiển thị trên Sidebar khi có kết quả
    if st.session_state.break_result: 
        res = st.session_state.break_result 
        st.sidebar.error("📍 VỊ TRÍ ĐỨT CÁP DỰ KIẾN") 
        st.sidebar.markdown(f"**Đoạn cáp:** `{res['cable']}`") 
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("**📐 Khoảng cách đến 2 điểm kết nối:**")
        st.sidebar.info(
            f"🔹 **Từ {res['from']}:** `{res['d1']:.1f} m` (Tổng {res['seg_len']}m)\n\n"
            f"🔸 **Từ {res['to']}:** `{res['d2']:.1f} m`"
        )
          
        if st.session_state.break_gps: 
            gps = st.session_state.break_gps 
            gmap_url = f"https://www.google.com/maps?q={gps[0]},{gps[1]}" 
            st.sidebar.markdown(f"📍 **GPS:** `{gps[0]:.6f}, {gps[1]:.6f}`") 
            st.sidebar.link_button("📍 Mở trên Google Maps", gmap_url, type="primary", use_container_width=True)

    # 3. Chuẩn bị Dữ liệu Render Bản đồ Leaflet JS
    map_center = [21.0285, 105.8542] 
    zoom_lvl = 12 

    if st.session_state.break_gps: 
        map_center = list(st.session_state.break_gps)
        zoom_lvl = 18 
    elif len(node_coords) > 0: 
        first_coord = list(node_coords.values())[0] 
        map_center = [first_coord[0], first_coord[1]] 
        zoom_lvl = 15 

    polylines = []
    markers = []
    break_marker = None

    if st.session_state.break_result: 
        u = st.session_state.break_result['from'] 
        v = st.session_state.break_result['to'] 

        if u in node_coords and v in node_coords: 
            polylines.append({
                "coords": [node_coords[u], node_coords[v]],
                "color": "#EF4444",
                "weight": 6,
                "opacity": 0.9,
                "tooltip": f"Sự cố đoạn: {st.session_state.break_result['cable']}"
            })

            for node in [u, v]: 
                markers.append({
                    "coords": node_coords[node],
                    "popup": f"<b>Điểm Kết Nối:</b> {node}",
                    "tooltip": f"Điểm KN: {node}",
                    "color": "#3B82F6",
                    "radius": 7
                })

        if st.session_state.break_gps: 
            res = st.session_state.break_result
            gps = st.session_state.break_gps
            gmap_url = f"https://www.google.com/maps?q={gps[0]},{gps[1]}"
            
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; min-width: 180px;">
                <b style="color: #DC2626; font-size: 13px;">🚨 VỊ TRÍ ĐỨT CÁP: {res['cable']}</b><br/>
                <div style="margin: 6px 0; font-size: 12px; line-height: 1.4;">
                    • Cách <b>{res['from']}</b>: {res['d1']:.1f}m<br/>
                    • Cách <b>{res['to']}</b>: {res['d2']:.1f}m
                </div>
                <a href="{gmap_url}" target="_blank" style="
                    display: inline-block;
                    width: 100%;
                    text-align: center;
                    background-color: #10B981;
                    color: white;
                    padding: 6px 0;
                    margin-top: 4px;
                    border-radius: 4px;
                    text-decoration: none;
                    font-weight: bold;
                    font-size: 11px;
                ">📍 Mở trên Google Maps</a>
            </div>
            """
            
            break_marker = {
                "coords": list(st.session_state.break_gps),
                "popup": popup_html,
                "tooltip": "🚨 Vị trí đứt cáp dự kiến"
            }

    else: 
        for u, v, data in G.edges(data=True): 
            if u in node_coords and v in node_coords: 
                polylines.append({
                    "coords": [node_coords[u], node_coords[v]],
                    "color": "#2B5C8F",
                    "weight": 3,
                    "opacity": 0.6,
                    "tooltip": f"Cáp: {data.get('cable', '')}"
                })

        for node_id, coord in node_coords.items(): 
            markers.append({
                "coords": coord,
                "popup": f"<b>Điểm KN:</b> {node_id}",
                "tooltip": str(node_id),
                "color": "#2B5C8F",
                "radius": 4
            })

    leaflet_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            html, body {{
                width: 100%;
                height: 100vh;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }}
            #map {{
                width: 100%;
                height: 100vh;
                background: #f8f9fa;
            }}
            .custom-break-icon {{
                background-color: #EF4444;
                border: 2px solid #FFFFFF;
                border-radius: 50%;
                width: 24px !important;
                height: 24px !important;
                margin-left: -12px !important;
                margin-top: -12px !important;
                box-shadow: 0 0 10px rgba(239, 68, 68, 0.8);
                animation: pulse 1.5s infinite;
            }}
            @keyframes pulse {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
                70% {{ transform: scale(1.2); box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
            }}
            .leaflet-control-layers {{
                font-family: Arial, sans-serif;
                border-radius: 8px !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                var streetMap = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '&copy; OpenStreetMap contributors',
                    crossOrigin: true
                }});

                var satelliteMap = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    maxZoom: 19,
                    attribution: 'Tiles &copy; Esri',
                    crossOrigin: true
                }});

                var map = L.map('map', {{
                    zoomControl: true,
                    attributionControl: false,
                    layers: [streetMap]
                }}).setView({json.dumps(map_center)}, {zoom_lvl});

                var baseMaps = {{
                    "🗺️ Đường phố": streetMap,
                    "🛰️ Vệ tinh": satelliteMap
                }};
                L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

                var polylinesData = {json.dumps(polylines)};
                polylinesData.forEach(function(item) {{
                    var line = L.polyline(item.coords, {{
                        color: item.color,
                        weight: item.weight,
                        opacity: item.opacity
                    }}).addTo(map);
                    if (item.tooltip) line.bindTooltip(item.tooltip);
                }});

                var markersData = {json.dumps(markers)};
                markersData.forEach(function(item) {{
                    var circle = L.circleMarker(item.coords, {{
                        radius: item.radius,
                        color: item.color,
                        fillColor: '#FFFFFF',
                        fillOpacity: 0.9,
                        weight: 2
                    }}).addTo(map);
                    if (item.popup) circle.bindPopup(item.popup);
                    if (item.tooltip) circle.bindTooltip(item.tooltip);
                }});

                var breakMarkerData = {json.dumps(break_marker)};
                if (breakMarkerData) {{
                    var breakIcon = L.divIcon({{ className: 'custom-break-icon' }});
                    var bMarker = L.marker(breakMarkerData.coords, {{ icon: breakIcon }}).addTo(map);
                    if (breakMarkerData.popup) bMarker.bindPopup(breakMarkerData.popup).openPopup();
                    if (breakMarkerData.tooltip) bMarker.bindTooltip(breakMarkerData.tooltip);
                }}

                setTimeout(function() {{
                    map.invalidateSize();
                }}, 200);
            }});
        </script>
    </body>
    </html>
    """

    components.html(leaflet_html, height=1000, scrolling=False)

else: 
    st.error("❌ Không tìm thấy file Excel trên Server. Vui lòng kiểm tra lại tên file `Danh-Sách-Đoạn-Cáp.xlsx` trong thư mục chạy mã.")
