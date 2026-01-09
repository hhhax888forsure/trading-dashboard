import streamlit as st
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

# =========================
# 参数设置
# =========================
LEVEL_WAIT = 0.02
LEVEL_PREP = 0.03
LEVEL_GOOD = 0.035
LEVEL_BUY  = 0.045

TICKERS = ["QQQ", "SMH", "VGT"]

# =========================
# 工具函数
# =========================
def classify(drawdown: float):
    if drawdown >= LEVEL_BUY:
        return "触发买入区间（≥4.5%）", "buy"
    if drawdown >= LEVEL_GOOD:
        return "适合进场（≥3.5%）", "good"
    if drawdown >= LEVEL_PREP:
        return "准备进场（≥3.0%）", "prep"
    if drawdown >= LEVEL_WAIT:
        return "等待（≥2.0%）", "wait"
    return "观望（<2.0%)", "watch"

def fmt_price(x):
    return f"{x:.2f}"

def fmt_pct(x):
    return f"{x*100:.2f}%"

def market_status_la():
    la = datetime.now(ZoneInfo("America/Los_Angeles"))
    m = la.hour * 60 + la.minute
    if 390 <= m < 780:
        return "盘中"
    if 780 <= m < 1020:
        return "盘后"
    return "休市"

# =========================
# 数据获取
# =========================
@st.cache_data(ttl=2)
def fetch_last_fast(tickers):
    out = {}
    for tk in tickers:
        try:
            v = yf.Ticker(tk).fast_info.get("last_price")
            if v is not None:
                out[tk] = float(v)
        except:
            pass
    return out

@st.cache_data(ttl=600)
def fetch_prev_close(tickers):
    df = yf.download(" ".join(tickers), period="5d", interval="1d", group_by="ticker", progress=False)
    out = {}
    if isinstance(df.columns, pd.MultiIndex):
        for tk in tickers:
            try:
                out[tk] = float(df[tk]["Close"].dropna().iloc[-1])
            except:
                pass
    return out

@st.cache_data(ttl=30)
def fetch_intraday_high(tickers):
    for interval in ["1m", "2m", "5m"]:
        try:
            df = yf.download(" ".join(tickers), period="1d", interval=interval, group_by="ticker", progress=False)
            if not df.empty:
                return df, interval
        except:
            pass
    return pd.DataFrame(), "NA"

@st.cache_data(ttl=21600)
def fetch_ath(tickers):
    df = yf.download(" ".join(tickers), period="max", interval="1d", group_by="ticker", progress=False)
    out = {}
    if isinstance(df.columns, pd.MultiIndex):
        for tk in tickers:
            try:
                out[tk] = float(df[tk]["High"].max())
            except:
                pass
    return out

def get_day_high(df, tk):
    try:
        return float(df[tk]["High"].max())
    except:
        return None

# =========================
# 页面配置
# =========================
st.set_page_config("交易纪律执行助手", layout="wide")

st.markdown("""
<style>
.stApp { background:#0b0f14; color:#fff }
div[data-testid="stMetric"]{background:rgba(255,255,255,0.04);border-radius:10px;padding:12px}
.status-buy{color:#2cff6a;animation:blink 1s infinite}
.status-wait{color:#ffd34d}
@keyframes blink{50%{opacity:.3}}
</style>
""", unsafe_allow_html=True)

# =========================
# 标题 & 时间
# =========================
st.title("交易纪律执行助手")

bj = datetime.now(ZoneInfo("Asia/Shanghai"))
la = datetime.now(ZoneInfo("America/Los_Angeles"))

st.caption(
    f"当前时间：北京时间 {bj:%Y-%m-%d %H:%M:%S} ｜ "
    f"洛杉矶时间 {la:%Y-%m-%d %H:%M:%S} ｜ "
    f"市场状态：{market_status_la()}"
)

# =========================
# 刷新
# =========================
with st.sidebar:
    refresh = st.slider("自动刷新（秒）", 3, 60, 5, 1)

st.markdown(f"""
<script>
setTimeout(()=>location.reload(), {refresh*1000});
</script>
""", unsafe_allow_html=True)

# =========================
# 拉数据
# =========================
last_map = fetch_last_fast(TICKERS)
prev_map = fetch_prev_close(TICKERS)
intra_df, intra_iv = fetch_intraday_high(TICKERS)
ath_map = fetch_ath(TICKERS)

cols = st.columns(len(TICKERS))

# =========================
# 渲染
# =========================
for i, tk in enumerate(TICKERS):
    with cols[i]:
        st.subheader(f"标的：{tk}")

        last = last_map.get(tk)
        prev = prev_map.get(tk)
        high = get_day_high(intra_df, tk)
        ath  = ath_map.get(tk)

        if prev is None or ath is None:
            st.warning("数据暂不可用")
            continue

        price_for_dd = last if last is not None else prev
        dd = max(0, (ath - price_for_dd) / ath)
        status_text, status_kind = classify(dd)

        c1,c2,c3,c4,c5 = st.columns(5)

        c1.metric("最新价格（fast）", fmt_price(last) if last else "—")
        c2.metric("闭市前价格（昨收）", fmt_price(prev))
        c3.metric("盘中高点(今日)", fmt_price(high) if high else "—")
        c4.metric("历史最高点(ALL)", fmt_price(ath))
        c5.metric("从历史最高点回撤", fmt_pct(dd))

        st.markdown(
            f"<b>状态：</b> <span class='status-{status_kind}'>{status_text}</span>",
            unsafe_allow_html=True
        )
