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

def market_status_la() -> str:
    """
    简化判断：只根据洛杉矶时间判断（不处理节假日）
    盘中：06:30–13:00
    盘后：13:00–17:00
    休市：其它
    """
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
# ✅ 最新价：fast_info（免费里尽可能接近实时）
# =========================
@st.cache_data(ttl=2, show_spinner=False)
def fetch_last_fast_batch(tickers: list[str]) -> tuple[dict, str]:
    out = {}
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
# ✅ 昨日收盘价（闭市之前的价格）：用日线 Close
# - period="5d" 更稳（防止遇到周末/节假日只有1天）
# - 取最后一个有效 Close 作为“上一交易日收盘”
# =========================
@st.cache_data(ttl=10 * 60, show_spinner=False)
def fetch_prev_close_batch(tickers: list[str]) -> tuple[dict, str]:
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

    out = {}
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
# ✅ 分时：主要用来拿 day_high（盘中高点）
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

def get_day_high_from_batch(df: pd.DataFrame, ticker: str):
    if df is None or df.empty:
        return None
    try:
        if isinstance(df.columns, pd.MultiIndex):
            sub = df[ticker].dropna()
            if sub.empty:
                return None
            return float(sub["High"].max())
        else:
            sub = df.dropna()
            if sub.empty:
                return None
            return float(sub["High"].max())
    except Exception:
        return None

# =========================
# ✅ ATH：历史最高点（All-time high）
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

# =========================
# Streamlit 基本设置
# =========================
st.set_page_config(page_title="交易纪律执行助手", layout="wide")

# =========================
# 🔥 暗黑 CSS + 状态颜色/闪烁
# =========================
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { background: rgba(0,0,0,0) !important; height: 0px !important; }
    div[data-testid="stToolbar"] { visibility: hidden !important; height: 0px !important; }
    div[data-testid="stDecoration"] { display: none !important; }

    .stApp { background-color: #0b0f14; }

    html, body, [class*="css"] { color: #f5f7fa !important; }
    h1, h2, h3, h4, h5 { color: #ffffff !important; }
    .stCaption, .stMarkdown, .stText { color: #cfd8e3 !important; }

    div[data-testid="stMetricLabel"] { color: #9fb3c8 !important; font-size: 0.85rem; }
    div[data-testid="stMetricValue"] { color: #ffffff !important; font-weight: 600; }

    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 12px;
    }

    .status-box {
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.1);
        background: rgba(255,255,255,0.04);
        color: #ffffff;
        margin-top: 10px;
    }

    section[data-testid="stSidebar"] {
        background-color: #0a0d12 !important;
        border-right: 1px solid rgba(255,255,255,0.08);
    }
    section[data-testid="stSidebar"] * { color: #f5f7fa !important; }
    section[data-testid="stSidebar"] label { color: #cfd8e3 !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12) !important; }

    @keyframes blinkGreen {
        0%   { opacity: 1; }
        50%  { opacity: 0.2; }
        100% { opacity: 1; }
    }
    .status-text { font-weight: 800; }

    .status-buy  { color: #2cff6a !important; animation: blinkGreen 1s infinite; }
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

# ✅ 双时区时间
bj_time = datetime.now(ZoneInfo("Asia/Shanghai"))
la_time = datetime.now(ZoneInfo("America/Los_Angeles"))
st.caption(
    f"当前时间：北京时间 {bj_time.strftime('%Y-%m-%d %H:%M:%S')} ｜"
    f"洛杉矶时间 {la_time.strftime('%Y-%m-%d %H:%M:%S')} ｜"
    f"市场状态：{market_status_la()}"
)

with st.sidebar:
    st.header("设置")
    refresh = st.slider("自动刷新间隔（秒）", 3, 60, 5, 1)
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

# ✅ 自动刷新
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
# ✅ 数据拉取
# =========================
last_map, last_updated_at = fetch_last_fast_batch(TICKERS)
prev_close_map, prev_updated_at = fetch_prev_close_batch(TICKERS)
intraday_df, interval_used = fetch_intraday_batch_for_high(TICKERS)
ath_map = fetch_ath_batch(TICKERS)

st.caption(
    f"最新价来源：fast_info（更新于 LA {last_updated_at}）｜"
    f"上一交易日收盘：日线 Close（更新于 LA {prev_updated_at}）｜"
    f"盘中高点分时精度：{interval_used}（自动降级防限流）"
)

cols = st.columns(len(TICKERS))

def render_ticker(col, ticker: str):
    with col:
        st.subheader(f"标的：{ticker}")

        # 上面：最新价（fast）
        last_price = last_map.get(ticker)

        # 下面：闭市之前的价格（上一交易日收盘）
        prev_close = prev_close_map.get(ticker)

        # 盘中高点（今日）
        day_high = get_day_high_from_batch(intraday_df, ticker)

        # ATH
        ath = ath_map.get(ticker)

        # 允许：休市 last_price 为 None，但 prev_close 必须有（否则没法显示）
        if prev_close is None or ath is None:
            st.warning("行情暂时不可用/被限流（缺少上一交易日收盘或ATH），稍后自动刷新")
            return

        # 用哪个价格来计算回撤？优先最新价，否则用上一收盘
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

        # 4列指标：把“闭市之前价格”做成独立指标（你要的）
        c1, c2, c3, c4 = st.columns(4)

        # ✅ 最新价（可能为空）
        if last_price is None:
            c1.metric("最新价格（fast）", "—")
        else:
            c1.metric("最新价格（fast）", fmt_price(last_price))

        # ✅ 你要的：闭市之前价格（上一交易日收盘）
        c2.metric("闭市前价格（昨收）", fmt_price(prev_close))

        # ✅ 盘中高点：休市时可能拿不到，就用 —
        c3.metric("盘中高点(今日)", fmt_price(day_high) if day_high is not None else "—")

        # ✅ 回撤：用最新价或昨收计算
        c4.metric("从历史最高点回撤", fmt_pct(drawdown))

        st.markdown(
            f"""
            <div class="status-box">
                <b>状态：</b>
                <span class="status-text {status_class}">{status_text}</span>
                <div style="margin-top:6px; opacity:0.8; font-size:0.85rem;">
                    回撤计算价格口径：{"最新价（fast）" if last_price is not None else "昨收（休市/无fast）"}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.caption("核心纪律：用明确数字对抗情绪，用纪律换取长期复利。")

for i, tk in enumerate(TICKERS):
    render_ticker(cols[i], tk)
