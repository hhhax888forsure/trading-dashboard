st.markdown(
    """
    <style>
    /* =================================================
       0. 页面 & 根节点兜底（防任何白边）
       ================================================= */
    html, body {
        background-color: #0b0f14 !important;
        color: #ffffff !important;
    }

    /* =================================================
       1. 主应用背景
       ================================================= */
    .stApp {
        background-color: #0b0f14 !important;
        color: #ffffff !important;
    }

    /* =================================================
       2. Sidebar（所有层级，彻底解决左侧白块）
       ================================================= */
    section[data-testid="stSidebar"],
    div[data-testid="stSidebar"],
    [data-testid="stSidebar"] > div {
        background-color: #0a0d12 !important;
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    /* =================================================
       3. 顶部 Header / Toolbar 清理
       ================================================= */
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0px !important;
    }

    div[data-testid="stToolbar"] {
        visibility: hidden !important;
        height: 0px !important;
    }

    div[data-testid="stDecoration"] {
        display: none !important;
    }

    /* =================================================
       4. 全站文字：恢复“最早版本”的纯白
       ================================================= */
    h1, h2, h3, h4, h5 {
        color: #ffffff !important;
        font-weight: 700;
    }

    p, span, div, label, li {
        color: #ffffff !important;
    }

    .stCaption {
        color: #dfe6ee !important;
    }

    /* =================================================
       5. Metric 卡片（和你最初版本一致）
       ================================================= */
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 12px;
    }

    div[data-testid="stMetricLabel"] {
        color: #cfd8e3 !important;
        font-size: 0.85rem;
    }

    div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 700;
    }

    /* =================================================
       6. 状态条容器
       ================================================= */
    .status-box {
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.05);
        margin-top: 10px;
    }

    /* =================================================
       7. 状态颜色 + 闪烁（保持你现在逻辑）
       ================================================= */
    @keyframes blinkGreen {
        0%   { opacity: 1; }
        50%  { opacity: 0.2; }
        100% { opacity: 1; }
    }

    .status-buy {
        color: #2cff6a !important;
        font-weight: 800;
        animation: blinkGreen 1s infinite;
    }

    .status-wait {
        color: #ffd34d !important;
        font-weight: 700;
    }

    .status-good {
        color: #9dffb8 !important;
        font-weight: 700;
    }

    .status-prep {
        color: #b6c7ff !important;
        font-weight: 700;
    }

    .status-watch {
        color: #cfd8e3 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)
