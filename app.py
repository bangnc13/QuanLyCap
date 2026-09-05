# Thay thế đoạn st.markdown CSS & HTML tiêu đề cũ bằng đoạn này:

st.markdown("""
    <style>
        html, body, [data-testid="stAppViewContainer"], .main, .stApp {
            margin: 0 !important;
            padding: 0 !important;
            height: 100vh !important;
            overflow: hidden !important;
        }

        /* Tùy chỉnh thanh Header Streamlit */
        header[data-testid="stHeader"] {
            background-color: #ffffff !important;
            height: 2.8rem !important;
            z-index: 9999999 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: flex-start !important;
            padding-left: 0.5rem !important;
            border-bottom: 1px solid #E5E7EB;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }

        /* Đảm bảo nút toggle sidebar và tiêu đề xếp hàng ngang đẹp mắt */
        header[data-testid="stHeader"] > div {
            display: flex !important;
            align-items: center !important;
        }

        /* Định dạng badge tiêu đề nằm sát trái trong header */
        .top-left-title {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #F3F4F6;
            padding: 3px 10px;
            border-radius: 6px;
            border: 1px solid #E5E7EB;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin-left: 0.5rem;
            pointer-events: auto;
        }
        
        .top-left-title .main-text {
            font-size: 0.85rem;
            font-weight: 800;
            color: #1E3A8A;
            white-space: nowrap;
        }
        
        .top-left-title .sub-text {
            font-size: 0.75rem;
            color: #4B5563;
            font-weight: 500;
            white-space: nowrap;
        }

        section[data-testid="stSidebar"] {
            z-index: 999999 !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
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

# Đặt tiêu đề cố định ở góc trên bên trái
st.markdown("""
    <div class="top-left-title">
        <span class="main-text">⚡ TQG-XÁC ĐỊNH VỊ TRÍ ĐỨT CÁP</span>
        <span class="sub-text">| FPT Telecom</span>
    </div>
""", unsafe_allow_html=True)
