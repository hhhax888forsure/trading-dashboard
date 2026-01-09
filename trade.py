from __future__ import annotations

import streamlit as st
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

# =========================
# 回撤规则（可自己改）
# =========================
LEVEL_WAIT = 0.02
LEVEL_PREP = 0.03
LEVEL_GOOD = 0.035
LEVEL_BUY  = 0.045

TICKERS = ["QQQ", "SMH", "VGT"]

# =========================
# Streamlit 基本设置
# =========================
st.set_page_config(page_title="交易纪律执行助手", layout="wide")

# =========================
# ✅ 终极暗黑 CSS（修复左侧白块 + 纯白字体）
# =========================
st.markdown(
    """
    <style>
    html, body {
        background-color: #0b0f14 !important;
        color: #ffffff !important;
    }
    .stApp {
        background-color: #0b0f14 !important;
        color: #ffffff !important;
    }

    /* Sidebar 全层级强制深色（彻底解决左侧白块） */
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

    /* 顶部 Header/Toolbar */
    header[data-testid="stHeader"] { background: transparent !important; height: 0px !important; }
    div[data-testid="stToolbar"] { visibility: hidden !important; height: 0px !important; }
    div[data-testid="stDecoration"] { display: none !important; }

    h1, h2, h3, h4, h5 { color: #ffffff !important; font-weight: 700; }
    p, span, div, label, li { color: #ffffff !important; }
    .stCaption { color: #dfe6ee !important; }

    /* Metric 卡片 */
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 12px;
    }
    div[data-testid="stMetricLabel"] { color: #cfd8e3 !important; font-size: 0.85rem; }
    div[data-testid="stMetricValue"] { color: #ffffff !important; font-weight: 800; }

    /* 状态条 */
    .status-box {
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.05);
        margin-top: 10px;
    }

    /* 状态颜色 + 闪烁 */
    @keyframes blinkGreen {
        0%   { opacity: 1; }
        50%  { opacity: 0.2; }
        100% { opacity: 1; }
    }
    .status-buy  { color: #2cff6a !important; font-weight: 900; animation: blinkGreen 1s infinite; }
    .status-wait { color: #ffd34d !important; font-weight: 800; }
    .status-good { color: #9dffb8 !important; font-weight: 800; }
    .status-prep { color: #b6c7ff !important; font-weight: 800; }
    .status-watch{ color: #cfd8e3 !important; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True
)

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

def market_status_la() -> str:
    la_now = datetime.now(ZoneInfo("America/Los_Angeles"))
    hhmm = la_now.hour * 60 + la_now.minute
    open_m = 6 * 60 + 30
    close_m = 13 * 60
    after_m = 17 * 60
    if open_m <= hhmm < close_m:
        return "盘中"
    if close_m <= hhmm < after_m:
        return "盘后"
    return "休市"

# =========================
# ✅ 最新价：fast_info
# =========================
@st.cache_data(ttl=2, show_spinner=False)
def fetch_last_fast_batch(tickers: list[str]) -> tuple[dict[str, float], str]:
    out: dict[str, float] = {}
    for tk in tickers:
        try:
            t = yf.Ticker(tk)
            lp = t.fast_info.get("last_price", None)
            if lp is not None:
                out[tk] = float(lp)
        except Exception:
            pass
    la_now = datetime.now(ZoneInfo("America/Los_Angeles"))
    return out, la_now.strftime("%Y-%m-%d %H:%M:%S")

# =========================
# ✅ 昨收：日线 Close
# =========================
@st.cache_data(ttl=10 * 60, show_spinner=False)
def fetch_prev_close_batch(tickers: list[str]) -> tuple[dict[str, float], str]:
    symbols = " ".join(tickers)
    try:
        df = yf.download(
            tickers=symbols,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=False,
            progress=False,
        )
    except Exception:
        return {}, "NA"

    out: dict[str, float] = {}
    if df is None or df.empty:
        return out, "NA"

    try:
        if isinstance(df.columns, pd.MultiIndex):
            for tk in tickers:
                sub = df[tk].dropna()
                if sub.empty or "Close" not in sub.columns:
                    continue
                out[tk] = float(sub["Close"].iloc[-1])
        else:
            sub = df.dropna()
            if not sub.empty and "Close" in sub.columns:
                out[tickers[0]] = float(sub["Close"].iloc[-1])
    except Exception:
        pass

    la_now = datetime.now(ZoneInfo("America/Los_Angeles"))
    return out, la_now.strftime("%Y-%m-%d %H:%M:%S")

# =========================
# ✅ 分时：盘中高点
# =========================
@st.cache_data(ttl=30, show_spinner=False)
def fetch_intraday_batch_for_high(tickers: list[str]) -> tuple[pd.DataFrame, str]:
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

def get_day_high_from_batch(df: pd.DataFrame, ticker: str) -> float | None:
    if df is None or df.empty:
        return None
    try:
        if isinstance(df.columns, pd.MultiIndex):
            sub = df[ticker].dropna()
            if sub.empty:
                return None
            return float(sub["High"].max())
        sub = df.dropna()
        if sub.empty:
            return None
        return float(sub["High"].max())
    except Exception:
        return None

# =========================
# ✅ ATH：历史最高点（ALL）
# =========================
@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_ath_batch(tickers: list[str]) -> dict[str, float]:
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

    ath_map: dict[str, float] = {}
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

# =========================
# 页面内容
# =========================
st.title("交易纪律执行助手")

bj_time = datetime.now(ZoneInfo("Asia/Shanghai"))
la_time = datetime.now(ZoneInfo("America/Los_Angeles"))
st.caption(
    f"当前时间：北京时间 {bj_time.strftime('%Y-%m-%d %H:%M:%S')} ｜"
    f"洛杉矶时间 {la_time.strftime('%Y-%m-%d %H:%M:%S')} ｜"
    f"市场状态：{market_status_la()}"
)

with st.sidebar:
    st.header("设置")
    refresh = st.slider("自动刷新间隔（秒）", 3, 120, 10, 1)
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

# 拉数据
last_map, last_updated_at = fetch_last_fast_batch(TICKERS)
prev_close_map, prev_updated_at = fetch_prev_close_batch(TICKERS)
intraday_df, interval_used = fetch_intraday_batch_for_high(TICKERS)
ath_map = fetch_ath_batch(TICKERS)

st.caption(
    f"最新价：fast_info（LA {last_updated_at}）｜"
    f"昨收：日线 Close（LA {prev_updated_at}）｜"
    f"盘中高点：{interval_used} 分时（自动降级防限流）"
)

cols = st.columns(len(TICKERS))

def render_ticker(col, ticker: str):
    with col:
        st.subheader(f"标的：{ticker}")

        last_price = last_map.get(ticker)
        prev_close = prev_close_map.get(ticker)
        day_high = get_day_high_from_batch(intraday_df, ticker)
        ath = ath_map.get(ticker)

        if prev_close is None or ath is None:
            st.warning("行情暂时不可用（缺少昨收或ATH），稍后自动刷新")
            return

        # 回撤计算：优先最新价，否则昨收（休市/无fast时）
        price_for_dd = last_price if last_price is not None else prev_close
        drawdown = max(0.0, (ath - price_for_dd) / ath)
        status_text, status_kind = classify(drawdown)

        status_class = {
            "buy": "status-buy",
            "wait": "status-wait",
            "good": "status-good",
            "prep": "status-prep",
            "watch": "status-watch",
        }.get(status_kind, "status-watch")

        # ✅ 两行布局：3 + 2（数字不会挤）
        r1a, r1b, r1c = st.columns(3)
        r2a, r2b = st.columns(2)

        r1a.metric("最新价格（fast）", fmt_price(last_price) if last_price is not None else "—")
        r1b.metric("闭市前价格（昨收）", fmt_price(prev_close))
        r1c.metric("盘中高点(今日)", fmt_price(day_high) if day_high is not None else "—")

        r2a.metric("历史最高点(ALL)", fmt_price(ath))
        r2b.metric("从历史最高点回撤", fmt_pct(drawdown))

        st.markdown(
            f"""
            <div class="status-box">
                <b>状态：</b> <span class="{status_class}">{status_text}</span>
                <div style="margin-top:6px; opacity:0.85; font-size:0.85rem;">
                    回撤计算口径：{"最新价（fast）" if last_price is not None else "昨收（休市/无fast）"}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.caption("核心纪律：用明确数字对抗情绪，用纪律换取长期复利。")

for i, tk in enumerate(TICKERS):
    render_ticker(cols[i], tk)
