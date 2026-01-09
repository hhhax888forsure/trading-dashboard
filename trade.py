import streamlit as st
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

# =========================
# 你的回撤规则（可自己改）
# =========================
LEVEL_WAIT = 0.02
LEVEL_PREP = 0.03
LEVEL_GOOD = 0.035
LEVEL_BUY  = 0.045

TICKERS = ["QQQ", "SMH", "VGT"]

# =========================
# 工具函数
# =========================
def classify(drawdown: float) -> tuple[str, str]:
    if drawdown >= LEVEL_BUY:
        return "触发买入区间（≥4.5%）", "buy"
    if drawdown >= LEVEL_GOOD:
        return "适合进场（≥3.5%）", "good"
    if drawdown >= LEVEL_PREP:
        return "准备进场（≥3.0%）", "prep"
    if drawdown >= LEVEL_WAIT:
        return "等待（≥2.0%）", "wait"
    return "观望（<2.0%)", "watch"

def fmt_price(x: float) -> str:
    return f"{x:.2f}"

def fmt_pct(x: float) -> str:
    return f"{x*100:.2f}%"

# =========================
# ✅ 批量拉取分时（优先1m，更准；失败自动降级2m/5m）
# =========================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_intraday_batch(tickers: list[str]) -> tuple[pd.DataFrame, str]:
    """
    优先 1m（更准），失败则降级 2m/5m
    返回 (df, interval_used)
    """
    symbols = " ".join(tickers)
    for interval in ["1m", "2m", "5m"]:
        try:
            df = yf.download(
                tickers=symbols,
                period="1d",
                interval=interval,
                group_by="ticker",
                auto_adjust=False,
                threads=False,
                progress=False,
            )
            if df is not None and not df.empty:
                return df, interval
        except Exception:
            pass
    return pd.DataFrame(), "NA"

# =========================
# ✅ 批量拉取历史最高点（ATH）
# =========================
@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_ath_batch(tickers: list[str]) -> dict:
    symbols = " ".join(tickers)
    df = yf.download(
        tickers=symbols,
        period="max",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=False,
        progress=False,
    )

    ath_map = {}
    if df is None or df.empty:
        return ath_map

    if isinstance(df.columns, pd.MultiIndex):
        for tk in tickers:
            try:
                sub = df[tk].dropna()
                if sub.empty:
                    continue
                ath_map[tk] = float(sub["High"].max())
            except Exception:
                continue
    else:
        try:
            sub = df.dropna()
            ath_map[tickers[0]] = float(sub["High"].max())
        except Exception:
            pass

    return ath_map

def get_last_and_day_high_from_batch(df: pd.DataFrame, ticker: str):
    if df is None or df.empty:
        return None, None

    try:
        if isinstance(df.columns, pd.MultiIndex):
            sub = df[ticker].dropna()
            if sub.empty:
                return None, None
            last_price = float(sub["Close"].iloc[-1])
            day_high = float(sub["High"].max())
            return last_price, day_high
        else:
            sub = df.dropna()
            if sub.empty:
                return None, None
            last_price = float(sub["Close"].iloc[-1])
            day_high = float(sub["High"].max())
            return last_price, day_high
    except Exception:
        return None, None

# =========================
# Streamlit 基本设置
# =========================
st.set_page_config(
    page_title="交易纪律执行助手",
    layout="wide",
)

