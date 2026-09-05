# 2. CSS Tùy chỉnh TRÀN MÀN HÌNH & CHUYỂN NÚT ZOOM XUỐNG DƯỚI
st.markdown("""
    <style>
        /* 1. Xóa cuộn trang chính và thụt lề nền */
        html, body, [data-testid="stAppViewContainer"], .main, .stApp {
            margin: 0 !important;
            padding: 0 !important;
            height: 100vh !important;
            overflow: hidden !important;
        }

        /* 2. Triệt tiêu nền Header nhưng GIỮ LẠI các nút hệ thống */
        header[data-testid="stHeader"] {
            background: transparent !important;
            height: 0px !important;
            z-index: 999999 !important;
        }

        /* 3. Đưa nút Mở/Ẩn Sidebar lên lớp ưu tiên cao nhất */
        [data-testid="stSidebarCollapseButton"], 
        [data-testid="collapsedControl"] {
            z-index: 1000000 !important;
            position: fixed !important;
            top: 10px !important;
            left: 10px !important;
            background-color: rgba(255, 255, 255, 0.9) !important;
            border-radius: 50% !important;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.3) !important;
            padding: 4px !important;
        }

        /* 4. Xóa khoảng trắng phía trên Container nội dung chính */
        .main .block-container, 
        [data-testid="stMainBlockContainer"],
        [data-testid="stVerticalBlock"] {
            padding: 0 !important;
            margin: 0 !important;
            gap: 0rem !important;
            max-width: 100vw !important;
        }

        /* 5. Căn bản đồ tràn 100% màn hình */
        [data-testid="element-container"], .stCustomComponentV1, iframe {
            width: 100vw !important;
            height: 100vh !important;
            border: none !important;
            margin: 0 !important;
            padding: 0 !important;
            display: block !important;
        }

        /* 6. Đảm bảo Sidebar nằm đè lên bản đồ khi mở */
        section[data-testid="stSidebar"] {
            z-index: 999999 !important;
        }

        /* 7. DI CHUYỂN CỤM NÚT ZOOM (+ / -) XUỐNG GÓC DƯỚI BÊN PHẢI MÀN HÌNH */
        .leaflet-top.leaflet-left .leaflet-control-zoom,
        .leaflet-control-zoom {
            position: fixed !important;
            bottom: 25px !important;
            right: 20px !important;
            top: auto !important;
            left: auto !important;
            z-index: 99999 !important;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.4) !important;
        }
    </style>
""", unsafe_allow_html=True)
