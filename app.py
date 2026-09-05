import os
import streamlit as st
import pandas as pd
import networkx as nx
import folium
from streamlit_folium import st_folium

# 1. Cấu hình trang Streamlit
st.set_page_config(page_title="Xác Định Vị Trí Đứt Cáp Make by BangNC13", layout="wide", initial_sidebar_state="expanded")

# Khởi tạo session state lưu kết quả
if "break_result" not in st.session_state:
    st.session_state.break_result = None
if "break_gps" not in st.session_state:
    st.session_state.break_gps = None

# Hàm tự động tìm và đọc file Excel có sẵn trên Server
@st.cache_data
def load_server_data():
    # Tìm các tên file Excel mặc định trên thư mục Server
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

    # Nếu không tìm thấy các tên cố định, quét lấy file .xlsx đầu tiên
    if not selected_file:
        files = [f for f in os.listdir(".") if f.endswith(".xlsx") or f.endswith(".xls")]
        if files:
            selected_file = files[0]

    if selected_file:
        df = pd.read_excel(selected_file)
        return df, selected_file
    return None, None

st.title("⚡ TQG-XÁC ĐỊNH VỊ TRÍ ĐỨT CÁP ")
st.caption("Fiber Optic Break Location Finder - FPT Telecom System")

# 2. Tải Dữ Liệu Từ Server
df, file_name = load_server_data()

if df is not None:
    st.sidebar.success(f"🐒 Make by BangNC13")
    
    df.columns = [str(col).strip() for col in df.columns]
    
    # Tự động tìm các cột Tọa độ
    lat_col1 = next((c for c in df.columns if 'lat' in c.lower() and '1' in c.lower()), None)
    lon_col1 = next((c for c in df.columns if 'lng' in c.lower() or ('lon' in c.lower() and '1' in c.lower())), None)
    lat_col2 = next((c for c in df.columns if 'lat' in c.lower() and '2' in c.lower()), None)
    lon_col2 = next((c for c in df.columns if 'lng' in c.lower() or ('lon' in c.lower() and '2' in c.lower())), None)

    if not lat_col1:
        lat_col1 = next((c for c in df.columns if 'lat' in c.lower() or 'vĩ độ' in c.lower()), None)
        lon_col1 = next((c for c in df.columns if 'lng' in c.lower() or 'lon' in c.lower() or 'kinh độ' in c.lower()), None)

    # Lọc tuyến cáp theo POP
    if 'Tên đoạn cáp' in df.columns:
        df['POP'] = df['Tên đoạn cáp'].apply(lambda x: str(x).split('.')[0] if '.' in str(x) else str(x))
        pop_list = sorted(df['POP'].unique())
        selected_pop = st.sidebar.selectbox("LỌC DỮ LIỆU POP", pop_list, key="selected_pop")
        pop_df = df[df['POP'] == selected_pop].copy()
    else:
        pop_df = df.copy()

    # Dựng đồ thị kết nối & Lưu tọa độ các Node
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

        # Tính toán điểm đứt
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

    # Display Báo lỗi / Vị trí đứt ở Sidebar
    if st.session_state.break_result:
        res = st.session_state.break_result
        st.sidebar.error("📍 VỊ TRÍ ĐỨT CÁP DỰ KIẾN")
        st.sidebar.markdown(f"**Đoạn cáp:** `{res['cable']}`")
        st.sidebar.markdown(f"• Cách **{res['from']}**: `{res['d1']:.1f}m` / {res['seg_len']}m")
        st.sidebar.markdown(f"• Cách **{res['to']}**: `{res['d2']:.1f}m`")
        
        if st.session_state.break_gps:
            gps = st.session_state.break_gps
            gmap_url = f"https://www.google.com/maps?q={gps[0]},{gps[1]}"
            st.sidebar.markdown(f"📍 **GPS:** `{gps[0]:.6f}, {gps[1]:.6f}`")
            st.sidebar.markdown(f"👉 [**Mở trên Google Maps**]({gmap_url})")

    # 3. Hiển thị Bản đồ
    map_center = [21.0285, 105.8542]
    zoom_lvl = 12

    if st.session_state.break_gps:
        map_center = st.session_state.break_gps
        zoom_lvl = 17
    elif len(node_coords) > 0:
        first_coord = list(node_coords.values())[0]
        map_center = [first_coord[0], first_coord[1]]
        zoom_lvl = 15

    m = folium.Map(location=map_center, zoom_start=zoom_lvl, tiles="OpenStreetMap")

    # Nếu ĐÃ TÍNH ĐƯỢC VỊ TRÍ ĐỨT -> Chỉ vẽ tuyến bị đứt
    if st.session_state.break_result:
        u = st.session_state.break_result['from']
        v = st.session_state.break_result['to']

        if u in node_coords and v in node_coords:
            folium.PolyLine(
                locations=[node_coords[u], node_coords[v]],
                color="red",
                weight=6,
                opacity=0.9,
                tooltip=f"Sự cố đoạn: {st.session_state.break_result['cable']}"
            ).add_to(m)

            for node in [u, v]:
                folium.CircleMarker(
                    location=node_coords[node],
                    radius=7,
                    popup=f"Điểm KN: {node}",
                    tooltip=f"Điểm KN: {node}",
                    color="blue",
                    fill=True,
                    fill_color="white"
                ).add_to(m)

        if st.session_state.break_gps:
            folium.Marker(
                location=st.session_state.break_gps,
                popup=f"🚨 VỊ TRÍ ĐỨT CÁP: {st.session_state.break_result['cable']}",
                tooltip="Vị trí đứt cáp",
                icon=folium.Icon(color="red", icon="warning", prefix="fa")
            ).add_to(m)

    # Nếu CHƯA ĐO -> Hiển thị toàn bộ mạng cáp để quan sát tổng thể
    else:
        for u, v, data in G.edges(data=True):
            if u in node_coords and v in node_coords:
                folium.PolyLine(
                    locations=[node_coords[u], node_coords[v]],
                    color="#2b5c8f",
                    weight=3,
                    opacity=0.6,
                    tooltip=f"Cáp: {data.get('cable', '')}"
                ).add_to(m)

        for node_id, coord in node_coords.items():
            folium.CircleMarker(
                location=coord,
                radius=4,
                popup=f"Điểm KN: {node_id}",
                tooltip=node_id,
                color="#2b5c8f",
                fill=True,
                fill_color="white"
            ).add_to(m)

    st_folium(m, width=1100, height=650, key="folium_map")

else:
    st.error("❌ Không tìm thấy file Excel trên Server. Vui lòng kiểm tra lại tên file `Danh-Sách-Đoạn-Cáp.xlsx` trong thư mục chạy mã.")