# =========================
# 🔥 终极暗黑 CSS + 状态颜色/闪烁
# =========================
st.markdown(
    """
    <style>
    /* ===== ① 干掉顶部白色 Header ===== */
    header[data-testid="stHeader"] {
        background: rgba(0,0,0,0) !important;
        height: 0px !important;
    }
    div[data-testid="stToolbar"] {
        visibility: hidden !important;
        height: 0px !important;
    }
    div[data-testid="stDecoration"] {
        display: none !important;
    }

    /* ===== ② 全局黑色背景 ===== */
    .stApp {
        background-color: #0b0f14;
    }

    /* ===== ③ 全站文字强制白色体系 ===== */
    html, body, [class*="css"] {
        color: #f5f7fa !important;
    }
    h1, h2, h3, h4, h5 {
        color: #ffffff !important;
    }
    .stCaption, .stMarkdown, .stText {
        color: #cfd8e3 !important;
    }

    /* ===== ④ 指标卡片文字 ===== */
    div[data-testid="stMetricLabel"] {
        color: #9fb3c8 !important;
        font-size: 0.85rem;
    }
    div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 600;
    }

    /* ===== ⑤ 指标卡片样式 ===== */
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 12px;
    }

    /* ===== ⑥ 状态条 ===== */
    .status-box {
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.1);
        background: rgba(255,255,255,0.04);
        color: #ffffff;
        margin-top: 10px;
    }

    /* ===== Sidebar：左侧黑底白字 ===== */
    section[data-testid="stSidebar"] {
        background-color: #0a0d12 !important;
        border-right: 1px solid rgba(255,255,255,0.08);
    }
    section[data-testid="stSidebar"] * {
        color: #f5f7fa !important;
    }
    section[data-testid="stSidebar"] label {
        color: #cfd8e3 !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.12) !important;
    }

    /* ===== ⑦ 状态颜色/闪烁 ===== */
    @keyframes blinkGreen {
        0%   { opacity: 1; }
        50%  { opacity: 0.2; }
        100% { opacity: 1; }
    }
    .status-text { font-weight: 700; }

    .status-buy {
        color: #2cff6a !important;
        animation: blinkGreen 1s infinite;
    }
    .status-wait { color: #ffd34d !important; }
    .status-good { color: #9dffb8 !important; }
    .status-prep { color: #b6c7ff !important; }
    .status-watch{ color: #cfd8e3 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# 页面内容
# =========================
st.title("交易纪律执行助手")

# ✅ 双时区时间（自动夏令时）
bj_time = datetime.now(ZoneInfo("Asia/Shanghai"))
la_time = datetime.now(ZoneInfo("America/Los_Angeles"))
st.caption(
    f"当前时间：北京时间 {bj_time.strftime('%Y-%m-%d %H:%M:%S')} ｜"
    f"洛杉矶时间 {la_time.strftime('%Y-%m-%d %H:%M:%S')}"
)

with st.sidebar:
    st.header("设置")

    # ✅ 建议别太频繁，否则再稳也可能被限流
    refresh = st.slider("自动刷新间隔（秒）", 15, 300, 60, 15)
    st.markdown(
        """
        **规则分层**
        - ≥2%：等待
        - ≥3%：准备进场
        - ≥3.5%：适合进场
        - ≥4.5%：触发买入区间

        ⚠️ 当前高点：**历史最高点（All-time high）**
        """
    )

# 自动刷新
st.markdown(
    f"""
    <script>
    setTimeout(function() {{
        window.location.reload();
    }}, {refresh * 1000});
    </script>
    """,
    unsafe_allow_html=True
)

# ✅ 这里提前批量抓数据：只打 2 次网络请求（分时一次 + ATH一次）
intraday_df, interval_used = fetch_intraday_batch(TICKERS)
ath_map = fetch_ath_batch(TICKERS)

st.caption(f"分时精度：{interval_used}（优先1m，失败自动降级防限流）")

cols = st.columns(len(TICKERS))

def render_ticker(col, ticker: str):
    with col:
        st.subheader(f"标的：{ticker}")

        last_price, day_high = get_last_and_day_high_from_batch(intraday_df, ticker)
        ath = ath_map.get(ticker)

        if last_price is None or day_high is None or ath is None:
            st.warning("行情被限流/暂时不可用（已启用缓存兜底），稍后自动刷新")
            return

        drawdown = max(0.0, (ath - last_price) / ath)
        status_text, status_kind = classify(drawdown)

        status_class = {
            "buy": "status-buy",
            "wait": "status-wait",
            "good": "status-good",
            "prep": "status-prep",
            "watch": "status-watch",
        }.get(status_kind, "status-watch")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新价格", fmt_price(last_price))
        c2.metric("盘中高点(今日)", fmt_price(day_high))
        c3.metric("历史最高点(ALL)", fmt_price(ath))
        c4.metric("从历史最高点回撤", fmt_pct(drawdown))

        st.markdown(
            f"""
            <div class="status-box">
                <b>状态：</b>
                <span class="status-text {status_class}">{status_text}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.caption("核心纪律：用明确数字对抗情绪，用纪律换取长期复利。")

for i, tk in enumerate(TICKERS):
    render_ticker(cols[i], tk)
