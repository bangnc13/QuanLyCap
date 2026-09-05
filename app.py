# 2. CSS Tùy chỉnh TRÀN HẾT TẤT CẢ CÁC CẠNH (Tường tận Trên - Dưới - Trái - Phải)
st.markdown("""
    <style>
        /* 1. Reset toàn bộ khoảng trắng của trang web */
        html, body, [data-testid="stAppViewContainer"], .main, .stApp {
            margin: 0 !important;
            padding: 0 !important;
            height: 100vh !important;
            overflow: hidden !important; /* Dập tắt hoàn toàn thanh cuộn */
        }

        /* 2. Ẩn Header & Footer mặc định của Streamlit */
        header[data-testid="stHeader"], footer {
            display: none !important;
        }

        /* 3. Ép container chính phủ kín 100% chiều cao/rộng góc nhìn */
        .main .block-container {
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100vw !important;
            height: 100vh !important;
        }

        /* 4. Khắc phục cạnh trên & cạnh dưới: Xóa gap/padding của các thẻ bọc Folium */
        [data-testid="stVerticalBlock"] {
            gap: 0rem !important;
            padding: 0 !important;
        }

        [data-testid="element-container"], .stCustomComponentV1 {
            margin: 0 !important;
            padding: 0 !important;
            height: 100vh !important;
        }

        /* 5. Ép iframe bản đồ tràn cố định full chiều cao viewport */
        iframe {
            width: 100vw !important;
            height: 100vh !important;
            border: none !important;
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
        }

        /* 6. Đảm bảo Sidebar nổi lên trên bản đồ */
        section[data-testid="stSidebar"] {
            z-index: 999999 !important;
        }
    </style>
""", unsafe_allow_html=True)
