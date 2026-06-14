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


# ── Strategy computation (all math in Python, not AI) ──
def compute_strategies(rows, cur, ticker, expiry):
    """rows: list of {strike, callBid, callAsk, putBid, putAsk}. Compute all valid spreads."""
    valid = [r for r in rows if r.get("strike") is not None]
    valid.sort(key=lambda r: r["strike"])

    bulls, bears, calls = [], [], []

    # Bull Call: buy lower strike (callAsk), sell higher strike (callBid)
    for i in range(len(valid)):
        for j in range(i+1, len(valid)):
            lo, hi = valid[i], valid[j]
            ba = lo.get("callAsk"); sb = hi.get("callBid")
            if ba is None or sb is None or ba <= 0: continue
            nc = ba - sb
            if nc <= 0: continue  # must be debit
            spread = hi["strike"] - lo["strike"]
            maxP = (spread - nc) * 100
            maxL = nc * 100
            if maxP <= 0 or maxL <= 0: continue
            rr = maxP / maxL
            if rr < 1.0: continue  # exclude poor risk/reward
            be = lo["strike"] + nc
            ror = maxP / maxL * 100
            # realistic: buy strike should be near/below current (ITM or slightly OTM)
            # penalize deep OTM (buyStrike far above current) — those rarely pay out
            buy_otm = (lo["strike"] - cur) / cur if cur else 0  # positive = OTM
            if buy_otm > 0.10: continue  # skip if buy leg >10% OTM (unrealistic)
            be_dist = abs(be - cur) / cur if cur else 1
            # prob of profit proxy: how far breakeven is above current
            prof_gap = (be - cur) / cur if cur else 1
            safety = (1/(1+max(prof_gap,0)*5)) * 100 * 0.5 + min(ror,300)/3 * 0.3 + (1/(1+maxL/200)) * 100 * 0.2
            bulls.append({"type":"bull","buyStrike":lo["strike"],"buyPremium":round(ba,2),"sellStrike":hi["strike"],"sellPremium":round(sb,2),
                "maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(rr,2),"_safety":safety})

    # Bear Put: buy higher strike (putAsk), sell lower strike (putBid)
    for i in range(len(valid)):
        for j in range(i+1, len(valid)):
            lo, hi = valid[i], valid[j]
            ba = hi.get("putAsk"); sb = lo.get("putBid")
            if ba is None or sb is None or ba <= 0: continue
            nc = ba - sb
            if nc <= 0: continue
            spread = hi["strike"] - lo["strike"]
            maxP = (spread - nc) * 100
            maxL = nc * 100
            if maxP <= 0 or maxL <= 0: continue
            rr = maxP / maxL
            if rr < 1.0: continue
            be = hi["strike"] - nc
            ror = maxP / maxL * 100
            # realistic: buy put strike should be near/above current
            buy_otm = (cur - hi["strike"]) / cur if cur else 0  # positive = OTM (strike below current)
            if buy_otm > 0.10: continue  # skip deep OTM puts
            # prob proxy: how far below current the breakeven is
            prof_gap = (cur - be) / cur if cur else 1
            safety = (1/(1+max(prof_gap,0)*5)) * 100 * 0.5 + min(ror,300)/3 * 0.3 + (1/(1+maxL/200)) * 100 * 0.2
            bears.append({"type":"bear","buyStrike":hi["strike"],"buyPremium":round(ba,2),"sellStrike":lo["strike"],"sellPremium":round(sb,2),
                "maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(rr,2),"_safety":safety})

    # Single Call: buy callAsk, target = cur*1.15
    for r in valid:
        ba = r.get("callAsk")
        if ba is None or ba <= 0: continue
        # only near-the-money calls (within +/-10% of current)
        if cur and abs(r["strike"] - cur) / cur > 0.12: continue
        be = r["strike"] + ba
        target = cur * 1.20 if cur else r["strike"] * 1.20
        maxP = (target - r["strike"] - ba) * 100
        maxL = ba * 100
        if maxP <= 0: continue
        ror = maxP / maxL * 100
        prof_gap = (be - cur) / cur if cur else 1
        safety = (1/(1+max(prof_gap,0)*4)) * 100 * 0.6 + min(ror,200)/2 * 0.2 + (1/(1+maxL/300)) * 100 * 0.2
        calls.append({"type":"call","strike":r["strike"],"premium":round(ba,2),
            "maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_safety":safety})

    # Sort by safety (not pure ROI), take top
    bulls.sort(key=lambda x: -x["_safety"]); bears.sort(key=lambda x: -x["_safety"]); calls.sort(key=lambda x: -x["_safety"])
    bulls, bears, calls = bulls[:3], bears[:3], calls[:2]

    # Assign stars by safety percentile
    def assign_stars(items):
        for it in items:
            s = it["_safety"]
            it["stars"] = 5 if s>=90 else 4 if s>=70 else 3 if s>=50 else 2
            # auto pros/cons
            pros = []; cons = []
            if it["rr"] >= 2: pros.append("盈虧比佳")
            if it["maxLoss"] <= 150: pros.append("成本低")
            be_d = abs(it["breakeven"]-cur)/cur*100 if cur else 0
            if be_d <= 5: pros.append("接近現價易獲利")
            if it["rr"] < 1.5: cons.append("盈虧比偏低")
            if it["maxLoss"] > 300: cons.append("成本較高")
            if be_d > 8: cons.append(f"需變動{be_d:.0f}%")
            it["pros"] = "、".join(pros) if pros else "風險可控"
            it["cons"] = "、".join(cons) if cons else "需注意時間價值"
    assign_stars(bulls); assign_stars(bears); assign_stars(calls)

    # Overall top 3 by safety across all
    everything = bulls + bears + calls
    everything_sorted = sorted(everything, key=lambda x: -x["_safety"])
    top3 = everything_sorted[:3]
    medals = ["🥇","🥈","🥉"]
    for i,t in enumerate(top3):
        t["_medal"] = medals[i]

    return {"cur":cur, "ticker":ticker, "expiry":expiry, "bull":bulls, "bear":bears, "call":calls, "top3":top3}


def combo_strikes(it):
    if it["type"]=="call": return f"${fmt(it['strike'])} Call"
    return f"買${fmt(it['buyStrike'])} 賣${fmt(it['sellStrike'])}"

def combo_typename(t):
    return "看漲價差" if t=="bull" else "看跌價差" if t=="bear" else "單買Call"

def render_combo_detail(it, cur, show_save=True, save_key=""):
    t = it["type"]
    mp, ml, be = it.get("maxProfit",0), it.get("maxLoss",0), it.get("breakeven",0)
    ror = it.get("ror",0); rr = it.get("rr",0)
    # one-row metrics
    st.markdown(f'''
    <div style="display:flex;gap:6px;margin:8px 0">
      <div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:3px">最大獲利</div>
        <div style="font-size:15px;font-weight:700;color:#22C55E">+${fmtm(mp)}</div></div>
      <div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:3px">最大虧損</div>
        <div style="font-size:15px;font-weight:700;color:#EF4444">-${fmtm(ml)}</div></div>
      <div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#F59E0B;font-weight:700;margin-bottom:3px">損益平衡</div>
        <div style="font-size:15px;font-weight:700;color:#F59E0B">${fmt(be)}</div></div>
      <div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:3px">盈虧比</div>
        <div style="font-size:15px;font-weight:700;color:#F0F0F0">{rr:.2f}x</div></div>
    </div>
    <div style="text-align:center;margin:2px 0 8px;color:#F0B429;font-size:14px">{stars(it.get("stars",3))}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
      <div style="background:#0D1F14;border:1px solid #1A3A24;border-radius:10px;padding:8px 10px">
        <div style="font-size:9px;color:#22C55E;font-weight:700;margin-bottom:3px">✓ 優點</div>
        <div style="font-size:12px;color:#AAA;line-height:1.4">{it.get('pros','')}</div></div>
      <div style="background:#1F0D0D;border:1px solid #3A1A1A;border-radius:10px;padding:8px 10px">
        <div style="font-size:9px;color:#EF4444;font-weight:700;margin-bottom:3px">✗ 缺點</div>
        <div style="font-size:12px;color:#AAA;line-height:1.4">{it.get('cons','')}</div></div>
    </div>''', unsafe_allow_html=True)
    # ladder
    if t!="call":
        bs=it["buyStrike"];ss=it["sellStrike"];bp=it["buyPremium"];sp2=it["sellPremium"]
        show_ladder(t,bs,ss,bp-sp2,(bp-sp2)*100,be,abs(bs-ss),bs,bp)
    else:
        show_ladder("call",0,0,it["premium"],it["premium"]*100,be,0,it["strike"],it["premium"])
    if show_save:
        if st.button("⭐ 收藏這個組合", key=save_key):
            combo = {k:v for k,v in it.items() if not k.startswith("_")}
            combo["ticker"]=st.session_state["scan_result"]["ticker"]
            combo["currentPrice"]=cur
            add_fav(combo); st.success("已收藏！到「我的組合」查看")

def render_scan_results(res):
    cur = res["cur"]; tkr = res["ticker"]; exp = res["expiry"]
    allc = res["bull"]+res["bear"]+res["call"]
    if not allc:
        st.error("找不到有效組合（可能截圖數字不清楚，或都是盈虧比過低的組合）"); return
    max_ror = max(x["ror"] for x in allc)
    exp_txt = f" · 到期 {exp}" if exp else ""
    st.markdown(f'''
    <div style="display:flex;justify-content:space-between;align-items:flex-end;padding:6px 0 14px;border-bottom:1px solid #2A2A2A;margin-bottom:14px">
      <div><div style="font-size:22px;font-weight:900;letter-spacing:-0.8px">{tkr or "分析結果"}</div>
      <div style="font-size:12px;color:#555;margin-top:1px">現價 ${fmt(cur)}{exp_txt}</div></div>
      <div style="text-align:right"><div style="font-size:10px;color:#555;font-weight:700">最高投資報酬率</div>
      <div style="font-size:20px;font-weight:800;color:#22C55E">{max_ror:.0f}%</div></div>
    </div>''', unsafe_allow_html=True)

    # Top 3 — directly expandable
    st.markdown('<div style="font-size:10px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:8px">整體最佳 Top 3（點擊看損益）</div>', unsafe_allow_html=True)
    for i, it in enumerate(res["top3"]):
        t = it["type"]
        tname = combo_typename(t)
        medal = it.get("_medal","")
        medal_txt = {"🥇":"金牌","🥈":"銀牌","🥉":"銅牌"}.get(medal,"")
        with st.expander(f"{medal_txt}｜{tname}  {combo_strikes(it)}  ·  {it['ror']:.0f}%", expanded=(i==0)):
            st.markdown(f'<div style="font-size:24px;text-align:center;margin-bottom:4px">{medal}</div>', unsafe_allow_html=True)
            render_combo_detail(it, cur, save_key=f"savetop_{i}")

    # All combos by category
    def render_group(items, label):
        if not items: return
        st.markdown(f'<div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:18px 0 8px">{label}</div>', unsafe_allow_html=True)
        for idx, it in enumerate(items):
            tname = combo_typename(it["type"])
            with st.expander(f"{tname}  {combo_strikes(it)}  ·  平衡 ${fmt(it['breakeven'])}  ·  {it['ror']:.0f}%"):
                render_combo_detail(it, cur, save_key=f"save_{it['type']}_{idx}")
    render_group(res["bull"], "📈 看漲價差 Bull Call — Top 3")
    render_group(res["bear"], "📉 看跌價差 Bear Put — Top 3")
    render_group(res["call"], "📞 單買 Call — Top 2")


tab1, tab2, tab3, tab4, tab5 = st.tabs(["計算", "比較", "AI 掃描", "我的組合", "說明"])

# ══════ TAB 1: CALC ══════
with tab1:
    # ── Stock + Expiry selector ──────────────────────
    tc1, tc2 = st.columns([2, 1])
    chain_ticker = tc1.text_input("股票代號", placeholder="ORCL / DKNG / MU", key="ct").upper()

    @st.cache_data(ttl=300)
    def get_chain_expiries(symbol):
        if not HAS_YF or not symbol: return []
        try:
            return list(yf.Ticker(symbol).options)
        except Exception: return []

    @st.cache_data(ttl=120)
    def get_chain_data(symbol, expiry):
        if not HAS_YF or not symbol or not expiry: return None, None
        try:
            t = yf.Ticker(symbol)
            opt = t.option_chain(expiry)
            cur = round(float(t.fast_info.get("lastPrice") or t.fast_info.get("last_price") or 0), 2)
            calls_df = opt.calls[["strike","bid","ask"]].rename(columns={"bid":"callBid","ask":"callAsk"})
            puts_df  = opt.puts[["strike","bid","ask"]].rename(columns={"bid":"putBid","ask":"putAsk"})
            merged = calls_df.merge(puts_df, on="strike", how="outer").sort_values("strike")
            rows = merged.to_dict("records")
            return cur, rows
        except Exception as e:
            return None, None

    expiries = get_chain_expiries(chain_ticker) if chain_ticker else []

    if expiries:
        selected_expiry = tc2.selectbox("到期日", expiries, key="cexp")
    else:
        tc2.markdown('<div style="background:#141414;border-radius:12px;padding:13px;text-align:center;font-size:12px;color:#555">輸入代號</div>', unsafe_allow_html=True)
        selected_expiry = None

    if chain_ticker and selected_expiry:
        chain_cur, chain_rows = get_chain_data(chain_ticker, selected_expiry)
        if chain_cur:
            stock_info_card(chain_ticker)
        if not chain_rows:
            st.error("抓不到期權鏈，請稍後再試")
        else:
            # ── Strategy selector ──
            strat_map = {"看漲價差 Bull Call":"bull","看跌價差 Bear Put":"bear","單買 Call":"call","單買 Put":"put"}
            strat_labels = list(strat_map.keys())
            strat_needs = {"bull":["buyCall","sellCall"],"bear":["buyPut","sellPut"],"call":["buyCall"],"put":["buyPut"]}
            leg_label_map = {"buyCall":"買入 Call","sellCall":"賣出 Call","buyPut":"買入 Put","sellPut":"賣出 Put"}
            strat_colors = {"bull":"#3B82F6","bear":"#EF4444","call":"#22C55E","put":"#F59E0B"}

            if "chain_strat" not in st.session_state: st.session_state["chain_strat"] = "bull"
            if "chain_legs" not in st.session_state: st.session_state["chain_legs"] = {}

            chosen_lbl = st.selectbox("策略", strat_labels, key="chain_strat_sel",
                index=list(strat_map.values()).index(st.session_state["chain_strat"]),
                label_visibility="collapsed")
            new_sk = strat_map[chosen_lbl]
            if new_sk != st.session_state["chain_strat"]:
                st.session_state["chain_strat"] = new_sk
                st.session_state["chain_legs"] = {}
                st.rerun()

            cur_strat = st.session_state["chain_strat"]
            cur_legs  = st.session_state["chain_legs"]
            needs     = strat_needs[cur_strat]
            next_leg  = next((n for n in needs if n not in cur_legs), None)

            # Leg status display
            leg_html = ""
            for n in needs:
                filled = n in cur_legs
                val = f"${fmt(cur_legs[n]['strike'])} @ ${fmt(cur_legs[n]['prem'])}" if filled else "點下方選"
                col_c = "#22C55E" if filled else "#555"
                border = f"1px solid {strat_colors[cur_strat]}" if (not filled and n==next_leg) else "1px solid #2A2A2A"
                leg_html += f'''<div style="flex:1;background:#1C1C1C;border:{border};border-radius:10px;padding:8px 10px">
                  <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:2px">{leg_label_map[n]}</div>
                  <div style="font-size:13px;font-weight:700;color:{col_c}">{val}</div></div>'''
            reset_btn = '<div style="display:flex;align-items:center"><button onclick="void(0)" style="background:none;border:none;color:#555;font-size:18px;cursor:pointer">↺</button></div>'
            st.markdown(f'<div style="display:flex;gap:6px;margin:10px 0 6px">{leg_html}</div>', unsafe_allow_html=True)
            if cur_legs and st.button("↺ 重選", key="chain_reset"):
                st.session_state["chain_legs"] = {}
                st.rerun()

            if next_leg:
                is_buy = next_leg.startswith("buy")
                sc = strat_colors[cur_strat]
                st.markdown(f'<div style="font-size:11px;color:{sc};font-weight:600;margin-bottom:6px">👇 點選「{leg_label_map[next_leg]}」的行權價</div>', unsafe_allow_html=True)

            # ── Chain table ──────────────────────────────
            is_call_leg = next_leg and "Call" in next_leg
            is_put_leg  = next_leg and "Put"  in next_leg
            is_buy = next_leg and next_leg.startswith("buy")

            header_html = f'''<div style="display:grid;grid-template-columns:1fr 56px 1fr;background:#1C1C1C;border-radius:12px 12px 0 0;padding:6px 0">
              <div style="text-align:center;font-size:10px;color:#22C55E;font-weight:700">CALL</div>
              <div style="text-align:center;font-size:10px;color:#555;font-weight:700">行權價</div>
              <div style="text-align:center;font-size:10px;color:#EF4444;font-weight:700">PUT</div></div>'''
            st.markdown(header_html, unsafe_allow_html=True)

            for row in chain_rows:
                strike = row.get("strike",0)
                atm = chain_cur and abs(strike - chain_cur) < 1.5
                call_p = row.get("callAsk" if is_buy else "callBid")
                put_p  = row.get("putAsk"  if is_buy else "putBid")
                call_val = f"${fmt(call_p)}" if call_p else "—"
                put_val  = f"${fmt(put_p)}"  if put_p  else "—"
                row_bg = "rgba(59,130,246,0.06)" if atm else "transparent"
                strike_color = "#3B82F6" if atm else "#F0F0F0"

                col_l, col_m, col_r = st.columns([1, 0.6, 1])
                with col_l:
                    if is_call_leg and call_p:
                        if st.button(call_val, key=f"cl_{strike}", use_container_width=True):
                            st.session_state["chain_legs"][next_leg] = {"strike":strike,"prem":call_p}
                            st.rerun()
                    else:
                        st.markdown(f'<div style="text-align:center;font-size:12px;color:#555;padding:6px 0">{call_val}</div>', unsafe_allow_html=True)
                with col_m:
                    st.markdown(f'<div style="text-align:center;font-size:13px;font-weight:800;color:{strike_color};padding:6px 0">{strike:.0f if strike==int(strike) else strike}</div>', unsafe_allow_html=True)
                with col_r:
                    if is_put_leg and put_p:
                        if st.button(put_val, key=f"pt_{strike}", use_container_width=True):
                            st.session_state["chain_legs"][next_leg] = {"strike":strike,"prem":put_p}
                            st.rerun()
                    else:
                        st.markdown(f'<div style="text-align:center;font-size:12px;color:#555;padding:6px 0">{put_val}</div>', unsafe_allow_html=True)

            # ── Result ───────────────────────────────────
            if all(n in cur_legs for n in needs):
                legs = cur_legs
                def pnl_at(price):
                    v=0
                    if "buyCall"  in legs: v+=max(price-legs["buyCall"]["strike"],0)*100  - legs["buyCall"]["prem"]*100
                    if "sellCall" in legs: v+=-max(price-legs["sellCall"]["strike"],0)*100 + legs["sellCall"]["prem"]*100
                    if "buyPut"   in legs: v+=max(legs["buyPut"]["strike"]-price,0)*100   - legs["buyPut"]["prem"]*100
                    if "sellPut"  in legs: v+=-max(legs["sellPut"]["strike"]-price,0)*100 + legs["sellPut"]["prem"]*100
                    return v
                strikes_sel = [l["strike"] for l in legs.values()]
                safe_cur = chain_cur if chain_cur and chain_cur>0 else strikes_sel[0]
                # First pass: find breakeven using wide range
                _lo0=min(strikes_sel+[safe_cur])*0.80; _hi0=max(strikes_sel+[safe_cur])*1.25
                _pts0=[_lo0+(_hi0-_lo0)*i/400 for i in range(401)]
                _pnls0=[pnl_at(p) for p in _pts0]
                be=None
                for i in range(1,len(_pts0)):
                    if (_pnls0[i-1]<=0 and _pnls0[i]>0) or (_pnls0[i-1]>=0 and _pnls0[i]<0):
                        be=_pts0[i]; break
                unlimited = len(needs)==1
                # Build chart range: center around breakeven (or current price if no BE)
                center = be if be else safe_cur
                all_key = strikes_sel + [safe_cur] + ([be] if be else [])
                span = max(max(all_key)-min(all_key), chain_cur*0.15) * 1.4
                lo = center - span*0.55
                hi = center + span*0.55
                pts=[lo+(hi-lo)*i/200 for i in range(201)]
                pnls=[pnl_at(p) for p in pts]
                maxP=max(pnls); minP=min(pnls)
                cost=abs(minP)
                ror=maxP/cost*100 if cost else 0

                st.divider()
                mp_label = "無限 ∞" if unlimited else f"+${fmtm(maxP)}"
                mp_color = "#22C55E"
                st.markdown(f'''<div style="display:flex;gap:6px;margin:10px 0 10px">
                  <div style="flex:1;background:#141414;border-radius:10px;padding:10px 4px;text-align:center">
                    <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:3px">最大獲利</div>
                    <div style="font-size:14px;font-weight:700;color:#22C55E">{mp_label}</div></div>
                  <div style="flex:1;background:#141414;border-radius:10px;padding:10px 4px;text-align:center">
                    <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:3px">最大虧損</div>
                    <div style="font-size:14px;font-weight:700;color:#EF4444">-${fmtm(cost)}</div></div>
                  <div style="flex:1;background:#141414;border-radius:10px;padding:10px 4px;text-align:center">
                    <div style="font-size:9px;color:#F59E0B;font-weight:700;margin-bottom:3px">損益平衡</div>
                    <div style="font-size:14px;font-weight:700;color:#F59E0B">${fmt(be) if be else "—"}</div></div>
                  <div style="flex:1;background:#141414;border-radius:10px;padding:10px 4px;text-align:center">
                    <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:3px">{"投報率" if not unlimited else "成本"}</div>
                    <div style="font-size:14px;font-weight:700;color:#F0F0F0">{"∞" if unlimited else f"{ror:.0f}%"}</div></div>
                </div>''', unsafe_allow_html=True)

                # SVG payoff chart — full featured version
                W,H,padX,padTop,padBot=380,230,14,24,10
                plotH=H-padTop-padBot-30  # reserve 30px at bottom for labels
                vpad=(maxP-minP)*0.18
                vTop=maxP+vpad; vBot=minP-vpad; vRange=(vTop-vBot) or 1
                def cx(p): return padX+((p-lo)/(hi-lo))*(W-2*padX)
                def cy(v): return padTop+(vTop-v)/vRange*plotH
                zY=cy(0)
                line_d=" ".join(f"{'M' if i==0 else 'L'}{cx(pts[i]):.1f},{cy(pnls[i]):.1f}" for i in range(len(pts)))
                fill_d=f"{line_d} L{cx(hi):.1f},{zY:.1f} L{cx(lo):.1f},{zY:.1f} Z"
                sc=strat_colors[cur_strat]
                # x-axis price ticks
                tick_svgs="".join(f'<line x1="{cx(lo+(hi-lo)*i/5):.1f}" y1="{zY:.1f}" x2="{cx(lo+(hi-lo)*i/5):.1f}" y2="{zY+4:.1f}" stroke="#444" stroke-width="0.8"/><text x="{cx(lo+(hi-lo)*i/5):.1f}" y="{zY+13:.1f}" fill="#444" font-size="7.5" text-anchor="middle">${lo+(hi-lo)*i/5:.0f}</text>' for i in range(6))
                # strike dots with bg labels
                strike_svgs=""
                for leg_k,leg_v in legs.items():
                    sk=leg_v["strike"]
                    if not (lo<sk<hi): continue
                    sx=cx(sk)
                    pnl_at_strike=pnl_at(sk)
                    dy=cy(pnl_at_strike)
                    mc="#60A5FA" if "buy" in leg_k else "#FB923C"
                    lbl=f"{'買入' if 'buy' in leg_k else '賣出'} ${sk}"
                    above = dy > H*0.45
                    by2=dy-26 if above else dy+11
                    strike_svgs+=f'<rect x="{sx-30:.1f}" y="{by2:.1f}" width="60" height="14" rx="3" fill="#0D0D0D" opacity="0.9"/><text x="{sx:.1f}" y="{by2+11:.1f}" fill="{mc}" font-size="9" text-anchor="middle" font-weight="700">{lbl}</text><circle cx="{sx:.1f}" cy="{dy:.1f}" r="5" fill="{mc}"/><circle cx="{sx:.1f}" cy="{dy:.1f}" r="9" fill="{mc}" opacity="0.18"/>'
                # breakeven dot
                be_svg=""
                if be and lo<be<hi:
                    bx=cx(be)
                    be_svg=f'<rect x="{bx-32:.1f}" y="{zY-30:.1f}" width="64" height="22" rx="4" fill="#0D0D0D" opacity="0.9"/><text x="{bx:.1f}" y="{zY-18:.1f}" fill="#F0B429" font-size="8" text-anchor="middle" font-weight="600">損益平衡</text><text x="{bx:.1f}" y="{zY-8:.1f}" fill="#F0B429" font-size="10" text-anchor="middle" font-weight="800">${be:.2f}</text><circle cx="{bx:.1f}" cy="{zY:.1f}" r="5" fill="#F0B429"/><circle cx="{bx:.1f}" cy="{zY:.1f}" r="9" fill="#F0B429" opacity="0.2"/>'
                cur_x=cx(chain_cur)
                cur_svg=f'<text x="{cur_x:.1f}" y="16" fill="#3B82F6" font-size="9" text-anchor="middle">現價${chain_cur}</text>' if lo<chain_cur<hi else ""
                # profit/loss labels at bottom — direction depends on strategy
                profit_right = cur_strat in ("bull","call")
                px1=W-padX-4 if profit_right else padX+4
                pa1="end" if profit_right else "start"
                lx1=padX+4 if profit_right else W-padX-4
                la1="start" if profit_right else "end"
                mp_txt="∞" if unlimited else f"+${maxP:.0f}"
                bottom_labels=f'<text x="{px1}" y="{H-16}" fill="#4ADE80" font-size="8" font-weight="700" text-anchor="{pa1}">最大獲利</text><text x="{px1}" y="{H-5}" fill="#4ADE80" font-size="11" font-weight="800" text-anchor="{pa1}">{mp_txt}</text><text x="{lx1}" y="{H-16}" fill="#F87171" font-size="8" font-weight="700" text-anchor="{la1}">最大虧損</text><text x="{lx1}" y="{H-5}" fill="#F87171" font-size="11" font-weight="800" text-anchor="{la1}">${minP:.0f}</text>'
                svg=f'''<svg viewBox="0 0 {W} {H}" style="width:100%;height:230px;display:block;background:#141414;border-radius:12px;margin-top:6px">
                  <clipPath id="cp_p"><rect x="{padX}" y="{padTop}" width="{W-2*padX}" height="{max(zY-padTop,0):.1f}"/></clipPath>
                  <clipPath id="cp_l"><rect x="{padX}" y="{zY:.1f}" width="{W-2*padX}" height="{max(plotH-(zY-padTop),0):.1f}"/></clipPath>
                  <line x1="{padX}" y1="{zY:.1f}" x2="{W-padX}" y2="{zY:.1f}" stroke="#333" stroke-width="1" stroke-dasharray="4 3"/>
                  {tick_svgs}
                  {cur_svg}
                  <path d="{fill_d}" fill="#4ADE80" opacity="0.18" clip-path="url(#cp_p)"/>
                  <path d="{fill_d}" fill="#F87171" opacity="0.18" clip-path="url(#cp_l)"/>
                  <path d="{line_d}" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cp_p)"/>
                  <path d="{line_d}" fill="none" stroke="#F87171" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cp_l)"/>
                  {strike_svgs}
                  {be_svg}
                  {bottom_labels}
                </svg>'''
                st.markdown(svg, unsafe_allow_html=True)

                if st.button("⭐ 收藏這個組合", key="chain_save", use_container_width=True):
                    combo = {"type":cur_strat,"ticker":chain_ticker,"currentPrice":chain_cur,"expiry":selected_expiry}
                    for leg_key,leg_val in legs.items():
                        if leg_key=="buyCall":  combo["buyStrike"]=leg_val["strike"]; combo["buyPremium"]=leg_val["prem"]
                        if leg_key=="sellCall": combo["sellStrike"]=leg_val["strike"]; combo["sellPremium"]=leg_val["prem"]
                        if leg_key=="buyPut":   combo["buyStrike"]=leg_val["strike"]; combo["buyPremium"]=leg_val["prem"]
                        if leg_key=="sellPut":  combo["sellStrike"]=leg_val["strike"]; combo["sellPremium"]=leg_val["prem"]
                        if leg_key in ("buyCall","buyPut"):
                            combo["breakeven"]=round(be,2) if be else None
                            combo["maxLoss"]=round(cost)
                            combo["maxProfit"]=None if unlimited else round(maxP)
                    add_fav(combo)
                    st.success("已收藏！到「我的組合」查看")
    elif chain_ticker:
        st.info("輸入股票代號後會自動載入到期日和期權鏈")

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
      <div style="font-size:12px;color:#555;line-height:1.5">AI 讀取截圖數字，程式精算損益<br>自動排除盈虧比過低的組合，以「不易賠錢」優先</div>
    </div>
    """, unsafe_allow_html=True)
    ec1, ec2 = st.columns(2)
    scan_ticker = ec1.text_input("股票代號", placeholder="DKNG / ORCL", key="stk").upper()
    scan_expiry = ec2.text_input("選擇權到期日", placeholder="2026-08-21", key="exp")
    scan_info = None
    scan_price = None
    if scan_ticker:
        scan_info = stock_info_card(scan_ticker)
        scan_price = scan_info.get("price") if scan_info else None

    uploaded_files = st.file_uploader("上傳截圖（最多3張）", type=["png","jpg","jpeg","webp"], accept_multiple_files=True)

    all_b64s = []
    if uploaded_files:
        all_b64s = [compress_image(f) for f in uploaded_files[:3]]
        with st.expander(f"📷 已上傳 {len(uploaded_files[:3])} 張圖片（點擊查看）"):
            cols = st.columns(min(len(uploaded_files),3))
            for i, f in enumerate(uploaded_files[:3]):
                with cols[i]: st.image(f, use_container_width=True)

        if st.button("🤖  AI 分析最佳組合", key="scan_btn"):
            if not api_key:
                st.error("請先設定 API Key")
            else:
                with st.spinner("AI 讀取數據中..."):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        # STEP 1: AI ONLY reads the option chain numbers
                        read_prompt = """你是期權鏈數據讀取員。仔細讀取這些截圖中的所有數據。

對每個行權價，讀取：
- Call 的賣盤價（ask）和買盤價（bid）
- Put 的賣盤價（ask）和買盤價（bid）

只回純JSON，不要任何說明或計算：
{"currentPrice": 29.00, "rows": [{"strike":17.5,"callBid":11.45,"callAsk":12.90,"putBid":0.05,"putAsk":0.18},{"strike":20,"callBid":8.95,"callAsk":10.05,"putBid":0.22,"putAsk":0.34}]}

讀不到的值填null。strike必須是數字。把所有看得到的行權價都列出來。"""
                        content_parts = [{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b}} for b in all_b64s]
                        content_parts.append({"type":"text","text":read_prompt})
                        msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=2000, messages=[{"role":"user","content":content_parts}])
                        text = msg.content[0].text.strip()
                        m = re.search(r'\{[\s\S]*\}', text)
                        if not m:
                            st.error("讀取失敗：" + text[:300])
                        else:
                            chain = json.loads(m.group())
                            cur = scan_price or chain.get("currentPrice", 0)
                            rows = chain.get("rows", [])
                            st.session_state["scan_result"] = compute_strategies(rows, cur, scan_ticker, scan_expiry)
                    except Exception as e:
                        st.error(f"分析失敗：{e}")

    # Display results from session
    if st.session_state.get("scan_result"):
        render_scan_results(st.session_state["scan_result"])

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
