import streamlit as st
import anthropic
import base64, json, math, re, io
from PIL import Image

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

try:
    from streamlit_local_storage import LocalStorage
    HAS_LS = True
except ImportError:
    HAS_LS = False

st.set_page_config(page_title="Options Pro", page_icon="📈", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', -apple-system, sans-serif !important; }
.stApp { background: #0A0A0A; color: #F0F0F0; }
.main .block-container { padding: 0 16px 80px; max-width: 430px; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.stTabs [data-baseweb="tab-list"] { background:#141414;border-radius:100px;padding:3px;gap:0;border:none;margin-bottom:20px; }
.stTabs [data-baseweb="tab"] { background:transparent!important;border-radius:100px;color:#666;font-size:13px;font-weight:600;padding:8px 16px;border:none!important; }
.stTabs [aria-selected="true"] { background:#F0F0F0!important;color:#000!important;border-radius:100px; }
.stTabs [data-baseweb="tab-highlight"],[data-baseweb="tab-border"] { display:none; }
.stTextInput>div>div,.stNumberInput>div>div>div { background:#141414!important;border:none!important;border-radius:12px!important; }
.stTextInput input,.stNumberInput input { background:#141414!important;border:none!important;border-radius:12px!important;color:#F0F0F0!important;font-size:16px!important;font-weight:500!important;padding:14px 16px!important;caret-color:#22C55E; }
.stTextInput input:focus,.stNumberInput input:focus { outline:none!important;box-shadow:0 0 0 2px #22C55E!important; }
.stTextInput label,.stNumberInput label { color:#555!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }
.stButton>button { background:#22C55E!important;color:#000!important;border:none!important;border-radius:100px!important;font-size:15px!important;font-weight:700!important;padding:14px 24px!important;width:100%!important;letter-spacing:-0.2px; }
.stButton>button:hover { background:#16A34A!important; }
[data-testid="stMetric"] { background:#141414;border:none;border-radius:14px;padding:14px; }
[data-testid="stMetricLabel"] { font-size:10px!important;color:#555!important;font-weight:700!important;text-transform:uppercase;letter-spacing:0.8px; }
[data-testid="stMetricValue"] { font-size:18px!important;font-weight:700!important;color:#F0F0F0!important;letter-spacing:-0.3px; }
[data-testid="stMetricDelta"] { display:none; }
[data-testid="stFileUploader"] { background:#141414;border:1.5px dashed #333;border-radius:14px;padding:8px; }
[data-testid="stExpander"] { background:#141414!important;border:none!important;border-radius:14px!important;margin-bottom:8px;overflow:hidden; }
[data-testid="stExpander"] summary { background:#141414!important;border-radius:14px!important;color:#F0F0F0!important;font-weight:600!important;padding:14px!important;font-size:13px!important; }
[data-testid="stExpander"]>div>div { background:#0F0F0F!important;border-top:1px solid #222!important; }
.stRadio>label { color:#555!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }
[data-testid="stRadio"]>div { background:#141414;border-radius:100px;padding:3px;display:flex;gap:0; }
[data-testid="stRadio"] label { background:transparent!important;border-radius:100px!important;padding:8px 14px!important;color:#666!important;font-size:12px!important;font-weight:600!important;flex:1;text-align:center;cursor:pointer; }
[data-testid="stRadio"] label:has(input:checked) { background:#F0F0F0!important;color:#000!important; }
.stSuccess { background:#0D1F14!important;border:1px solid #22C55E!important;border-radius:12px!important;color:#22C55E!important; }
.stError { background:#1F0D0D!important;border:1px solid #EF4444!important;border-radius:12px!important;color:#EF4444!important; }
.stInfo { background:#0D1421!important;border:1px solid #3B82F6!important;border-radius:12px!important;color:#3B82F6!important; }
hr { border-color:#1A1A1A!important;margin:18px 0!important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding:24px 0 18px;text-align:center;border-bottom:1px solid #1A1A1A;margin:0 -16px 20px">
  <div style="font-size:11px;color:#444;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">OPTIONS</div>
  <div style="font-size:26px;font-weight:900;letter-spacing:-1px">Strategy Pro</div>
</div>
""", unsafe_allow_html=True)

api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── Helpers ───────────────────────────────────────────
def get_step(s): return 1 if s < 20 else 2.5 if s <= 50 else 5

def spread_pnl(t, p, bs, ss, nc, ml):
    sp = abs(bs-ss); mp = (sp-nc)*100
    if t=="bull":
        if p<=bs: return -ml
        if p>=ss: return mp
        return ((p-bs)-nc)*100
    else:
        if p>=bs: return -ml
        if p<=ss: return mp
        return ((bs-p)-nc)*100

def call_pnl(p, k, pr): return -pr*100 if p<=k else (p-k-pr)*100

def fmt(v):  # prices - always 2 decimals
    if v is None: return "N/A"
    if not isinstance(v,(int,float)): return str(v)
    return f"{v:.2f}"

def fmtm(v):  # money - no decimal if whole
    if v is None: return "N/A"
    if not isinstance(v,(int,float)): return str(v)
    return f"{v:.0f}" if float(v).is_integer() else f"{v:.2f}"

def stars(n):
    n = int(n) if n else 3
    return "".join("★" if i<n else "☆" for i in range(5))

@st.cache_data(ttl=120)
def get_price(symbol):
    if not HAS_YF or not symbol: return None
    try:
        t = yf.Ticker(symbol)
        info = t.fast_info
        price = info.get("lastPrice") or info.get("last_price")
        if price: return round(float(price), 2)
        hist = t.history(period="1d")
        if not hist.empty: return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        return None
    return None

@st.cache_data(ttl=300)
def get_stock_info(symbol):
    """Return dict: price, target, next_er, last_er"""
    if not HAS_YF or not symbol: return None
    out = {"price": None, "target": None, "next_er": None, "last_er": None}
    try:
        t = yf.Ticker(symbol)
        # price
        try:
            fi = t.fast_info
            out["price"] = round(float(fi.get("lastPrice") or fi.get("last_price")), 2)
        except Exception:
            pass
        if not out["price"]:
            h = t.history(period="1d")
            if not h.empty: out["price"] = round(float(h["Close"].iloc[-1]), 2)
        # target + earnings from info
        try:
            info = t.info
            tp = info.get("targetMeanPrice")
            if tp: out["target"] = round(float(tp), 2)
        except Exception:
            info = {}
        # earnings dates
        try:
            cal = t.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed:
                    if isinstance(ed, list) and ed: out["next_er"] = str(ed[0])
                    else: out["next_er"] = str(ed)
        except Exception:
            pass
        try:
            edf = t.earnings_dates
            if edf is not None and not edf.empty:
                import pandas as pd
                now = pd.Timestamp.now(tz=edf.index.tz)
                future = edf[edf.index > now]
                past = edf[edf.index <= now]
                if not future.empty and not out["next_er"]:
                    out["next_er"] = future.index[-1].strftime("%Y-%m-%d")
                if not past.empty:
                    out["last_er"] = past.index[0].strftime("%Y-%m-%d")
        except Exception:
            pass
    except Exception:
        return out
    return out

def stock_info_card(symbol):
    info = get_stock_info(symbol)
    if not info or not info.get("price"):
        st.markdown(f'<div style="background:#141414;border-radius:14px;padding:16px;text-align:center;color:#555;font-size:13px;margin-bottom:14px">查無 {symbol} 資料</div>', unsafe_allow_html=True)
        return info
    price = info["price"]; target = info.get("target"); ner = info.get("next_er"); ler = info.get("last_er")
    upside = ((target-price)/price*100) if target else None
    target_html = ""
    if target:
        uc = "#22C55E" if upside>=0 else "#EF4444"
        target_html = f'''<div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 12px">
          <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">分析師目標價</div>
          <div style="display:flex;align-items:baseline;gap:6px"><span style="font-size:17px;font-weight:700;color:#F0F0F0">${target:.2f}</span>
          <span style="font-size:12px;font-weight:700;color:{uc}">{"+" if upside>=0 else ""}{upside:.1f}%</span></div></div>'''
    er_html = f'''<div style="display:flex;gap:8px">
      <div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 12px">
        <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">下次財報</div>
        <div style="font-size:14px;font-weight:700;color:#F59E0B">{ner or "—"}</div></div>
      <div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 12px">
        <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">上次財報</div>
        <div style="font-size:14px;font-weight:700;color:#888">{ler or "—"}</div></div></div>'''
    st.markdown(f'''
    <div style="background:#141414;border-radius:16px;padding:16px;margin-bottom:14px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
        <div><div style="font-size:22px;font-weight:900;letter-spacing:-0.8px">{symbol}</div>
        <div style="font-size:11px;color:#555;margin-top:1px">即時連線</div></div>
        <div style="text-align:right"><div style="font-size:26px;font-weight:900;letter-spacing:-1px">${price:.2f}</div>
        <div style="font-size:10px;color:#555;font-weight:600">現價</div></div>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:8px">{target_html}</div>
      {er_html}
    </div>''', unsafe_allow_html=True)
    return info

def compress_image(uf):
    img = Image.open(uf)
    if img.width > 1200:
        img = img.resize((1200, int(img.height*1200/img.width)), Image.LANCZOS)
    if img.mode != "RGB": img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=75); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

def show_ladder(t, bs, ss, nc, ml, be, spread=0, strike=0, premium=0):
    step = get_step(premium*5) if t=="call" else get_step(spread)
    lower = strike if t=="call" else (bs if t=="bull" else ss)
    upper = (strike+premium*6) if t=="call" else (ss if t=="bull" else bs)
    start = math.floor((lower-step*3)/step)*step
    end = math.ceil((upper+step*3)/step)*step
    rows = []
    p = start
    while p <= end+0.001:
        v = call_pnl(p,strike,premium) if t=="call" else spread_pnl(t,p,bs,ss,nc,ml)
        ret = v/abs(ml)*100 if ml else 0
        near = abs(p-be)<=step*0.55
        ismax = (t=="bull" and p>=ss) or (t=="bear" and p<=ss)
        tag = '<span style="font-size:8px;background:#1A1000;color:#F59E0B;padding:1px 5px;border-radius:100px;margin-left:4px;font-weight:700">平衡</span>' if near else ('<span style="font-size:8px;background:#0D1F14;color:#22C55E;padding:1px 5px;border-radius:100px;margin-left:4px;font-weight:700">MAX</span>' if ismax else "")
        col = "#22C55E" if v>0 else "#EF4444" if v<0 else "#F59E0B"
        bg = "rgba(34,197,94,0.04)" if v>1 else "rgba(239,68,68,0.04)" if v<-1 else "rgba(245,158,11,0.06)"
        s1="+" if v>=0 else ""; s2="+" if ret>=0 else ""
        rows.append(f'<tr style="background:{bg}"><td style="font-size:12px;padding:7px 10px;color:#F0F0F0;font-weight:500;border-bottom:1px solid #1A1A1A">${p:.2f}{tag}</td><td style="font-size:12px;padding:7px 10px;color:{col};text-align:right;border-bottom:1px solid #1A1A1A">{s1}${fmtm(v)}</td><td style="font-size:12px;padding:7px 10px;color:{col};text-align:right;font-weight:600;border-bottom:1px solid #1A1A1A">{s2}{ret:.0f}%</td></tr>')
        p = round(p+step, 3)
    st.markdown(f"""
    <div style="background:#1C1C1C;border-radius:12px;overflow:hidden;margin-top:10px">
      <div style="padding:8px 12px;display:flex;justify-content:space-between;border-bottom:1px solid #2A2A2A">
        <span style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px">損益對照</span>
        <span style="font-size:9px;color:#555;background:#242424;padding:1px 8px;border-radius:100px">每${fmtm(step)}</span>
      </div>
      <table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="font-size:9px;color:#555;padding:6px 10px;text-align:left;border-bottom:1px solid #2A2A2A;font-weight:700;text-transform:uppercase">股價</th>
          <th style="font-size:9px;color:#555;padding:6px 10px;text-align:right;border-bottom:1px solid #2A2A2A;font-weight:700;text-transform:uppercase">損益</th>
          <th style="font-size:9px;color:#555;padding:6px 10px;text-align:right;border-bottom:1px solid #2A2A2A;font-weight:700;text-transform:uppercase">報酬率</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>""", unsafe_allow_html=True)

def show_calc_results(t, max_p, max_l, be, nc, bs=0, ss=0, spread=0, strike=0, premium=0):
    ror = (max_p/max_l*100) if max_l and max_p else 0
    rr = (max_p/max_l) if max_l and max_p else 0
    move = f"+{((be-bs)/bs*100):.1f}%" if t=="bull" else f"-{((bs-be)/bs*100):.1f}%" if t=="bear" else f"+{((be-strike)/strike*100):.1f}%"
    st.markdown(f"""
    <div style="background:#141414;border-radius:16px;padding:16px 18px;margin-bottom:10px;text-align:center">
      <div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">投資報酬率</div>
      <div style="font-size:38px;font-weight:900;color:{'#22C55E' if ror>0 else '#EF4444'};letter-spacing:-1.5px">{ror:.0f}%</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:6px">
      <div style="background:#141414;border-radius:12px;padding:12px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">最大獲利</div>
        <div style="font-size:16px;font-weight:700;color:#22C55E">+${fmtm(max_p)}</div></div>
      <div style="background:#141414;border-radius:12px;padding:12px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">最大虧損</div>
        <div style="font-size:16px;font-weight:700;color:#EF4444">-${fmtm(max_l)}</div></div>
      <div style="background:#141414;border-radius:12px;padding:12px;text-align:center">
        <div style="font-size:9px;color:#F59E0B;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">損益平衡</div>
        <div style="font-size:16px;font-weight:700;color:#F59E0B">${fmt(be)}</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:14px">
      <div style="background:#141414;border-radius:12px;padding:12px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">盈虧比</div>
        <div style="font-size:16px;font-weight:700;color:#F0F0F0">{rr:.2f}x</div></div>
      <div style="background:#141414;border-radius:12px;padding:12px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">需漲跌</div>
        <div style="font-size:16px;font-weight:700;color:#F0F0F0">{move}</div></div>
    </div>
    """, unsafe_allow_html=True)
    show_ladder(t, bs, ss, nc, max_l, be, spread, strike, premium)

# ── Tabs ──────────────────────────────────────────────
# Init local storage for favorites
if HAS_LS:
    try:
        ls = LocalStorage()
    except Exception:
        ls = None
else:
    ls = None

def load_favs():
    if ls:
        try:
            raw = ls.getItem("opt_favs")
            return json.loads(raw) if raw else []
        except Exception:
            return []
    return st.session_state.get("_favs", [])

def save_favs(favs):
    if ls:
        try:
            ls.setItem("opt_favs", json.dumps(favs))
        except Exception:
            pass
    st.session_state["_favs"] = favs

def add_fav(combo):
    favs = load_favs()
    combo["_id"] = f"{combo.get('ticker','')}_{combo.get('type','')}_{combo.get('buyStrike',combo.get('strike',0))}_{len(favs)}"
    favs.insert(0, combo)
    save_favs(favs)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["計算", "比較", "AI 掃描", "我的組合", "說明"])

# ══════ TAB 1: CALC ══════
with tab1:
    cc1, cc2 = st.columns([2,1])
    ticker = cc1.text_input("股票代號", placeholder="ORCL / DKNG", key="t1").upper()
    with cc2:
        st.markdown('<div style="font-size:11px;color:#555;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">現價</div>', unsafe_allow_html=True)
        if ticker:
            price = get_price(ticker)
            if price:
                st.markdown(f'<div style="background:#141414;border-radius:12px;padding:13px;text-align:center;font-size:16px;font-weight:700;color:#22C55E">${price}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#141414;border-radius:12px;padding:13px;text-align:center;font-size:13px;color:#555">查無</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:#141414;border-radius:12px;padding:13px;text-align:center;font-size:13px;color:#555">—</div>', unsafe_allow_html=True)

    calc_type = st.radio("策略", ["📈 Bull Call", "📉 Bear Put", "📞 單 Call"], horizontal=True)

    if "Bull" in calc_type:
        st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">買入 Call（低行權價）</p>', unsafe_allow_html=True)
        c1,c2=st.columns(2)
        buy_s=c1.number_input("行權價",key="b_bs",min_value=0.0,format="%.2f")
        buy_p=c2.number_input("權利金",key="b_bp",min_value=0.0,format="%.2f")
        st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">賣出 Call（高行權價）</p>', unsafe_allow_html=True)
        c1,c2=st.columns(2)
        sell_s=c1.number_input("行權價",key="b_ss",min_value=0.0,format="%.2f")
        sell_p=c2.number_input("權利金",key="b_sp",min_value=0.0,format="%.2f")
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("計算損益",key="cb"):
            if buy_s and buy_p and sell_s and sell_p:
                nc=buy_p-sell_p;sp=sell_s-buy_s;mp=(sp-nc)*100;ml=nc*100
                st.divider(); show_calc_results("bull",mp,ml,buy_s+nc,nc,bs=buy_s,ss=sell_s,spread=sp)
            else: st.error("請填入所有數值")
    elif "Bear" in calc_type:
        st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">買入 Put（高行權價）</p>', unsafe_allow_html=True)
        c1,c2=st.columns(2)
        buy_s=c1.number_input("行權價",key="p_bs",min_value=0.0,format="%.2f")
        buy_p=c2.number_input("權利金",key="p_bp",min_value=0.0,format="%.2f")
        st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">賣出 Put（低行權價）</p>', unsafe_allow_html=True)
        c1,c2=st.columns(2)
        sell_s=c1.number_input("行權價",key="p_ss",min_value=0.0,format="%.2f")
        sell_p=c2.number_input("權利金",key="p_sp",min_value=0.0,format="%.2f")
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("計算損益",key="cp"):
            if buy_s and buy_p and sell_s and sell_p:
                nc=buy_p-sell_p;sp=buy_s-sell_s;mp=(sp-nc)*100;ml=nc*100
                st.divider(); show_calc_results("bear",mp,ml,buy_s-nc,nc,bs=buy_s,ss=sell_s,spread=sp)
            else: st.error("請填入所有數值")
    else:
        st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">買入 Call</p>', unsafe_allow_html=True)
        c1,c2,c3=st.columns(3)
        strike=c1.number_input("行權價",key="c_ks",min_value=0.0,format="%.2f")
        premium=c2.number_input("權利金",key="c_pp",min_value=0.0,format="%.2f")
        target=c3.number_input("目標價",key="c_tp",min_value=0.0,format="%.2f")
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("計算損益",key="cc"):
            if strike and premium:
                ml=premium*100;be=strike+premium
                mp=(target-strike-premium)*100 if target else None
                st.divider(); show_calc_results("call",mp or 0,ml,be,premium,strike=strike,premium=premium)
            else: st.error("請填入行權價和權利金")

# ══════ TAB 2: COMPARE ══════
with tab2:
    c1,c2,c3=st.columns(3)
    cmp_ticker=c1.text_input("股票",key="cmp_t",placeholder="ORCL").upper()
    auto_price = get_price(cmp_ticker) if cmp_ticker else None
    cmp_cur=c2.number_input("現價",key="cmp_c",min_value=0.0,format="%.2f",value=float(auto_price) if auto_price else 0.0)
    cmp_target=c3.number_input("目標價",key="cmp_tg",min_value=0.0,format="%.2f")
    if auto_price:
        st.markdown(f'<p style="font-size:11px;color:#22C55E;margin:-8px 0 8px">✓ {cmp_ticker} 現價 ${auto_price}（自動帶入）</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">📈 Bull Call Spread</p>', unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    cbbs=c1.number_input("買入價",key="cbbs",min_value=0.0,format="%.2f")
    cbbp=c2.number_input("買入金",key="cbbp",min_value=0.0,format="%.2f")
    cbss=c3.number_input("賣出價",key="cbss",min_value=0.0,format="%.2f")
    cbsp=c4.number_input("賣出金",key="cbsp",min_value=0.0,format="%.2f")
    st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">📉 Bear Put Spread</p>', unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    cpbs=c1.number_input("買入價",key="cpbs",min_value=0.0,format="%.2f")
    cpbp=c2.number_input("買入金",key="cpbp",min_value=0.0,format="%.2f")
    cpss=c3.number_input("賣出價",key="cpss",min_value=0.0,format="%.2f")
    cpsp=c4.number_input("賣出金",key="cpsp",min_value=0.0,format="%.2f")
    st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">📞 單買 Call</p>', unsafe_allow_html=True)
    c1,c2=st.columns(2)
    ccks=c1.number_input("行權價",key="ccks",min_value=0.0,format="%.2f")
    ccpp=c2.number_input("權利金",key="ccpp",min_value=0.0,format="%.2f")
    st.markdown("<br>",unsafe_allow_html=True)
    if st.button("比較三種策略",key="cmp_btn"):
        results={}
        if cbbs and cbbp and cbss and cbsp:
            nc=cbbp-cbsp;sp=cbss-cbbs;ml=nc*100;mp=(sp-nc)*100
            pat=spread_pnl("bull",cmp_target,cbbs,cbss,nc,ml)
            results["Bull Call"]={"最大獲利":f"+${fmtm(mp)}","最大虧損":f"-${fmtm(ml)}","損益平衡":f"${fmt(cbbs+nc)}","目標損益":f"{'+' if pat>=0 else ''}${fmtm(pat)}","報酬率":f"{mp/ml*100:.0f}%","成本":f"${fmtm(ml)}","_ror":mp/ml*100}
        if cpbs and cpbp and cpss and cpsp:
            nc=cpbp-cpsp;sp=cpbs-cpss;ml=nc*100;mp=(sp-nc)*100
            pat=spread_pnl("bear",cmp_target,cpbs,cpss,nc,ml)
            results["Bear Put"]={"最大獲利":f"+${fmtm(mp)}","最大虧損":f"-${fmtm(ml)}","損益平衡":f"${fmt(cpbs-nc)}","目標損益":f"{'+' if pat>=0 else ''}${fmtm(pat)}","報酬率":f"{mp/ml*100:.0f}%","成本":f"${fmtm(ml)}","_ror":mp/ml*100}
        if ccks and ccpp:
            ml=ccpp*100;pat=call_pnl(cmp_target,ccks,ccpp)
            results["單Call"]={"最大獲利":f"+${fmtm(max(pat,0))}","最大虧損":f"-${fmtm(ml)}","損益平衡":f"${fmt(ccks+ccpp)}","目標損益":f"{'+' if pat>=0 else ''}${fmtm(pat)}","報酬率":f"{pat/ml*100:.0f}%","成本":f"${fmtm(ml)}","_ror":pat/ml*100}
        if results:
            best=max(results,key=lambda k:results[k]["_ror"])
            lbls=["最大獲利","最大虧損","損益平衡","目標損益","報酬率","成本"]
            cols_r=list(results.keys())
            hdr="| 項目 | "+" | ".join(cols_r)+" |"
            sep="| --- | "+" | ".join(["---"]*len(cols_r))+" |"
            rows_md=[hdr,sep]
            for lbl in lbls:
                row=[lbl]
                for k in cols_r:
                    v=results[k][lbl]
                    if lbl=="報酬率" and k==best: v=f"✅ **{v}**"
                    row.append(v)
                rows_md.append("| "+" | ".join(row)+" |")
            st.divider(); st.markdown("\n".join(rows_md))
            st.success(f"🏆 最佳策略：**{best}** — {results[best]['報酬率']}")

# ══════ TAB 3: AI SCAN ══════
with tab3:
    st.markdown("""
    <div style="background:#0D1F14;border:1px solid #22C55E;border-radius:14px;padding:14px;margin-bottom:18px">
      <div style="font-size:13px;color:#22C55E;font-weight:700;margin-bottom:4px">🤖 AI 智能分析</div>
      <div style="font-size:12px;color:#555;line-height:1.5">上傳 1-3 張期權鏈截圖，AI 找出 8 個最佳組合<br>以「不易賠錢＋成本低」為優先排序</div>
    </div>
    """, unsafe_allow_html=True)
    scan_ticker = st.text_input("股票代號", placeholder="DKNG / ORCL / MU", key="stk").upper()
    scan_info = None
    scan_price = None
    if scan_ticker:
        scan_info = stock_info_card(scan_ticker)
        scan_price = scan_info.get("price") if scan_info else None

    uploaded_files = st.file_uploader("上傳截圖（最多3張）", type=["png","jpg","jpeg","webp"], accept_multiple_files=True)

    if uploaded_files:
        cols = st.columns(min(len(uploaded_files),3))
        all_b64s = []
        for i, f in enumerate(uploaded_files[:3]):
            with cols[i]: st.image(f, use_container_width=True)
            all_b64s.append(compress_image(f))

        if st.button("🤖  AI 分析 8 個最佳組合", key="scan_btn"):
            if not api_key:
                st.error("請先設定 API Key")
            else:
                with st.spinner("AI 深度分析中，約 20-30 秒..."):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        price_hint = f"現價為 ${scan_price}（已由系統提供，請用此價格）。" if scan_price else "請從截圖讀取現價。"
                        prompt = f"""你是頂級期權策略分析師。分析這些期權鏈截圖（股票：{scan_ticker or '未知'}）。{price_hint}

第一步：讀取每個行權價對應的 Call 賣盤/買盤、Put 賣盤/買盤價格。

第二步：計算所有可能組合：
- Bull Call：淨成本=低Call賣盤-高Call買盤，最大獲利=(價差-淨成本)×100，報酬率=最大獲利/最大虧損×100
- Bear Put：淨成本=高Put賣盤-低Put買盤，計算同上
- Single Call：損益平衡=行權價+賣盤，報酬率用(現價×1.15-行權價-賣盤)/賣盤×100

第三步：排序原則【重要】——不是選報酬率最高，而是綜合考量「安全性」：
1. 損益平衡點越接近現價越好（越容易獲利）
2. 最大虧損（成本）越低越好（賠也賠得少）
3. 盈虧比合理（不要為高報酬冒巨大風險）
選出：Bull前3、Bear前3、Call前2（共8個），每組評1-5星（星級代表安全性與性價比）

第四步：為每組寫優點、缺點各1句（20字內）

第五步：從8個中選整體最佳Top3，以「最不容易賠錢＋成本低」為準

只回純JSON：
{{"currentPrice":{scan_price or 29.0},"ticker":"{scan_ticker or 'DKNG'}",
"bull":[{{"rank":1,"buyStrike":30,"buyPremium":2.42,"sellStrike":35,"sellPremium":0.95,"maxProfit":333,"maxLoss":167,"breakeven":31.67,"ror":199,"pros":"優點","cons":"缺點","stars":4}}],
"bear":[{{"rank":1,"buyStrike":28,"buyPremium":1.94,"sellStrike":22,"sellPremium":0.51,"maxProfit":338,"maxLoss":162,"breakeven":26.57,"ror":209,"pros":"優點","cons":"缺點","stars":4}}],
"call":[{{"rank":1,"strike":32.5,"premium":1.56,"breakeven":34.06,"ror":85,"pros":"優點","cons":"缺點","stars":3}}],
"top3Overall":[{{"type":"bull","ref_rank":1,"medal":"🥇","summary":"損益平衡最接近現價，最容易獲利"}}]}}
注意：金額精確，bull需3個bear需3個call需2個，top3Overall需3個。"""
                        content_parts = [{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b}} for b in all_b64s]
                        content_parts.append({"type":"text","text":prompt})
                        msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=3000, messages=[{"role":"user","content":content_parts}])
                        text = msg.content[0].text.strip()
                        match = re.search(r'\{[\s\S]*\}', text)
                        if not match:
                            st.error("格式錯誤：" + text[:300])
                        else:
                            data = json.loads(match.group())
                            cur = data.get("currentPrice", scan_price or 0)
                            tkr = data.get("ticker", scan_ticker)
                            all_items = [("bull",x) for x in data.get("bull",[])] + [("bear",x) for x in data.get("bear",[])] + [("call",x) for x in data.get("call",[])]
                            max_ror = max([x[1].get("ror",0) for x in all_items]) if all_items else 0

                            st.markdown(f"""
                            <div style="display:flex;justify-content:space-between;align-items:flex-end;padding:6px 0 16px;border-bottom:1px solid #2A2A2A;margin-bottom:16px">
                              <div><div style="font-size:22px;font-weight:900;letter-spacing:-0.8px">{tkr}</div>
                              <div style="font-size:12px;color:#555;margin-top:1px">現價 ${fmt(cur)} · 8 個組合</div></div>
                              <div style="text-align:right"><div style="font-size:10px;color:#555;font-weight:700;letter-spacing:0.5px">最高投資報酬率</div>
                              <div style="font-size:20px;font-weight:800;color:#22C55E">{max_ror:.0f}%</div></div>
                            </div>""", unsafe_allow_html=True)

                            # Top 3
                            top3 = data.get("top3Overall", [])
                            top3_keys = {}
                            if top3:
                                st.markdown('<div style="font-size:10px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:10px">整體最佳 Top 3</div>', unsafe_allow_html=True)
                                for t3 in top3[:3]:
                                    typ=t3.get("type"); ref=t3.get("ref_rank",1)
                                    top3_keys[f"{typ}-{ref}"]=t3.get("medal","")
                                    lst=data.get(typ,[])
                                    item=next((x for x in lst if x.get("rank")==ref), lst[0] if lst else {})
                                    tc="#3B82F6" if typ=="bull" else "#EF4444" if typ=="bear" else "#22C55E"
                                    tlabel="BULL" if typ=="bull" else "BEAR" if typ=="bear" else "CALL"
                                    strikes=f"${fmt(item.get('buyStrike',0))} / ${fmt(item.get('sellStrike',0))}" if typ!="call" else f"${fmt(item.get('strike',0))} Call"
                                    st.markdown(f"""
                                    <div style="background:#141414;border:1px solid #2A2A2A;border-radius:12px;padding:10px 14px;margin-bottom:8px;display:flex;align-items:center;gap:10px">
                                      <span style="font-size:20px">{t3.get('medal','')}</span>
                                      <div style="flex:1;min-width:0">
                                        <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
                                          <span style="font-size:9px;font-weight:800;color:{tc};background:{tc}18;padding:2px 7px;border-radius:100px;letter-spacing:1px">{tlabel}</span>
                                          <span style="font-size:13px;font-weight:700;color:#F0F0F0">{strikes}</span>
                                        </div>
                                        <div style="font-size:11px;color:#555;line-height:1.4">{t3.get('summary','')}</div>
                                      </div>
                                      <div style="text-align:right;flex-shrink:0">
                                        <div style="font-size:16px;font-weight:800;color:#22C55E">{item.get('ror',0):.0f}%</div>
                                        <div style="font-size:11px;color:#F0B429">{stars(item.get('stars',3))}</div>
                                      </div>
                                    </div>""", unsafe_allow_html=True)

                            # Overview list — expandable
                            st.markdown('<div style="font-size:10px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin:20px 0 8px">全部 8 個組合（點擊展開）</div>', unsafe_allow_html=True)
                            for typ, item in all_items:
                                tc="#3B82F6" if typ=="bull" else "#EF4444" if typ=="bear" else "#22C55E"
                                tlabel="Bull" if typ=="bull" else "Bear" if typ=="bear" else "Call"
                                key=f"{typ}-{item.get('rank')}"
                                medal=top3_keys.get(key,"")
                                strikes=f"${fmt(item.get('buyStrike',0))} / ${fmt(item.get('sellStrike',0))}" if typ!="call" else f"${fmt(item.get('strike',0))} Call"
                                ror_v=item.get("ror",0)
                                title=f"{medal+'  ' if medal else ''}{tlabel}  {strikes}  ·  平衡 ${fmt(item.get('breakeven',0))}  ·  {ror_v:.0f}%"
                                with st.expander(title):
                                    mp=item.get("maxProfit",0); ml=item.get("maxLoss",0); be=item.get("breakeven",0)
                                    c1,c2,c3=st.columns(3)
                                    c1.metric("最大獲利", f"+${fmtm(mp)}")
                                    c2.metric("最大虧損", f"-${fmtm(ml)}")
                                    c3.metric("損益平衡", f"${fmt(be)}")
                                    st.markdown(f'<div style="text-align:center;margin:4px 0 8px;color:#F0B429;font-size:14px">{stars(item.get("stars",3))}</div>', unsafe_allow_html=True)
                                    st.markdown(f"""
                                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
                                      <div style="background:#0D1F14;border:1px solid #1A3A24;border-radius:10px;padding:8px 10px">
                                        <div style="font-size:9px;color:#22C55E;font-weight:700;margin-bottom:3px">✓ 優點</div>
                                        <div style="font-size:12px;color:#AAA;line-height:1.4">{item.get('pros','')}</div></div>
                                      <div style="background:#1F0D0D;border:1px solid #3A1A1A;border-radius:10px;padding:8px 10px">
                                        <div style="font-size:9px;color:#EF4444;font-weight:700;margin-bottom:3px">✗ 缺點</div>
                                        <div style="font-size:12px;color:#AAA;line-height:1.4">{item.get('cons','')}</div></div>
                                    </div>""", unsafe_allow_html=True)
                                    if typ!="call":
                                        bs=item.get("buyStrike",0);ss=item.get("sellStrike",0)
                                        bp=item.get("buyPremium",0);sp2=item.get("sellPremium",0)
                                        if bs and ss and bp and sp2:
                                            nc=bp-sp2
                                            show_ladder(typ,bs,ss,nc,nc*100,be,abs(bs-ss),bs,bp)
                                    else:
                                        bs=item.get("strike",0);bp=item.get("premium",0)
                                        if bs and bp: show_ladder("call",0,0,bp,bp*100,be,0,bs,bp)
                                    # Save button
                                    if st.button("⭐ 收藏這個組合", key=f"fav_{key}"):
                                        combo = dict(item); combo["type"]=typ; combo["ticker"]=tkr; combo["currentPrice"]=cur
                                        add_fav(combo)
                                        st.success("已收藏！到「我的組合」查看")
                    except Exception as e:
                        st.error(f"分析失敗：{e}")

# ══════ TAB 4: HELP ══════
# ══════ TAB 4: 我的組合 ══════
with tab4:
    favs = load_favs()
    if not favs:
        st.markdown('''<div style="background:#141414;border-radius:14px;padding:30px 20px;text-align:center;color:#555;font-size:13px">
        尚無收藏組合<br><span style="font-size:11px">在 AI 掃描分析後，點 ⭐ 收藏喜歡的組合</span></div>''', unsafe_allow_html=True)
    else:
        # Group by ticker
        groups = {}
        for f in favs:
            k = f.get("ticker","未命名")
            groups.setdefault(k, []).append(f)
        st.markdown(f'<div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">已收藏 {len(favs)} 個組合</div>', unsafe_allow_html=True)
        for tk, items in groups.items():
            st.markdown(f'<div style="font-size:15px;font-weight:800;color:#F0F0F0;margin:14px 0 8px">📌 {tk} <span style="font-size:11px;color:#555;font-weight:400">{len(items)} 個</span></div>', unsafe_allow_html=True)
            for f in items:
                typ = f.get("type","")
                tc = "#3B82F6" if typ=="bull" else "#EF4444" if typ=="bear" else "#22C55E"
                tlabel = "Bull" if typ=="bull" else "Bear" if typ=="bear" else "Call"
                strikes = f"${fmt(f.get('buyStrike',0))} / ${fmt(f.get('sellStrike',0))}" if typ!="call" else f"${fmt(f.get('strike',0))} Call"
                ror_v = f.get("ror",0); be = f.get("breakeven",0)
                mp = f.get("maxProfit",0); ml = f.get("maxLoss",0)
                with st.expander(f"{tlabel}  {strikes}  ·  平衡 ${fmt(be)}  ·  {ror_v:.0f}%"):
                    c1,c2,c3 = st.columns(3)
                    c1.metric("最大獲利", f"+${fmtm(mp)}")
                    c2.metric("最大虧損", f"-${fmtm(ml)}")
                    c3.metric("損益平衡", f"${fmt(be)}")
                    st.markdown(f'<div style="text-align:center;margin:4px 0 8px;color:#F0B429;font-size:14px">{stars(f.get("stars",3))}</div>', unsafe_allow_html=True)
                    if f.get("pros") or f.get("cons"):
                        st.markdown(f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
                          <div style="background:#0D1F14;border:1px solid #1A3A24;border-radius:10px;padding:8px 10px">
                            <div style="font-size:9px;color:#22C55E;font-weight:700;margin-bottom:3px">✓ 優點</div>
                            <div style="font-size:12px;color:#AAA;line-height:1.4">{f.get('pros','')}</div></div>
                          <div style="background:#1F0D0D;border:1px solid #3A1A1A;border-radius:10px;padding:8px 10px">
                            <div style="font-size:9px;color:#EF4444;font-weight:700;margin-bottom:3px">✗ 缺點</div>
                            <div style="font-size:12px;color:#AAA;line-height:1.4">{f.get('cons','')}</div></div>
                        </div>''', unsafe_allow_html=True)
                    if typ!="call":
                        bs=f.get("buyStrike",0);ss=f.get("sellStrike",0);bp=f.get("buyPremium",0);sp2=f.get("sellPremium",0)
                        if bs and ss and bp and sp2:
                            show_ladder(typ,bs,ss,bp-sp2,(bp-sp2)*100,be,abs(bs-ss),bs,bp)
                    else:
                        bs=f.get("strike",0);bp=f.get("premium",0)
                        if bs and bp: show_ladder("call",0,0,bp,bp*100,be,0,bs,bp)
                    if st.button("🗑 移除", key=f"del_{f.get('_id','')}"):
                        save_favs([x for x in load_favs() if x.get("_id")!=f.get("_id")])
                        st.rerun()

with tab5:
    st.markdown("""
    <div style="color:#F0F0F0">
    <div style="margin-bottom:16px"><div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">什麼是投資報酬率 (ROI)</div>
    <div style="background:#141414;border-radius:14px;padding:14px;font-size:13px;color:#AAA;line-height:1.6">投資報酬率 = 最大獲利 ÷ 最大成本 × 100%<br><br>例如成本$167，最多賺$333，報酬率=199%，代表投入的錢最多賺回約2倍。</div></div>
    <div style="margin-bottom:16px"><div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">策略說明</div>
    <div style="background:#141414;border-radius:14px;padding:14px;font-size:13px;color:#AAA;line-height:1.6"><b style="color:#F0F0F0">Bull Call</b> — 看漲，買低Call賣高Call<br><br><b style="color:#F0F0F0">Bear Put</b> — 看跌，買高Put賣低Put<br><br><b style="color:#F0F0F0">單買Call</b> — 看漲，無限獲利潛力</div></div>
    <div><div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">AI 排序原則</div>
    <div style="background:#141414;border-radius:14px;padding:14px;font-size:13px;color:#AAA;line-height:1.6">以「最不容易賠錢」為優先：<br>1. 損益平衡接近現價<br>2. 成本（最大虧損）低<br>3. 盈虧比合理</div></div>
    </div>""", unsafe_allow_html=True)
