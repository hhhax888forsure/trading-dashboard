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

# ✅ 增加 IYW 作为观察ETF
TICKERS = ["QQQ", "SMH", "VGT", "IYW"]

# =========================
# Streamlit 基本设置
# =========================
st.set_page_config(page_title="交易纪律执行助手", layout="wide")

# =========================
# 暗黑 CSS（修复左侧白块 + 纯白字体）
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

    header[data-testid="stHeader"] { background: transparent !important; height: 0px !important; }
    div[data-testid="stToolbar"] { visibility: hidden !important; height: 0px !important; }
    div[data-testid="stDecoration"] { display: none !important; }

    h1, h2, h3, h4, h5 { color: #ffffff !important; font-weight: 700; }
    p, span, div, label, li { color: #ffffff !important; }
    .stCaption { color: #dfe6ee !important; }

    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 12px;
    }
    div[data-testid="stMetricLabel"] { color: #cfd8e3 !important; font-size: 0.85rem; }
    div[data-testid="stMetricValue"] { color: #ffffff !important; font-weight: 800; }

    .status-box {
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.05);
        margin-top: 10px;
    }

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

    /* 小提示条（用于“缺失/降级”提示） */
    .note-box {
        padding: 10px 12px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.10);
        background: rgba(255,255,255,0.03);
        margin-top: 10px;
        opacity: 0.95;
        font-size: 0.90rem;
    }
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

def fmt_price(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:.2f}"

def fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
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

def now_la_str() -> str:
    return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S")

# =========================
# ✅ 最新价：fast_info（逐个 ticker）
# =========================
@st.cache_data(ttl=2, show_spinner=False)
def fetch_last_fast_one(tk: str) -> float | None:
    try:
        t = yf.Ticker(tk)
        lp = t.fast_info.get("last_price", None)
        if lp is None:
            return None
        return float(lp)
    except Exception:
        return None

@st.cache_data(ttl=2, show_spinner=False)
def fetch_last_fast_map(tickers: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for tk in tickers:
        v = fetch_last_fast_one(tk)
        if v is not None:
            out[tk] = v
    return out

# =========================
# ✅ 昨收：日线 Close（逐个 ticker，更稳）
# =========================
@st.cache_data(ttl=10 * 60, show_spinner=False)
def fetch_prev_close_one(tk: str) -> float | None:
    try:
        df = yf.download(
            tickers=tk,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if df is None or df.empty or "Close" not in df.columns:
            return None
        s = df["Close"].dropna()
        if s.empty:
            return None
        return float(s.iloc[-1])
    except Exception:
        return None

@st.cache_data(ttl=10 * 60, show_spinner=False)
def fetch_prev_close_map(tickers: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for tk in tickers:
        v = fetch_prev_close_one(tk)
        if v is not None:
            out[tk] = v
    return out

# =========================
# ✅ 分时：盘中高点（今日）批量（可降级）
#    同时也用它来兜底“最新价”（取 Close 最后一笔）
# =========================
@st.cache_data(ttl=30, show_spinner=False)
def fetch_intraday_batch(tickers: list[str]) -> tuple[pd.DataFrame, str]:
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
            if sub.empty or "High" not in sub.columns:
                return None
            return float(sub["High"].max())
        sub = df.dropna()
        if sub.empty or "High" not in sub.columns:
            return None
        return float(sub["High"].max())
    except Exception:
        return None

def get_last_close_from_batch(df: pd.DataFrame, ticker: str) -> float | None:
    """从分时批量数据里取该 ticker 的 Close 最后一笔（兜底最新价）"""
    if df is None or df.empty:
        return None
    try:
        if isinstance(df.columns, pd.MultiIndex):
            sub = df[ticker].dropna()
            if sub.empty or "Close" not in sub.columns:
                return None
            return float(sub["Close"].dropna().iloc[-1])
        sub = df.dropna()
        if sub.empty or "Close" not in sub.columns:
            return None
        return float(sub["Close"].dropna().iloc[-1])
    except Exception:
        return None

# =========================
# ✅ ATH：用“复权后的 OHLC”计算（auto_adjust=True）——逐个 ticker 更稳
# =========================
@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_ath_adjusted_one(tk: str) -> float | None:
    try:
        df = yf.download(
            tickers=tk,
            period="max",
            interval="1d",
            auto_adjust=True,   # ✅ 复权 OHLC
            progress=False,
            threads=False,
        )
        if df is None or df.empty or "High" not in df.columns:
            return None
        s = df["High"].dropna()
        if s.empty:
            return None
        return float(s.max())
    except Exception:
        return None

@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_ath_adjusted_map(tickers: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for tk in tickers:
        v = fetch_ath_adjusted_one(tk)
        if v is not None:
            out[tk] = v
    return out

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

        ⚠️ ATH口径：**复权后的历史最高点（更符合“当前尺度”）**
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

# =========================
# 拉数据（更稳：昨收/ATH逐个 ticker；分时批量同时兜底最新价）
# =========================
last_fast_map = fetch_last_fast_map(TICKERS)
prev_close_map = fetch_prev_close_map(TICKERS)
intraday_df, interval_used = fetch_intraday_batch(TICKERS)
ath_map = fetch_ath_adjusted_map(TICKERS)

st.caption(
    f"最新价：fast_info（有时休市会缺失，会自动用分时Close/昨收兜底）｜"
    f"昨收：日线 Close（LA {now_la_str()}）｜"
    f"盘中高点/兜底最新价：{interval_used} 分时（自动降级防限流）｜"
    f"ATH：复权High最大值（auto_adjust=True）"
)

cols = st.columns(len(TICKERS))

def render_ticker(col, ticker: str):
    with col:
        st.subheader(f"标的：{ticker}")

        last_fast = last_fast_map.get(ticker)
        prev_close = prev_close_map.get(ticker)
        day_high = get_day_high_from_batch(intraday_df, ticker)
        last_from_bar = get_last_close_from_batch(intraday_df, ticker)
        ath = ath_map.get(ticker)

        # ✅ 选择“最新价”显示：fast -> 分时Close最后一笔 -> 昨收
        last_price: float | None = None
        source = "缺失"
        if last_fast is not None:
            last_price = last_fast
            source = "fast"
        elif last_from_bar is not None:
            last_price = last_from_bar
            source = f"{interval_used}分时Close"
        elif prev_close is not None:
            last_price = prev_close
            source = "昨收"

        # ✅ 允许“部分缺失”，不整块废掉
        missing_msgs = []
        if prev_close is None:
            missing_msgs.append("昨收缺失")
        if ath is None:
            missing_msgs.append("复权ATH缺失（可能是限流/暂时拉不到历史数据）")
        if last_price is None:
            missing_msgs.append("最新价缺失（fast/分时/昨收都没拿到）")

        # 回撤需要 ATH + 价格（优先最新价）
        drawdown: float | None = None
        status_text, status_kind = "观望（数据不足）", "watch"

        if ath is not None and last_price is not None:
            drawdown = max(0.0, (ath - last_price) / ath)
            status_text, status_kind = classify(drawdown)

        status_class = {
            "buy": "status-buy",
            "wait": "status-wait",
            "good": "status-good",
            "prep": "status-prep",
            "watch": "status-watch",
        }.get(status_kind, "status-watch")

        # 两行布局：3 + 2（数字不挤）
        r1a, r1b, r1c = st.columns(3)
        r2a, r2b = st.columns(2)

        r1a.metric(f"最新价格（{source}）", fmt_price(last_price))
        r1b.metric("闭市前价格（昨收）", fmt_price(prev_close))
        r1c.metric("盘中高点(今日)", fmt_price(day_high))

        r2a.metric("历史最高点（复权ATH）", fmt_price(ath))
        r2b.metric("从历史最高点回撤", fmt_pct(drawdown))

        st.markdown(
            f"""
            <div class="status-box">
                <b>状态：</b> <span class="{status_class}">{status_text}</span>
                <div style="margin-top:6px; opacity:0.85; font-size:0.85rem;">
                    最新价口径：{source} ｜ ATH口径：{"复权" if ath is not None else "缺失"}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if missing_msgs:
            st.markdown(
                f"""
                <div class="note-box">
                    ⚠️ {ticker} 数据不完整：{ "；".join(missing_msgs) }。<br/>
                    建议：稍等自动刷新；或把自动刷新调到 15~30 秒；或减少同时监控的标的数量。
                </div>
                """,
                unsafe_allow_html=True
            )

        st.caption("核心纪律：用明确数字对抗情绪，用纪律换取长期复利。")

for i, tk in enumerate(TICKERS):
    render_ticker(cols[i], tk)
