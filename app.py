# 2. CSS Tùy chỉnh TRÀN 100% MỌI CẠNH MÀN HÌNH (Sát mép trên cùng)
st.markdown("""
    <style>
        /* 1. Reset toàn bộ thẻ nền chính */
        html, body, [data-testid="stAppViewContainer"], .main, .stApp, [data-testid="stHeader"] {
            margin: 0 !important;
            padding: 0 !important;
            top: 0 !important;
            height: 100vh !important;
            overflow: hidden !important;
        }

        /* 2. Triệt tiêu hoàn toàn Header mặc định của Streamlit */
        header[data-testid="stHeader"], [data-testid="stHeader"] {
            display: none !important;
            height: 0px !important;
        }

        /* 3. Xóa padding trên cùng của Container chứa nội dung */
        .main .block-container, 
        [data-testid="stMainBlockContainer"],
        div[class*="stBlock-"],
        div[data-testid="stVerticalBlock"] {
            padding-top: 0rem !important;
            padding-bottom: 0rem !important;
            padding-left: 0rem !important;
            padding-right: 0rem !important;
            margin-top: 0px !important;
            margin-bottom: 0px !important;
            gap: 0rem !important;
            max-width: 100vw !important;
        }

        /* 4. Ép thẻ bọc iframe và chính iframe bản đồ nằm sát góc trên bên trái (0,0) */
        [data-testid="element-container"], .stCustomComponentV1, iframe {
            position: fixed !important;
            top: 0px !important;
            left: 0px !important;
            width: 100vw !important;
            height: 100vh !important;
            border: none !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* 5. Giữ cho Sidebar hiển thị đè lên trên bản đồ */
        section[data-testid="stSidebar"] {
            z-index: 999999 !important;
        }
    </style>
""", unsafe_allow_html=True)
