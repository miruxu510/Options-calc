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
.stTabs [data-baseweb="tab"] { background:transparent!important;border-radius:100px;color:#666;font-size:13px;font-weight:600;padding:8px 12px;border:none!important; }
.stTabs [aria-selected="true"] { background:#F0F0F0!important;color:#000!important;border-radius:100px; }
.stTabs [data-baseweb="tab-highlight"],[data-baseweb="tab-border"] { display:none; }
.stTextInput>div>div,.stNumberInput>div>div>div { background:#141414!important;border:none!important;border-radius:12px!important; }
.stTextInput input,.stNumberInput input { background:#141414!important;border:none!important;border-radius:12px!important;color:#F0F0F0!important;font-size:15px!important;font-weight:500!important;padding:12px 14px!important; }
.stTextInput label,.stNumberInput label,.stSelectbox label { color:#555!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }
.stSelectbox>div>div { background:#141414!important;border:none!important;border-radius:12px!important;color:#F0F0F0!important;font-size:14px!important;font-weight:600!important; }
.stButton>button { background:#22C55E!important;color:#000!important;border:none!important;border-radius:100px!important;font-size:14px!important;font-weight:700!important;padding:12px 20px!important;width:100%!important; }
[data-testid="stMetric"] { background:#141414;border:none;border-radius:12px;padding:12px; }
[data-testid="stMetricLabel"] { font-size:10px!important;color:#555!important;font-weight:700!important;text-transform:uppercase;letter-spacing:0.8px; }
[data-testid="stMetricValue"] { font-size:18px!important;font-weight:700!important;color:#F0F0F0!important; }
[data-testid="stMetricDelta"] { display:none; }
[data-testid="stFileUploader"] { background:#141414;border:1.5px dashed #333;border-radius:12px;padding:8px; }
[data-testid="stExpander"] { background:#141414!important;border:none!important;border-radius:12px!important;margin-bottom:8px;overflow:hidden; }
[data-testid="stExpander"] summary { background:#141414!important;color:#F0F0F0!important;font-weight:600!important;padding:12px 14px!important;font-size:13px!important; }
[data-testid="stExpander"]>div>div { background:#0F0F0F!important;border-top:1px solid #222!important; }
.stSuccess { background:#0D1F14!important;border:1px solid #22C55E!important;border-radius:10px!important;color:#22C55E!important; }
.stError { background:#1F0D0D!important;border:1px solid #EF4444!important;border-radius:10px!important;color:#EF4444!important; }
.stInfo { background:#0D1421!important;border:1px solid #3B82F6!important;border-radius:10px!important; }
hr { border-color:#1A1A1A!important;margin:16px 0!important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding:22px 0 16px;text-align:center;border-bottom:1px solid #1A1A1A;margin:0 -16px 18px">
  <div style="font-size:11px;color:#444;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px">OPTIONS</div>
  <div style="font-size:26px;font-weight:900;letter-spacing:-1px">Strategy Pro</div>
</div>
""", unsafe_allow_html=True)

api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── Helpers ───────────────────────────────────────────
def fmt(v):
    if v is None: return "N/A"
    return f"{v:.2f}" if isinstance(v,(int,float)) else str(v)

def fmtm(v):
    if v is None: return "N/A"
    return f"{v:.0f}" if isinstance(v,(int,float)) and float(v).is_integer() else f"{v:.2f}"

def stars(n):
    n = int(n or 3)
    return "".join("★" if i<n else "☆" for i in range(5))

def compress_image(uf):
    img = Image.open(uf)
    if img.width > 1200:
        img = img.resize((1200, int(img.height*1200/img.width)), Image.LANCZOS)
    if img.mode != "RGB": img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=75); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# ── yfinance ─────────────────────────────────────────
@st.cache_data(ttl=120)
def get_stock_info(symbol):
    if not HAS_YF or not symbol: return {}
    out = {"price":None,"target":None,"next_er":None,"last_er":None}
    try:
        t = yf.Ticker(symbol)
        try:
            fi = t.fast_info
            out["price"] = round(float(fi.get("lastPrice") or fi.get("last_price") or 0), 2) or None
        except: pass
        if not out["price"]:
            h = t.history(period="1d")
            if not h.empty: out["price"] = round(float(h["Close"].iloc[-1]), 2)
        try:
            info = t.info
            tp = info.get("targetMeanPrice")
            if tp: out["target"] = round(float(tp), 2)
        except: pass
        try:
            cal = t.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed:
                    out["next_er"] = str(ed[0] if isinstance(ed,list) else ed)
        except: pass
        try:
            import pandas as pd
            edf = t.earnings_dates
            if edf is not None and not edf.empty:
                now = pd.Timestamp.now(tz=edf.index.tz)
                past = edf[edf.index <= now]
                if not past.empty: out["last_er"] = past.index[0].strftime("%Y-%m-%d")
        except: pass
    except: pass
    return out

@st.cache_data(ttl=300)
def get_chain_expiries(symbol):
    if not HAS_YF or not symbol: return []
    try: return list(yf.Ticker(symbol).options)
    except: return []

@st.cache_data(ttl=120)
def get_chain_data(symbol, expiry):
    if not HAS_YF or not symbol or not expiry: return None, []
    try:
        t = yf.Ticker(symbol)
        opt = t.option_chain(expiry)
        try:
            fi = t.fast_info
            cur = round(float(fi.get("lastPrice") or fi.get("last_price") or 0), 2)
        except: cur = 0
        calls = opt.calls[["strike","bid","ask"]].rename(columns={"bid":"callBid","ask":"callAsk"})
        puts  = opt.puts[["strike","bid","ask"]].rename(columns={"bid":"putBid","ask":"putAsk"})
        merged = calls.merge(puts, on="strike", how="outer").sort_values("strike")
        return cur, merged.to_dict("records")
    except: return None, []

def stock_info_card(symbol):
    info = get_stock_info(symbol)
    if not info or not info.get("price"): return info
    price=info["price"]; target=info.get("target"); ner=info.get("next_er"); ler=info.get("last_er")
    upside=((target-price)/price*100) if target else None
    uc="#22C55E" if upside and upside>=0 else "#EF4444"
    target_html=f'<div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 12px"><div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">分析師目標價</div><div style="display:flex;align-items:baseline;gap:6px"><span style="font-size:17px;font-weight:700;color:#F0F0F0">${target:.2f}</span><span style="font-size:12px;font-weight:700;color:{uc}">{("+" if upside>=0 else "")}{upside:.1f}%</span></div></div>' if target else ""
    st.markdown(f'''
    <div style="background:#141414;border-radius:14px;padding:14px;margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
        <div><div style="font-size:20px;font-weight:900;letter-spacing:-0.5px">{symbol}</div>
        <div style="font-size:11px;color:#555;margin-top:1px">即時連線</div></div>
        <div style="text-align:right"><div style="font-size:24px;font-weight:900;letter-spacing:-1px">${price:.2f}</div>
        <div style="font-size:10px;color:#555;font-weight:600">現價</div></div>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:8px">{target_html}</div>
      <div style="display:flex;gap:8px">
        <div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 12px">
          <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">下次財報</div>
          <div style="font-size:14px;font-weight:700;color:#F59E0B">{ner or "—"}</div></div>
        <div style="flex:1;background:#1C1C1C;border-radius:10px;padding:10px 12px">
          <div style="font-size:9px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">上次財報</div>
          <div style="font-size:14px;font-weight:700;color:#888">{ler or "—"}</div></div>
      </div>
    </div>''', unsafe_allow_html=True)
    return info

# ── P&L helpers ──────────────────────────────────────
def pnl_at(legs, price):
    v = 0
    if "buyCall"  in legs: v += max(price-legs["buyCall"]["strike"],0)*100  - legs["buyCall"]["prem"]*100
    if "sellCall" in legs: v -= max(price-legs["sellCall"]["strike"],0)*100  - legs["sellCall"]["prem"]*100
    if "buyPut"   in legs: v += max(legs["buyPut"]["strike"]-price,0)*100   - legs["buyPut"]["prem"]*100
    if "sellPut"  in legs: v -= max(legs["sellPut"]["strike"]-price,0)*100  - legs["sellPut"]["prem"]*100
    return v

def find_be(legs, cur):
    strikes = [l["strike"] for l in legs.values()]
    lo = min(strikes+[cur])*0.75; hi = max(strikes+[cur])*1.35
    pts = [lo+(hi-lo)*i/600 for i in range(601)]
    pnls = [pnl_at(legs,p) for p in pts]
    for i in range(1,len(pts)):
        if (pnls[i-1]<=0 and pnls[i]>0) or (pnls[i-1]>=0 and pnls[i]<0):
            # linear interpolation
            frac = abs(pnls[i-1])/(abs(pnls[i-1])+abs(pnls[i]))
            return pts[i-1]+frac*(pts[i]-pts[i-1])
    return None


def analyze_legs(legs, strat=None):
    if not legs:
        return {"max_profit": None, "max_loss": 0, "cost": 0, "unlimited": False}
    debit = 0
    credit = 0
    if "buyCall" in legs: debit += legs["buyCall"]["prem"] * 100
    if "buyPut" in legs: debit += legs["buyPut"]["prem"] * 100
    if "sellCall" in legs: credit += legs["sellCall"]["prem"] * 100
    if "sellPut" in legs: credit += legs["sellPut"]["prem"] * 100
    net_debit = debit - credit

    if "buyCall" in legs and "sellCall" in legs and len(legs) == 2:
        width = abs(legs["sellCall"]["strike"] - legs["buyCall"]["strike"]) * 100
        max_loss = max(net_debit, 0)
        max_profit = max(width - net_debit, 0)
        return {"max_profit": max_profit, "max_loss": max_loss, "cost": max_loss, "unlimited": False}

    if "buyPut" in legs and "sellPut" in legs and len(legs) == 2:
        width = abs(legs["buyPut"]["strike"] - legs["sellPut"]["strike"]) * 100
        max_loss = max(net_debit, 0)
        max_profit = max(width - net_debit, 0)
        return {"max_profit": max_profit, "max_loss": max_loss, "cost": max_loss, "unlimited": False}

    if ("buyCall" in legs or "buyPut" in legs) and len(legs) == 1:
        return {"max_profit": None, "max_loss": max(net_debit, 0), "cost": max(net_debit, 0), "unlimited": True}

    strikes = [l["strike"] for l in legs.values()]
    lo = max(0, min(strikes) * 0.25)
    hi = max(strikes) * 2.5
    pts = [lo + (hi - lo) * i / 500 for i in range(501)]
    vals = [pnl_at(legs, x) for x in pts]
    return {"max_profit": max(vals), "max_loss": abs(min(vals)), "cost": abs(min(vals)), "unlimited": False}

def scenario_prices(cur, legs):
    strikes = sorted({float(v["strike"]) for v in legs.values()})
    base = cur if cur and cur > 0 else (strikes[0] if strikes else 0)
    if base <= 0:
        return strikes
    step = 1 if base < 80 else (5 if base < 250 else 10)
    start = math.floor((base * 0.8) / step) * step
    end = math.ceil((base * 1.35) / step) * step
    prices = [round(start + step * i, 2) for i in range(int((end - start) / step) + 1)]
    for x in strikes + [base]:
        prices.append(round(x, 2))
    return sorted(set([x for x in prices if x > 0]))

def pnl_table_html(legs, cur, cost):
    rows = []
    denom = cost if cost and cost > 0 else 1
    for price in scenario_prices(cur, legs):
        pnl = pnl_at(legs, price)
        pct = pnl / denom * 100
        color = "#22C55E" if pnl >= 0 else "#EF4444"
        sign = "+" if pnl >= 0 else ""
        rows.append(f'''<tr>
          <td style="padding:8px 10px;border-bottom:1px solid #202020;color:#E5E7EB;font-weight:700">${fmt(price)}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #202020;text-align:right;color:{color};font-weight:800">{sign}${fmtm(pnl)}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #202020;text-align:right;color:{color};font-weight:800">{sign}{pct:.0f}%</td>
        </tr>''')
    return f'''<div style="background:#141414;border-radius:14px;overflow:hidden;margin-top:10px;border:1px solid #242424">
      <div style="padding:10px 12px;font-size:12px;font-weight:800;color:#F0F0F0;border-bottom:1px solid #242424">損益表</div>
      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead><tr style="background:#1C1C1C;color:#888;font-size:10px;text-transform:uppercase;letter-spacing:.5px">
          <th style="padding:8px 10px;text-align:left">股價</th><th style="padding:8px 10px;text-align:right">損益金額</th><th style="padding:8px 10px;text-align:right">報酬率</th>
        </tr></thead><tbody>{''.join(rows)}</tbody>
      </table>
    </div>'''


def make_svg(legs, cur, strat):
    metrics = analyze_legs(legs, strat)
    unlimited = metrics.get("unlimited", False)
    profit_right = strat in ("bull","call")
    be = find_be(legs, cur)
    strikes = [l["strike"] for l in legs.values()]
    safe_cur = cur if cur and cur>0 else strikes[0]
    center = be if be else safe_cur
    all_pts = strikes + [safe_cur] + ([be] if be else [])
    span = max(max(all_pts)-min(all_pts), safe_cur*0.16) * 1.7
    lo = max(0, center - span*0.55); hi = center + span*0.55
    if hi <= lo: hi = lo + max(1, safe_cur*0.5)
    pts = [lo+(hi-lo)*i/240 for i in range(241)]
    pnls = [pnl_at(legs,p) for p in pts]
    maxV=max(pnls); minV=min(pnls)
    if metrics.get("max_profit") is not None: maxV = max(maxV, metrics["max_profit"])
    if metrics.get("max_loss") is not None: minV = min(minV, -metrics["max_loss"])
    W=380; H=250; pX=14; pTop=30; pBot=10; labelH=38
    plotH = H - pTop - pBot - labelH
    vpad=max((maxV-minV)*0.18, 50); vTop=maxV+vpad; vBot=minV-vpad; vRange=(vTop-vBot) or 1
    def cx(p): return pX+((p-lo)/(hi-lo))*(W-2*pX)
    def cy(v): return pTop+(vTop-v)/vRange*plotH
    zY=cy(0)
    lineD=" ".join(f"{'M' if i==0 else 'L'}{cx(pts[i]):.1f},{cy(pnls[i]):.1f}" for i in range(len(pts)))
    fillD=f"{lineD} L{cx(hi):.1f},{zY:.1f} L{cx(lo):.1f},{zY:.1f} Z"
    ticks=""
    for i in range(6):
        p=lo+(hi-lo)*i/5; tx=cx(p)
        ticks+=f'<line x1="{tx:.1f}" y1="{zY:.1f}" x2="{tx:.1f}" y2="{zY+4:.1f}" stroke="#444" stroke-width="0.8"/><text x="{tx:.1f}" y="{zY+14:.1f}" fill="#555" font-size="7.5" text-anchor="middle">${p:.0f}</text>'
    guide_svg=""
    def guide(price, color, label, yoff=0):
        if price is None or not (lo < price < hi): return ""
        x=cx(price)
        return f'<line x1="{x:.1f}" y1="{pTop}" x2="{x:.1f}" y2="{pTop+plotH}" stroke="{color}" stroke-width="1.2" stroke-dasharray="5 4" opacity=".95"/><rect x="{x-32:.1f}" y="{8+yoff:.1f}" width="64" height="15" rx="4" fill="#0D0D0D" opacity="0.94"/><text x="{x:.1f}" y="{19+yoff:.1f}" fill="{color}" font-size="8.5" text-anchor="middle" font-weight="800">{label}</text>'
    guide_svg += guide(safe_cur, "#3B82F6", f"現價 ${safe_cur:.0f}", 0)
    guide_svg += guide(be, "#F0B429", f"BE ${be:.1f}" if be else "", 17)
    stk_svg=""
    for leg_k,leg_v in legs.items():
        sk=leg_v["strike"]
        if not (lo<sk<hi): continue
        dy=cy(pnl_at(legs,sk)); sx=cx(sk)
        mc="#60A5FA" if "buy" in leg_k else "#FB923C"
        lbl=f"{'買' if 'buy' in leg_k else '賣'} ${sk:g}"
        stk_svg += f'<line x1="{sx:.1f}" y1="{pTop}" x2="{sx:.1f}" y2="{pTop+plotH}" stroke="{mc}" stroke-width="1" stroke-dasharray="3 4" opacity=".65"/>'
        above=dy>H*0.45; by2=dy-27 if above else dy+11
        stk_svg+=f'<rect x="{sx-28:.1f}" y="{by2:.1f}" width="56" height="14" rx="3" fill="#0D0D0D" opacity="0.92"/><text x="{sx:.1f}" y="{by2+11:.1f}" fill="{mc}" font-size="8.5" text-anchor="middle" font-weight="700">{lbl}</text><circle cx="{sx:.1f}" cy="{dy:.1f}" r="4.5" fill="{mc}"/><circle cx="{sx:.1f}" cy="{dy:.1f}" r="8" fill="{mc}" opacity="0.18"/>'
    bY=H-labelH+16; bY2=H-labelH+30
    pX1=W-pX-4; pA1="end"; lX1=pX+4; lA1="start"
    if not profit_right: pX1,pA1,lX1,lA1=pX+4,"start",W-pX-4,"end"
    mp_txt="無限 ∞" if unlimited else f"+${metrics.get('max_profit', maxV):.0f}"
    ml_txt=f"-${metrics.get('max_loss', abs(minV)):.0f}"
    bot=f'<text x="{pX1}" y="{bY}" fill="#4ADE80" font-size="8" font-weight="700" text-anchor="{pA1}">最大獲利</text><text x="{pX1}" y="{bY2}" fill="#4ADE80" font-size="12" font-weight="800" text-anchor="{pA1}">{mp_txt}</text><text x="{lX1}" y="{bY}" fill="#F87171" font-size="8" font-weight="700" text-anchor="{lA1}">最大虧損</text><text x="{lX1}" y="{bY2}" fill="#F87171" font-size="12" font-weight="800" text-anchor="{lA1}">{ml_txt}</text>'
    return f'''<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block;background:#141414;border-radius:14px;margin-top:8px;border:1px solid #242424">
  <clipPath id="cpp"><rect x="{pX}" y="{pTop}" width="{W-2*pX}" height="{max(zY-pTop,0):.1f}"/></clipPath>
  <clipPath id="cpl"><rect x="{pX}" y="{zY:.1f}" width="{W-2*pX}" height="{max(plotH-(zY-pTop),0):.1f}"/></clipPath>
  <line x1="{pX}" y1="{zY:.1f}" x2="{W-pX}" y2="{zY:.1f}" stroke="#2A2A2A" stroke-width="1" stroke-dasharray="4 3"/>
  {ticks}{guide_svg}
  <path d="{fillD}" fill="#4ADE80" opacity="0.18" clip-path="url(#cpp)"/>
  <path d="{fillD}" fill="#F87171" opacity="0.18" clip-path="url(#cpl)"/>
  <path d="{lineD}" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cpp)"/>
  <path d="{lineD}" fill="none" stroke="#F87171" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cpl)"/>
  {stk_svg}{bot}
</svg>'''


# ── Local storage / favorites ─────────────────────────
if HAS_LS:
    try: ls = LocalStorage()
    except: ls = None
else: ls = None

def load_favs():
    if ls:
        try:
            raw = ls.getItem("opt_favs")
            return json.loads(raw) if raw else []
        except: return []
    return st.session_state.get("_favs", [])

def save_favs(favs):
    if ls:
        try: ls.setItem("opt_favs", json.dumps(favs))
        except: pass
    st.session_state["_favs"] = favs

def add_fav(combo):
    favs = load_favs()
    combo["_id"] = f"{combo.get('ticker','')}_{combo.get('type','')}_{len(favs)}"
    favs.insert(0, combo); save_favs(favs)

# ── compute_strategies ────────────────────────────────
def compute_strategies(rows, cur, ticker, expiry):
    valid = [r for r in rows if r.get("strike") is not None]
    valid.sort(key=lambda r: r["strike"])
    bulls, bears, calls = [], [], []
    for i in range(len(valid)):
        for j in range(i+1, len(valid)):
            lo, hi = valid[i], valid[j]
            ba=lo.get("callAsk"); sb=hi.get("callBid")
            if ba and sb and ba>0:
                nc=ba-sb
                if nc>0:
                    sp=hi["strike"]-lo["strike"]; maxP=(sp-nc)*100; maxL=nc*100
                    if maxP>0 and maxL>0 and maxP/maxL>=1.0:
                        if cur and (lo["strike"]-cur)/cur<=0.10:
                            be=lo["strike"]+nc; ror=maxP/maxL*100
                            pg=max((be-cur)/cur,0) if cur else 0
                            safety=(1/(1+pg*5))*100*0.5+min(ror,300)/3*0.3+(1/(1+maxL/200))*100*0.2
                            bulls.append({"type":"bull","buyStrike":lo["strike"],"buyPremium":round(ba,2),"sellStrike":hi["strike"],"sellPremium":round(sb,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_safety":safety})
            ba=hi.get("putAsk"); sb=lo.get("putBid")
            if ba and sb and ba>0:
                nc=ba-sb
                if nc>0:
                    sp=hi["strike"]-lo["strike"]; maxP=(sp-nc)*100; maxL=nc*100
                    if maxP>0 and maxL>0 and maxP/maxL>=1.0:
                        if cur and (cur-hi["strike"])/cur<=0.10:
                            be=hi["strike"]-nc; ror=maxP/maxL*100
                            pg=max((cur-be)/cur,0) if cur else 0
                            safety=(1/(1+pg*5))*100*0.5+min(ror,300)/3*0.3+(1/(1+maxL/200))*100*0.2
                            bears.append({"type":"bear","buyStrike":hi["strike"],"buyPremium":round(ba,2),"sellStrike":lo["strike"],"sellPremium":round(sb,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_safety":safety})
    for r in valid:
        ba=r.get("callAsk")
        if ba and ba>0 and cur and abs(r["strike"]-cur)/cur<=0.12:
            be=r["strike"]+ba; target=cur*1.20
            maxP=(target-r["strike"]-ba)*100; maxL=ba*100
            if maxP>0:
                ror=maxP/maxL*100; pg=max((be-cur)/cur,0) if cur else 0
                safety=(1/(1+pg*4))*100*0.6+min(ror,200)/2*0.2+(1/(1+maxL/300))*100*0.2
                calls.append({"type":"call","strike":r["strike"],"premium":round(ba,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_safety":safety})
    bulls.sort(key=lambda x:-x["_safety"]); bears.sort(key=lambda x:-x["_safety"]); calls.sort(key=lambda x:-x["_safety"])
    B,R,L=bulls[:3],bears[:3],calls[:2]
    def assign(items):
        for it in items:
            it["stars"]=5 if it["_safety"]>=90 else 4 if it["_safety"]>=70 else 3 if it["_safety"]>=50 else 2
            pros=[]; cons=[]
            if it["rr"]>=2: pros.append("盈虧比佳")
            if it["maxLoss"]<=150: pros.append("成本低")
            bd=abs(it["breakeven"]-cur)/cur*100 if cur else 0
            if bd<=5: pros.append("接近現價")
            if it["rr"]<1.5: cons.append("盈虧比偏低")
            if it["maxLoss"]>300: cons.append("成本較高")
            if bd>8: cons.append(f"需變動{bd:.0f}%")
            it["pros"]="、".join(pros) or "風險可控"; it["cons"]="、".join(cons) or "注意時間價值"
    assign(B); assign(R); assign(L)
    everything=sorted(B+R+L,key=lambda x:-x["_safety"])
    for i,t in enumerate(everything[:3]): t["_medal"]=["🥇","🥈","🥉"][i]
    return {"cur":cur,"ticker":ticker,"expiry":expiry,"bull":B,"bear":R,"call":L,"top3":everything[:3]}

def render_combo(it, cur, strat_type, save_key=None):
    mp=it.get("maxProfit",0); ml=it.get("maxLoss",0); be=it.get("breakeven",0); ror=it.get("ror",0)
    unlimited=strat_type in ("call","put")
    mp_label="無限 ∞" if unlimited else f"+${fmtm(mp)}"
    st.markdown(f'''<div style="display:flex;gap:6px;margin:8px 0">
      <div style="flex:1;background:#1C1C1C;border-radius:9px;padding:9px 4px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:2px">最大獲利</div>
        <div style="font-size:14px;font-weight:700;color:#22C55E">{mp_label}</div></div>
      <div style="flex:1;background:#1C1C1C;border-radius:9px;padding:9px 4px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:2px">最大虧損</div>
        <div style="font-size:14px;font-weight:700;color:#EF4444">-${fmtm(ml)}</div></div>
      <div style="flex:1;background:#1C1C1C;border-radius:9px;padding:9px 4px;text-align:center">
        <div style="font-size:9px;color:#F59E0B;font-weight:700;margin-bottom:2px">損益平衡</div>
        <div style="font-size:14px;font-weight:700;color:#F59E0B">${fmt(be)}</div></div>
      <div style="flex:1;background:#1C1C1C;border-radius:9px;padding:9px 4px;text-align:center">
        <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:2px">報酬率</div>
        <div style="font-size:14px;font-weight:700;color:#F0F0F0">{"∞" if unlimited else f"{ror:.0f}%"}</div></div>
    </div>''', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center;margin:4px 0;color:#F0B429;font-size:13px">{stars(it.get("stars",3))}</div>', unsafe_allow_html=True)
    if it.get("pros") or it.get("cons"):
        st.markdown(f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
          <div style="background:#0D1F14;border:1px solid #1A3A24;border-radius:9px;padding:7px 10px">
            <div style="font-size:9px;color:#22C55E;font-weight:700;margin-bottom:2px">✓ 優點</div>
            <div style="font-size:11px;color:#AAA">{it.get("pros","")}</div></div>
          <div style="background:#1F0D0D;border:1px solid #3A1A1A;border-radius:9px;padding:7px 10px">
            <div style="font-size:9px;color:#EF4444;font-weight:700;margin-bottom:2px">✗ 缺點</div>
            <div style="font-size:11px;color:#AAA">{it.get("cons","")}</div></div>
        </div>''', unsafe_allow_html=True)
    # Build legs for chart
    legs = {}
    if strat_type in ("bull","bear"):
        if strat_type=="bull":
            legs={"buyCall":{"strike":it["buyStrike"],"prem":it["buyPremium"]},"sellCall":{"strike":it["sellStrike"],"prem":it["sellPremium"]}}
        else:
            legs={"buyPut":{"strike":it["buyStrike"],"prem":it["buyPremium"]},"sellPut":{"strike":it["sellStrike"],"prem":it["sellPremium"]}}
    elif strat_type=="call":
        legs={"buyCall":{"strike":it["strike"],"prem":it["premium"]}}
    elif strat_type=="put":
        legs={"buyPut":{"strike":it["strike"],"prem":it["premium"]}}
    if legs:
        st.markdown(make_svg(legs, cur, strat_type), unsafe_allow_html=True)
    if save_key and st.button("⭐ 收藏", key=save_key):
        combo=dict(it); combo["type"]=strat_type
        add_fav(combo); st.success("已收藏！")

# ── Tabs ──────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(["選股計算", "比較", "AI 掃描", "我的組合", "說明"])

# ══════ TAB 1: CHAIN PICKER ══════
with tab1:
    t1c1, t1c2 = st.columns([2,1])
    chain_ticker = t1c1.text_input("股票代號", placeholder="ORCL / DKNG / MU", key="ct").upper()
    expiries = get_chain_expiries(chain_ticker) if chain_ticker else []
    selected_expiry = t1c2.selectbox("到期日", expiries if expiries else ["—"], key="cexp",
        label_visibility="visible") if expiries else None

    if chain_ticker:
        stock_info_card(chain_ticker)

    if chain_ticker and selected_expiry and selected_expiry != "—":
        chain_cur, chain_rows = get_chain_data(chain_ticker, selected_expiry)
        if not chain_rows:
            st.error("抓不到期權鏈，請稍後再試")
        else:
            safe_cur = chain_cur if chain_cur and chain_cur>0 else 0
            STRAT_MAP = {"看漲價差 Bull Call":"bull","看跌價差 Bear Put":"bear","單買 Call":"call","單買 Put":"put"}
            NEEDS = {"bull":["buyCall","sellCall"],"bear":["buyPut","sellPut"],"call":["buyCall"],"put":["buyPut"]}
            LEG_LABEL = {"buyCall":"買入 Call","sellCall":"賣出 Call","buyPut":"買入 Put","sellPut":"賣出 Put"}
            STRAT_COLOR = {"bull":"#3B82F6","bear":"#EF4444","call":"#22C55E","put":"#F59E0B"}
            if "chain_strat" not in st.session_state: st.session_state["chain_strat"]="bull"
            if "chain_legs" not in st.session_state: st.session_state["chain_legs"]={}

            chosen = st.selectbox("策略", list(STRAT_MAP.keys()), key="chain_strat_sel", label_visibility="collapsed")
            new_sk = STRAT_MAP[chosen]
            if new_sk != st.session_state["chain_strat"]:
                st.session_state["chain_strat"]=new_sk; st.session_state["chain_legs"]={}; st.rerun()

            cur_strat = st.session_state["chain_strat"]
            cur_legs  = st.session_state["chain_legs"]
            needs     = NEEDS[cur_strat]
            next_leg  = next((n for n in needs if n not in cur_legs), None)
            sc        = STRAT_COLOR[cur_strat]

            # Leg status
            leg_html=""
            for n in needs:
                filled=n in cur_legs
                val=f"${fmt(cur_legs[n]['strike'])} @ ${fmt(cur_legs[n]['prem'])}" if filled else "點下方選"
                col_c="#22C55E" if filled else "#555"
                brd=f"1.5px solid {sc}" if (not filled and n==next_leg) else "1px solid #2A2A2A"
                leg_html+=f'<div style="flex:1;background:#1C1C1C;border:{brd};border-radius:10px;padding:8px 10px"><div style="font-size:9px;color:#555;font-weight:700;margin-bottom:2px">{LEG_LABEL[n]}</div><div style="font-size:13px;font-weight:700;color:{col_c}">{val}</div></div>'
            st.markdown(f'<div style="display:flex;gap:6px;margin:10px 0 6px">{leg_html}</div>', unsafe_allow_html=True)

            c_reset, _ = st.columns([1,3])
            if cur_legs and c_reset.button("↺ 重選", key="reset"):
                st.session_state["chain_legs"]={};st.rerun()

            if next_leg:
                st.markdown(f'<div style="font-size:11px;color:{sc};font-weight:600;margin-bottom:6px">👇 點選「{LEG_LABEL[next_leg]}」的行權價</div>', unsafe_allow_html=True)

            if next_leg:
                # Chain table — HTML display + selectbox to pick
                is_call_leg = next_leg and "Call" in next_leg
                is_put_leg  = next_leg and "Put"  in next_leg
                is_buy = next_leg and next_leg.startswith("buy")

                rows_html=""
                call_options=[]; put_options=[]
                for row in chain_rows:
                    strike=row.get("strike",0)
                    atm=safe_cur and abs(strike-safe_cur)<1.5
                    call_p=row.get("callAsk" if is_buy else "callBid")
                    put_p=row.get("putAsk" if is_buy else "putBid")
                    call_val=f"${fmt(call_p)}" if call_p else "—"
                    put_val=f"${fmt(put_p)}" if put_p else "—"
                    sk_str=f"{strike:.0f}" if strike==int(strike) else str(strike)
                    sk_color="#3B82F6" if atm else "#F0F0F0"
                    row_bg="rgba(59,130,246,0.05)" if atm else "transparent"

                    if is_call_leg and call_p:
                        call_cell=f'<td style="padding:5px 6px;text-align:center"><div style="background:#22C55E18;border:1px solid #22C55E55;border-radius:6px;padding:4px 2px;font-size:12px;font-weight:700;color:#22C55E">{call_val}</div></td>'
                        call_options.append((strike,call_p,call_val))
                    else:
                        call_cell=f'<td style="padding:5px 6px;text-align:center;font-size:11px;color:#3A3A3A">{call_val}</td>'

                    if is_put_leg and put_p:
                        put_cell=f'<td style="padding:5px 6px;text-align:center"><div style="background:#EF444418;border:1px solid #EF444455;border-radius:6px;padding:4px 2px;font-size:12px;font-weight:700;color:#EF4444">{put_val}</div></td>'
                        put_options.append((strike,put_p,put_val))
                    else:
                        put_cell=f'<td style="padding:5px 6px;text-align:center;font-size:11px;color:#3A3A3A">{put_val}</td>'

                    rows_html+=f'<tr style="background:{row_bg};border-bottom:1px solid #161616">{call_cell}<td style="padding:5px 4px;text-align:center;font-size:13px;font-weight:800;color:{sk_color}">{sk_str}</td>{put_cell}</tr>'

                st.markdown(f'''<div style="background:#1C1C1C;border-radius:12px;overflow:hidden;margin-bottom:10px">
                  <table style="width:100%;border-collapse:collapse">
                    <thead><tr style="background:#242424">
                      <th style="padding:7px;text-align:center;font-size:10px;color:#22C55E;font-weight:700;letter-spacing:0.5px">CALL</th>
                      <th style="padding:7px;text-align:center;font-size:10px;color:#555;font-weight:700">行權價</th>
                      <th style="padding:7px;text-align:center;font-size:10px;color:#EF4444;font-weight:700;letter-spacing:0.5px">PUT</th>
                    </tr></thead><tbody>{rows_html}</tbody></table></div>''', unsafe_allow_html=True)

                # Pick from highlighted options
                if next_leg and (call_options or put_options):
                    opts = call_options if is_call_leg else put_options
                    if opts:
                        idx = st.selectbox(
                            f"選擇 {LEG_LABEL[next_leg]}",
                            range(len(opts)),
                            format_func=lambda i: f"行權價 ${opts[i][0]}  ·  ${fmt(opts[i][1])}",
                            key=f"pick_{next_leg}"
                        )
                        if st.button(f"✓ 確認 {LEG_LABEL[next_leg]}", key=f"confirm_{next_leg}"):
                            s,p,_ = opts[idx]
                            st.session_state["chain_legs"][next_leg]={"strike":s,"prem":p}
                            st.rerun()

            # Show result
            if all(n in cur_legs for n in needs):
                legs = cur_legs
                be=find_be(legs,safe_cur)
                metrics = analyze_legs(legs, cur_strat)
                maxP = metrics.get("max_profit")
                cost = metrics.get("max_loss", 0)
                unlimited = metrics.get("unlimited", False)
                mp_label = "無限 ∞" if unlimited else f"+${fmtm(maxP)}"
                ror_label = "—" if unlimited or not cost else f"{(maxP / cost * 100):.0f}%"
                st.divider()
                st.markdown(f'''<div style="display:flex;gap:6px;margin-bottom:10px">
                  <div style="flex:1;background:#141414;border:1px solid #242424;border-radius:10px;padding:10px 4px;text-align:center">
                    <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:2px">最大獲利</div>
                    <div style="font-size:14px;font-weight:700;color:#22C55E">{mp_label}</div></div>
                  <div style="flex:1;background:#141414;border:1px solid #242424;border-radius:10px;padding:10px 4px;text-align:center">
                    <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:2px">最大虧損</div>
                    <div style="font-size:14px;font-weight:700;color:#EF4444">-${fmtm(cost)}</div></div>
                  <div style="flex:1;background:#141414;border:1px solid #242424;border-radius:10px;padding:10px 4px;text-align:center">
                    <div style="font-size:9px;color:#F59E0B;font-weight:700;margin-bottom:2px">損益平衡</div>
                    <div style="font-size:14px;font-weight:700;color:#F59E0B">${fmt(be) if be else "—"}</div></div>
                  <div style="flex:1;background:#141414;border:1px solid #242424;border-radius:10px;padding:10px 4px;text-align:center">
                    <div style="font-size:9px;color:#555;font-weight:700;margin-bottom:2px">報酬率</div>
                    <div style="font-size:14px;font-weight:700;color:#F0F0F0">{ror_label}</div></div>
                </div>''', unsafe_allow_html=True)
                st.markdown(make_svg(legs, safe_cur, cur_strat), unsafe_allow_html=True)
                st.markdown(pnl_table_html(legs, safe_cur, cost), unsafe_allow_html=True)
                if st.button("⭐ 收藏這個組合", key="chain_save"):
                    combo={"type":cur_strat,"ticker":chain_ticker,"currentPrice":safe_cur,"expiry":selected_expiry,"breakeven":round(be,2) if be else None,"maxLoss":round(cost),"maxProfit":None if unlimited else round(maxP or 0)}
                    for k,v in legs.items():
                        if k=="buyCall": combo["buyStrike"]=v["strike"]; combo["buyPremium"]=v["prem"]
                        if k=="sellCall": combo["sellStrike"]=v["strike"]; combo["sellPremium"]=v["prem"]
                        if k in ("buyPut","buyCall") and "Put" in k: combo["buyStrike"]=v["strike"]; combo["buyPremium"]=v["prem"]
                        if k=="sellPut": combo["sellStrike"]=v["strike"]; combo["sellPremium"]=v["prem"]
                    add_fav(combo); st.success("已收藏！到「我的組合」查看")
    elif chain_ticker and not expiries:
        st.info("載入到期日中...")

# ══════ TAB 2: COMPARE ══════
with tab2:
    c1,c2,c3=st.columns(3)
    cmp_ticker=c1.text_input("股票",key="cmp_t",placeholder="ORCL").upper()
    auto_price=get_stock_info(cmp_ticker).get("price") if cmp_ticker else None
    cmp_cur=c2.number_input("現價",key="cmp_c",min_value=0.0,format="%.2f",value=float(auto_price) if auto_price else 0.0)
    cmp_target=c3.number_input("目標價",key="cmp_tg",min_value=0.0,format="%.2f")
    if auto_price: st.markdown(f'<p style="font-size:11px;color:#22C55E;margin:-6px 0 8px">✓ {cmp_ticker} 現價 ${auto_price}</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">📈 Bull Call Spread</p>', unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    cbbs=c1.number_input("買入價",key="cbbs",min_value=0.0,format="%.2f"); cbbp=c2.number_input("買入金",key="cbbp",min_value=0.0,format="%.2f")
    cbss=c3.number_input("賣出價",key="cbss",min_value=0.0,format="%.2f"); cbsp=c4.number_input("賣出金",key="cbsp",min_value=0.0,format="%.2f")
    st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">📉 Bear Put Spread</p>', unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    cpbs=c1.number_input("買入價",key="cpbs",min_value=0.0,format="%.2f"); cpbp=c2.number_input("買入金",key="cpbp",min_value=0.0,format="%.2f")
    cpss=c3.number_input("賣出價",key="cpss",min_value=0.0,format="%.2f"); cpsp=c4.number_input("賣出金",key="cpsp",min_value=0.0,format="%.2f")
    st.markdown('<p style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:12px 0 6px">📞 單買 Call</p>', unsafe_allow_html=True)
    c1,c2=st.columns(2)
    ccks=c1.number_input("行權價",key="ccks",min_value=0.0,format="%.2f"); ccpp=c2.number_input("權利金",key="ccpp",min_value=0.0,format="%.2f")
    st.markdown("<br>",unsafe_allow_html=True)
    if st.button("比較三種策略",key="cmp_btn"):
        results={}
        def sp_pnl(t,p,bs,ss,nc,ml):
            sp=abs(bs-ss);mp=(sp-nc)*100
            if t=="bull": return -ml if p<=bs else (mp if p>=ss else ((p-bs)-nc)*100)
            else: return -ml if p>=bs else (mp if p<=ss else ((bs-p)-nc)*100)
        if cbbs and cbbp and cbss and cbsp:
            nc=cbbp-cbsp;sp=cbss-cbbs;ml=nc*100;mp=(sp-nc)*100;pat=sp_pnl("bull",cmp_target,cbbs,cbss,nc,ml)
            results["Bull Call"]={"最大獲利":f"+${fmtm(mp)}","最大虧損":f"-${fmtm(ml)}","損益平衡":f"${fmt(cbbs+nc)}","目標損益":f"{'+' if pat>=0 else ''}${fmtm(pat)}","報酬率":f"{mp/ml*100:.0f}%","_ror":mp/ml*100}
        if cpbs and cpbp and cpss and cpsp:
            nc=cpbp-cpsp;sp=cpbs-cpss;ml=nc*100;mp=(sp-nc)*100;pat=sp_pnl("bear",cmp_target,cpbs,cpss,nc,ml)
            results["Bear Put"]={"最大獲利":f"+${fmtm(mp)}","最大虧損":f"-${fmtm(ml)}","損益平衡":f"${fmt(cpbs-nc)}","目標損益":f"{'+' if pat>=0 else ''}${fmtm(pat)}","報酬率":f"{mp/ml*100:.0f}%","_ror":mp/ml*100}
        if ccks and ccpp:
            ml=ccpp*100; pat=(cmp_target-ccks-ccpp)*100 if cmp_target else 0
            results["單Call"]={"最大獲利":"∞","最大虧損":f"-${fmtm(ml)}","損益平衡":f"${fmt(ccks+ccpp)}","目標損益":f"{'+' if pat>=0 else ''}${fmtm(pat)}","報酬率":"∞","_ror":pat/ml*100 if ml else 0}
        if results:
            best=max(results,key=lambda k:results[k]["_ror"])
            lbls=["最大獲利","最大虧損","損益平衡","目標損益","報酬率"]
            cols_r=list(results.keys()); hdr="| 項目 | "+" | ".join(cols_r)+" |"; sep="| --- | "+" | ".join(["---"]*len(cols_r))+" |"
            rows_md=[hdr,sep]
            for lbl in lbls:
                row=[lbl]
                for k in cols_r:
                    v=results[k][lbl]
                    if lbl=="報酬率" and k==best: v=f"✅ **{v}**"
                    row.append(v)
                rows_md.append("| "+" | ".join(row)+" |")
            st.divider(); st.markdown("\n".join(rows_md))
            st.success(f"🏆 最佳：**{best}**")

# ══════ TAB 3: AI SCAN ══════
with tab3:
    st.markdown('''<div style="background:#0D1F14;border:1px solid #22C55E;border-radius:12px;padding:14px;margin-bottom:16px">
      <div style="font-size:13px;color:#22C55E;font-weight:700;margin-bottom:4px">🤖 AI 智能分析</div>
      <div style="font-size:12px;color:#555;line-height:1.5">AI 讀截圖數字，程式精算損益<br>自動排除盈虧比過低的組合</div></div>''', unsafe_allow_html=True)
    ec1,ec2=st.columns(2)
    scan_ticker=ec1.text_input("股票代號",placeholder="DKNG / ORCL",key="stk").upper()
    scan_expiry=ec2.text_input("選擇權到期日",placeholder="2026-08-21",key="exp")
    scan_info=None; scan_price=None
    if scan_ticker:
        scan_info=stock_info_card(scan_ticker)
        scan_price=scan_info.get("price") if scan_info else None
    uploaded_files=st.file_uploader("上傳截圖（最多3張）",type=["png","jpg","jpeg","webp"],accept_multiple_files=True)
    all_b64s=[]
    if uploaded_files:
        all_b64s=[compress_image(f) for f in uploaded_files[:3]]
        with st.expander(f"📷 已上傳 {len(uploaded_files[:3])} 張（點擊查看）"):
            cols=st.columns(min(len(uploaded_files),3))
            for i,f in enumerate(uploaded_files[:3]):
                with cols[i]: st.image(f,use_container_width=True)
        if st.button("🤖 AI 分析最佳組合",key="scan_btn"):
            if not api_key: st.error("請先設定 API Key")
            else:
                with st.spinner("AI 讀取數據中..."):
                    try:
                        client=anthropic.Anthropic(api_key=api_key)
                        ph=f"現價 ${scan_price}（請用此價格）。" if scan_price else "請從截圖讀取現價。"
                        if scan_expiry: ph+=f" 到期日：{scan_expiry}。"
                        read_prompt=f"""讀取期權鏈截圖數據（{scan_ticker or '未知'}）。{ph}
對每個行權價讀取 Call買盤/賣盤、Put買盤/賣盤。
只回純JSON：{{"currentPrice":29.0,"rows":[{{"strike":30,"callBid":2.36,"callAsk":2.42,"putBid":3.10,"putAsk":3.20}}]}}
讀不到填null，把所有看得到的行權價列出。"""
                        parts=[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b}} for b in all_b64s]
                        parts.append({"type":"text","text":read_prompt})
                        msg=client.messages.create(model="claude-sonnet-4-6",max_tokens=2000,messages=[{"role":"user","content":parts}])
                        text=msg.content[0].text.strip()
                        m=re.search(r'\{[\s\S]*\}',text)
                        if not m: st.error("讀取失敗："+text[:200])
                        else:
                            chain=json.loads(m.group())
                            cur2=scan_price or chain.get("currentPrice",0)
                            rows2=chain.get("rows",[])
                            st.session_state["scan_result"]=compute_strategies(rows2,cur2,scan_ticker,scan_expiry)
                    except Exception as e: st.error(f"失敗：{e}")

    if st.session_state.get("scan_result"):
        res=st.session_state["scan_result"]; cur2=res["cur"]; tkr=res["ticker"]; exp=res["expiry"]
        allc=res["bull"]+res["bear"]+res["call"]
        if not allc: st.error("找不到有效組合"); 
        else:
            max_ror=max(x["ror"] for x in allc)
            exp_txt=f" · 到期 {exp}" if exp else ""
            st.markdown(f'''<div style="display:flex;justify-content:space-between;align-items:flex-end;padding:6px 0 12px;border-bottom:1px solid #2A2A2A;margin-bottom:12px">
              <div><div style="font-size:20px;font-weight:900;letter-spacing:-0.5px">{tkr}</div>
              <div style="font-size:11px;color:#555">現價 ${fmt(cur2)}{exp_txt}</div></div>
              <div style="text-align:right"><div style="font-size:10px;color:#555;font-weight:700">最高投資報酬率</div>
              <div style="font-size:18px;font-weight:800;color:#22C55E">{max_ror:.0f}%</div></div></div>''', unsafe_allow_html=True)
            top3=res.get("top3",[])
            if top3:
                st.markdown('<div style="font-size:10px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:8px">整體最佳 Top 3</div>', unsafe_allow_html=True)
                for t3 in top3:
                    typ=t3["type"]; tc={"bull":"#3B82F6","bear":"#EF4444","call":"#22C55E","put":"#F59E0B"}.get(typ,"#888")
                    tname={"bull":"看漲價差","bear":"看跌價差","call":"單買Call","put":"單買Put"}.get(typ,"")
                    strikes=f"${fmt(t3.get('buyStrike',0))} / ${fmt(t3.get('sellStrike',0))}" if typ in ("bull","bear") else f"${fmt(t3.get('strike',0))} Call"
                    medal=t3.get("_medal","")
                    medal_txt={"🥇":"金牌","🥈":"銀牌","🥉":"銅牌"}.get(medal,"")
                    with st.expander(f"{medal_txt}｜{tname} {strikes}｜{t3['ror']:.0f}%", expanded=(medal=="🥇")):
                        st.markdown(f'<div style="font-size:22px;text-align:center;margin-bottom:4px">{medal}</div>', unsafe_allow_html=True)
                        render_combo(t3, cur2, typ, save_key=f"savetop_{medal}")
            def show_group(items, label):
                if not items: return
                st.markdown(f'<div style="font-size:10px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">{label}</div>', unsafe_allow_html=True)
                tname_map={"bull":"看漲價差","bear":"看跌價差","call":"單買Call","put":"單買Put"}
                for idx,it in enumerate(items):
                    typ=it["type"]; tname=tname_map.get(typ,"")
                    strikes=f"${fmt(it.get('buyStrike',0))} / ${fmt(it.get('sellStrike',0))}" if typ in ("bull","bear") else f"${fmt(it.get('strike',0))} Call"
                    with st.expander(f"{tname} {strikes} · 平衡${fmt(it.get('breakeven',0))} · {it['ror']:.0f}%"):
                        render_combo(it, cur2, typ, save_key=f"save_{typ}_{idx}")
            show_group(res["bull"],"📈 看漲價差 Bull Call — Top 3")
            show_group(res["bear"],"📉 看跌價差 Bear Put — Top 3")
            show_group(res["call"],"📞 單買 Call — Top 2")

# ══════ TAB 4: 我的組合 ══════
with tab4:
    favs=load_favs()
    if not favs:
        st.markdown('<div style="background:#141414;border-radius:12px;padding:28px;text-align:center;color:#555;font-size:13px">尚無收藏<br><span style="font-size:11px">在選股計算或AI掃描後點 ⭐ 收藏</span></div>', unsafe_allow_html=True)
    else:
        groups={}
        for f in favs: groups.setdefault(f.get("ticker","未命名"),[]).append(f)
        st.markdown(f'<div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">已收藏 {len(favs)} 個組合</div>', unsafe_allow_html=True)
        for tk,items in groups.items():
            st.markdown(f'<div style="font-size:15px;font-weight:800;color:#F0F0F0;margin:14px 0 8px">📌 {tk} <span style="font-size:11px;color:#555;font-weight:400">{len(items)} 個</span></div>', unsafe_allow_html=True)
            for f in items:
                typ=f.get("type",""); tname={"bull":"看漲價差","bear":"看跌價差","call":"單買Call","put":"單買Put"}.get(typ,"")
                strikes=f"${fmt(f.get('buyStrike',0))} / ${fmt(f.get('sellStrike',0))}" if typ in ("bull","bear") else f"${fmt(f.get('strike',0))} Call"
                with st.expander(f"{tname} {strikes} · {f.get('ror',0):.0f}%"):
                    render_combo(f, f.get("currentPrice",0), typ)
                    if st.button("🗑 移除", key=f"del_{f.get('_id','')}"):
                        save_favs([x for x in load_favs() if x.get("_id")!=f.get("_id")]); st.rerun()

# ══════ TAB 5: 說明 ══════
with tab5:
    st.markdown('''<div style="color:#F0F0F0">
    <div style="background:#141414;border-radius:12px;padding:14px;margin-bottom:12px">
      <div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">AI 排序原則</div>
      <div style="font-size:13px;color:#AAA;line-height:1.6">以「最不容易賠錢」優先：<br>1. 損益平衡接近現價<br>2. 成本（最大虧損）低<br>3. 盈虧比合理</div></div>
    <div style="background:#141414;border-radius:12px;padding:14px;margin-bottom:12px">
      <div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">策略說明</div>
      <div style="font-size:13px;color:#AAA;line-height:1.6"><b style="color:#F0F0F0">看漲價差</b> — 買低Call賣高Call<br><br><b style="color:#F0F0F0">看跌價差</b> — 買高Put賣低Put<br><br><b style="color:#F0F0F0">單買Call/Put</b> — 無限獲利潛力，最多虧損權利金</div></div>
    <div style="background:#141414;border-radius:12px;padding:14px">
      <div style="font-size:11px;color:#555;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">AI 分析費用</div>
      <div style="font-size:13px;color:#AAA">每次約 $0.02–0.05</div></div>
    </div>''', unsafe_allow_html=True)
