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
* { font-family: 'Inter', -apple-system, sans-serif !important; box-sizing: border-box; }
.stApp { background: #0D1117; color: #E6EDF3; }
.main .block-container { padding: 0 0 80px; max-width: 430px; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background:#161B22;border-radius:0;padding:0 16px;gap:0;border:none;border-bottom:1px solid #30363D;margin-bottom:16px; }
.stTabs [data-baseweb="tab"] { background:transparent!important;border-radius:0!important;color:#8B949E;font-size:13px;font-weight:600;padding:12px 16px;border:none!important;border-bottom:2px solid transparent!important; }
.stTabs [aria-selected="true"] { color:#E6EDF3!important;border-bottom:2px solid #1F6FEB!important; }
.stTabs [data-baseweb="tab-highlight"],[data-baseweb="tab-border"] { display:none; }

/* Inputs */
.stTextInput>div>div { background:#1C2128!important;border:1px solid #30363D!important;border-radius:10px!important; }
.stTextInput input { background:#1C2128!important;border:none!important;color:#E6EDF3!important;font-size:15px!important;font-weight:600!important;padding:10px 14px!important; }
.stTextInput label { color:#8B949E!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }
.stSelectbox>div>div { background:#1C2128!important;border:1px solid #30363D!important;border-radius:10px!important;color:#E6EDF3!important;font-size:14px!important;font-weight:600!important; }
.stSelectbox label { color:#8B949E!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }
.stNumberInput>div>div>div { background:#1C2128!important;border:1px solid #30363D!important;border-radius:10px!important; }
.stNumberInput input { background:#1C2128!important;border:none!important;color:#E6EDF3!important;font-size:14px!important;font-weight:600!important;padding:10px 14px!important; }
.stNumberInput label { color:#8B949E!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }

/* Button */
.stButton>button { background:linear-gradient(135deg,#1F6FEB,#0C54C7)!important;color:#fff!important;border:none!important;border-radius:12px!important;font-size:16px!important;font-weight:800!important;padding:16px 24px!important;width:100%!important;letter-spacing:0.3px; }
.stButton>button:hover { opacity:0.9!important; }

/* Expander */
[data-testid="stExpander"] { background:#161B22!important;border:1px solid #30363D!important;border-radius:12px!important;margin-bottom:8px; }
[data-testid="stExpander"] summary { color:#E6EDF3!important;font-weight:600!important;font-size:13px!important; }

/* Misc */
.stSuccess { background:#0D4429!important;border:1px solid #1A6B36!important;border-radius:10px!important;color:#3FB950!important; }
.stError { background:#4A1015!important;border:1px solid #8B1A1A!important;border-radius:10px!important;color:#F85149!important; }
.stInfo { background:#0C2D6B!important;border:1px solid #1F6FEB!important;border-radius:10px!important; }
.stFileUploader { background:#1C2128!important;border:1.5px dashed #30363D!important;border-radius:12px!important; }
hr { border-color:#30363D!important;margin:14px 0!important; }
</style>
""", unsafe_allow_html=True)

api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── helpers ───────────────────────────────────────────
def fmt(v, d=2):
    if v is None: return "—"
    return f"{v:.{d}f}"

def fmtm(v):
    if v is None: return "—"
    return f"{v:.0f}" if float(v) == int(v) else f"{v:.2f}"

def compress_image(uf):
    img = Image.open(uf)
    if img.width > 1200:
        img = img.resize((1200, int(img.height*1200/img.width)), Image.LANCZOS)
    if img.mode != "RGB": img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=75); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# ── yfinance ──────────────────────────────────────────
@st.cache_data(ttl=60)
def get_stock_info(symbol):
    if not HAS_YF or not symbol: return {}
    try:
        t = yf.Ticker(symbol)
        out = {}
        try:
            fi = t.fast_info
            p = fi.get("lastPrice") or fi.get("last_price")
            if p: out["price"] = round(float(p), 2)
            prev = fi.get("previousClose") or fi.get("previous_close")
            if prev and out.get("price"):
                out["change"]  = round(out["price"] - float(prev), 2)
                out["changePct"] = round((out["price"] - float(prev)) / float(prev) * 100, 2)
        except: pass
        if not out.get("price"):
            h = t.history(period="2d")
            if not h.empty:
                out["price"] = round(float(h["Close"].iloc[-1]), 2)
                if len(h) >= 2:
                    prev2 = float(h["Close"].iloc[-2])
                    out["change"] = round(out["price"] - prev2, 2)
                    out["changePct"] = round((out["price"] - prev2) / prev2 * 100, 2)
        try:
            info = t.info
            out["name"]   = info.get("longName") or info.get("shortName") or symbol
            out["sector"] = info.get("sector") or ""
            out["exchange"] = info.get("exchange") or ""
            tp = info.get("targetMeanPrice")
            if tp: out["target"] = round(float(tp), 2)
            out["lo52"] = info.get("fiftyTwoWeekLow")
            out["hi52"] = info.get("fiftyTwoWeekHigh")
        except: pass
        try:
            cal = t.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed: out["nextER"] = str(ed[0] if isinstance(ed, list) else ed)[:10]
        except: pass
        return out
    except: return {}

@st.cache_data(ttl=120)
def get_expiries(symbol):
    if not HAS_YF or not symbol: return []
    try: return list(yf.Ticker(symbol).options)
    except: return []

@st.cache_data(ttl=60)
def get_chain(symbol, expiry):
    if not HAS_YF or not symbol or not expiry: return [], []
    try:
        opt = yf.Ticker(symbol).option_chain(expiry)
        calls = opt.calls[["strike","bid","ask"]].dropna().to_dict("records")
        puts  = opt.puts[["strike","bid","ask"]].dropna().to_dict("records")
        # rename keys
        calls = [{"k": r["strike"], "bid": round(r["bid"],2), "ask": round(r["ask"],2)} for r in calls]
        puts  = [{"k": r["strike"], "bid": round(r["bid"],2), "ask": round(r["ask"],2)} for r in puts]
        return calls, puts
    except: return [], []

# ── P&L ───────────────────────────────────────────────
def calc_pnl(sk, bK, bP, sK, sP, price):
    if sk == "bull":
        nc = bP - sP
        if price <= bK: return -nc * 100
        if price >= sK: return (sK - bK - nc) * 100
        return (price - bK - nc) * 100
    elif sk == "bear":
        nc = bP - sP
        if price >= bK: return -nc * 100
        if price <= sK: return (bK - sK - nc) * 100
        return (bK - price - nc) * 100
    elif sk == "call":
        return (max(price - bK, 0) - bP) * 100
    elif sk == "put":
        return (max(bK - price, 0) - bP) * 100
    return 0

def find_be(sk, bK, bP, sK, sP, cur):
    lo = min(bK, sK or bK, cur) * 0.75
    hi = max(bK, sK or bK, cur) * 1.35
    pts = [lo + (hi-lo)*i/600 for i in range(601)]
    prev = calc_pnl(sk, bK, bP, sK, sP, pts[0])
    for i in range(1, len(pts)):
        cur2 = calc_pnl(sk, bK, bP, sK, sP, pts[i])
        if (prev <= 0 and cur2 > 0) or (prev >= 0 and cur2 < 0):
            f = abs(prev) / (abs(prev) + abs(cur2))
            return pts[i-1] + f * (pts[i] - pts[i-1])
        prev = cur2
    return None

def make_svg(sk, bK, bP, sK, sP, cur):
    unlimited = sk in ("call", "put")
    profit_right = sk in ("bull", "call")
    be = find_be(sk, bK, bP, sK, sP, cur)
    all_key = [bK, cur] + ([sK] if sK else []) + ([be] if be else [])
    center = be or cur
    span = max(max(all_key) - min(all_key), cur * 0.16) * 1.5
    lo = center - span * 0.55; hi = center + span * 0.55
    pts  = [lo + (hi-lo)*i/200 for i in range(201)]
    pnls = [calc_pnl(sk, bK, bP, sK, sP, p) for p in pts]
    maxV = max(pnls); minV = min(pnls)
    W,H,pX,pTop,pBot,labH = 380,230,14,26,10,34
    pH = H - pTop - pBot - labH
    vpad = (maxV-minV)*0.18
    vT = maxV+vpad; vR = (vT-(minV-vpad)) or 1
    def cx(p): return pX + ((p-lo)/(hi-lo))*(W-2*pX)
    def cy(v): return pTop + (vT-v)/vR*pH
    zY = cy(0)
    lineD = " ".join(f"{'M' if i==0 else 'L'}{cx(pts[i]):.1f},{cy(pnls[i]):.1f}" for i in range(len(pts)))
    fillD = f"{lineD} L{cx(hi):.1f},{zY:.1f} L{cx(lo):.1f},{zY:.1f} Z"
    # ticks
    ticks = "".join(f'<line x1="{cx(lo+(hi-lo)*i/5):.1f}" y1="{zY:.1f}" x2="{cx(lo+(hi-lo)*i/5):.1f}" y2="{zY+4:.1f}" stroke="#444" stroke-width="0.8"/><text x="{cx(lo+(hi-lo)*i/5):.1f}" y="{zY+13:.1f}" fill="#444" font-size="7.5" text-anchor="middle">${lo+(hi-lo)*i/5:.0f}</text>' for i in range(6))
    # current price line
    cur_svg = f'<line x1="{cx(cur):.1f}" y1="{pTop}" x2="{cx(cur):.1f}" y2="{H-pBot-labH}" stroke="#1F6FEB" stroke-width="1" stroke-dasharray="4 3" opacity="0.5"/><text x="{cx(cur):.1f}" y="{pTop-4}" fill="#1F6FEB" font-size="9" text-anchor="middle" font-weight="600">現價 ${cur:.2f}</text>' if lo < cur < hi else ""
    # strike dots
    dots = [(bK, bP, True)] + ([(sK, sP, False)] if sK else [])
    dot_svg = ""
    for dk, dp, buy in dots:
        if not (lo < dk < hi): continue
        dy = cy(calc_pnl(sk, bK, bP, sK, sP, dk))
        sx = cx(dk)
        mc = "#60A5FA" if buy else "#FB923C"
        lbl = f"{'買入' if buy else '賣出'} ${dk:.0f}"
        above = dy > H * 0.45
        by2 = dy - 27 if above else dy + 11
        dot_svg += f'<rect x="{sx-34:.1f}" y="{by2:.1f}" width="68" height="14" rx="3" fill="#0A0A0A" opacity="0.92"/><text x="{sx:.1f}" y="{by2+11:.1f}" fill="{mc}" font-size="9" text-anchor="middle" font-weight="700">{lbl}</text><circle cx="{sx:.1f}" cy="{dy:.1f}" r="5" fill="{mc}"/><circle cx="{sx:.1f}" cy="{dy:.1f}" r="9" fill="{mc}" opacity="0.18"/>'
    # be dot
    be_svg = ""
    if be and lo < be < hi:
        bx = cx(be)
        be_svg = f'<rect x="{bx-36:.1f}" y="{zY-32:.1f}" width="72" height="24" rx="4" fill="#0A0A0A" opacity="0.92"/><text x="{bx:.1f}" y="{zY-20:.1f}" fill="#F0B429" font-size="8" text-anchor="middle" font-weight="600">損益平衡</text><text x="{bx:.1f}" y="{zY-9:.1f}" fill="#F0B429" font-size="10" text-anchor="middle" font-weight="800">${be:.2f}</text><circle cx="{bx:.1f}" cy="{zY:.1f}" r="5" fill="#F0B429"/><circle cx="{bx:.1f}" cy="{zY:.1f}" r="9" fill="#F0B429" opacity="0.22"/>'
    # labels
    bY = H - labH + 14; bY2 = H - labH + 27
    pX1 = W-pX-4 if profit_right else pX+4; pA1 = "end" if profit_right else "start"
    lX1 = pX+4 if profit_right else W-pX-4; lA1 = "start" if profit_right else "end"
    mp_txt = "∞" if unlimited else f"+${maxV:.0f}"
    ml_txt = f"-${abs(minV):.0f}"
    return f'''<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block;background:#0D1117;border-radius:14px;margin-top:10px">
  <defs>
    <clipPath id="cp_p"><rect x="{pX}" y="{pTop}" width="{W-2*pX}" height="{max(zY-pTop,0):.1f}"/></clipPath>
    <clipPath id="cp_l"><rect x="{pX}" y="{zY:.1f}" width="{W-2*pX}" height="{max(pH-(zY-pTop)+pBot+4,0):.1f}"/></clipPath>
  </defs>
  <line x1="{pX}" y1="{zY:.1f}" x2="{W-pX}" y2="{zY:.1f}" stroke="#2A2A2A" stroke-width="1" stroke-dasharray="4 3"/>
  {ticks}{cur_svg}
  <path d="{fillD}" fill="#4ADE80" opacity="0.18" clip-path="url(#cp_p)"/>
  <path d="{fillD}" fill="#F87171" opacity="0.18" clip-path="url(#cp_l)"/>
  <path d="{lineD}" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cp_p)"/>
  <path d="{lineD}" fill="none" stroke="#F87171" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cp_l)"/>
  {dot_svg}{be_svg}
  <text x="{pX1}" y="{bY}" fill="#4ADE80" font-size="8" font-weight="700" text-anchor="{pA1}">最大獲利</text>
  <text x="{pX1}" y="{bY2}" fill="#4ADE80" font-size="12" font-weight="800" text-anchor="{pA1}">{mp_txt}</text>
  <text x="{lX1}" y="{bY}" fill="#F87171" font-size="8" font-weight="700" text-anchor="{lA1}">最大虧損</text>
  <text x="{lX1}" y="{bY2}" fill="#F87171" font-size="12" font-weight="800" text-anchor="{lA1}">{ml_txt}</text>
</svg>'''

def make_ladder(sk, bK, bP, sK, sP, maxL, be, cur):
    allK = [bK] + ([sK] if sK else [])
    spread = abs(bK - sK) if sK else bP * 5
    step = 1 if spread < 5 else 1 if spread <= 10 else 2.5 if spread <= 20 else 5 if spread <= 50 else 10
    lo = math.floor(min(allK + [cur]) * 0.88 / step) * step
    hi = math.ceil( max(allK + [cur]) * 1.12 / step) * step
    all_rows = []
    p = lo
    while p <= hi + 0.001:
        v   = calc_pnl(sk, bK, bP, sK, sP, p)
        ret = v / maxL * 100 if maxL else 0
        near_be = be is not None and abs(p - be) <= step * 0.55
        is_max  = (sk == "bull" and sK and p >= sK) or (sk == "bear" and sK and p <= sK)
        all_rows.append({"p": p, "v": v, "ret": ret, "nearBE": near_be, "isMax": is_max})
        p = round(p + step, 3)
    # trim: remove repeating rows at start/end, keep MAX+5
    rows = []
    # find min index (first change from floor)
    min_idx = 0
    for i in range(1, len(all_rows)):
        if all_rows[i]["v"] != all_rows[0]["v"]:
            min_idx = max(0, i - 1); break
    # find max index (MAX + 5 rows)
    max_idx = len(all_rows) - 1
    if sK:
        for i, r in enumerate(all_rows):
            if r["isMax"]:
                max_idx = min(i + 5, len(all_rows) - 1); break
    rows = all_rows[min_idx:max_idx+1]
    # render
    html = f'<div style="background:#1C2128;border-radius:12px;overflow:hidden;margin-top:12px"><div style="padding:8px 14px;display:flex;justify-content:space-between;border-bottom:1px solid #30363D"><span style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px">損益對照表</span><span style="font-size:10px;color:#484F58;background:#21262D;padding:1px 8px;border-radius:100px">每 ${fmtm(step)}</span></div><table style="width:100%;border-collapse:collapse"><thead><tr style="background:#21262D"><th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:left;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">股價</th><th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:right;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">損益 / 張</th><th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:right;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">報酬率</th></tr></thead><tbody>'
    for r in rows:
        col = "#4ADE80" if r["v"] > 0 else "#F87171" if r["v"] < 0 else "#F0B429"
        bg  = "rgba(74,222,128,0.05)" if r["v"] > 1 else "rgba(248,113,113,0.05)" if r["v"] < -1 else "rgba(240,180,41,0.06)"
        p_str = f"${r['p']:.0f}" if r['p'] % 1 == 0 else f"${r['p']:.2f}"
        tags = ""
        if r["nearBE"]: tags += '<span style="font-size:8px;background:#1A1000;color:#F0B429;padding:1px 5px;border-radius:100px;margin-left:4px;font-weight:700">平衡</span>'
        if r["isMax"]:  tags += '<span style="font-size:8px;background:#0D2010;color:#4ADE80;padding:1px 5px;border-radius:100px;margin-left:4px;font-weight:700">MAX</span>'
        pnl_str = f"{'+'if r['v']>=0 else ''}${abs(r['v']):.0f}"
        ret_str = f"{'+'if r['ret']>=0 else ''}{r['ret']:.0f}%"
        html += f'<tr style="background:{bg};border-bottom:1px solid #161B22"><td style="font-size:12px;color:#E6EDF3;padding:6px 12px;font-weight:500">{p_str}{tags}</td><td style="font-size:12px;color:{col};padding:6px 12px;text-align:right;font-weight:600">{pnl_str}</td><td style="font-size:12px;color:{col};padding:6px 12px;text-align:right;font-weight:600">{ret_str}</td></tr>'
    html += "</tbody></table></div>"
    return html

def show_result(sk, bK, bP, sK, sP, maxP, maxL, be, cur):
    unlimited = sk in ("call","put")
    mp_str = "∞" if unlimited else f"${fmtm(maxP)}"
    mp_sub = "" if unlimited else f"+{maxP/maxL*100:.0f}%"
    ror_str = "∞" if unlimited else f"{maxP/maxL*100:.0f}%"
    be_str = f"${fmt(be)}" if be else "—"
    st.markdown(f'''
    <div style="background:#161B22;border:1px solid #30363D;border-radius:14px;padding:14px;margin-top:4px">
      <div style="font-size:14px;font-weight:700;color:#E6EDF3;margin-bottom:12px">損益總覽</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:12px">
        <div style="background:#0D4429;border:1.5px solid #1A6B36;border-radius:10px;padding:10px 8px">
          <div style="font-size:9px;color:#86EFAC;font-weight:700;margin-bottom:4px;letter-spacing:0.5px">最大獲利</div>
          <div style="font-size:16px;font-weight:900;color:#4ADE80;letter-spacing:-0.5px">{mp_str}</div>
          {f'<div style="font-size:10px;color:#4ADE80;margin-top:1px;font-weight:600">{mp_sub}</div>' if mp_sub else ""}
        </div>
        <div style="background:#4A1015;border:1.5px solid #8B1A1A;border-radius:10px;padding:10px 8px">
          <div style="font-size:9px;color:#FCA5A5;font-weight:700;margin-bottom:4px;letter-spacing:0.5px">最大虧損</div>
          <div style="font-size:16px;font-weight:900;color:#F87171;letter-spacing:-0.5px">-${fmtm(maxL)}</div>
          <div style="font-size:10px;color:#F87171;margin-top:1px;font-weight:600">-{maxL/(maxL+(maxP or maxL))*100:.0f}%</div>
        </div>
        <div style="background:#1C2128;border:1.5px solid #30363D;border-radius:10px;padding:10px 8px">
          <div style="font-size:9px;color:#8B949E;font-weight:700;margin-bottom:4px;letter-spacing:0.5px">報酬率</div>
          <div style="font-size:16px;font-weight:900;color:#E6EDF3;letter-spacing:-0.5px">{ror_str}</div>
        </div>
        <div style="background:#2D1F52;border:1.5px solid #6E40C9;border-radius:10px;padding:10px 8px">
          <div style="font-size:9px;color:#C4B5FD;font-weight:700;margin-bottom:4px;letter-spacing:0.5px">損益平衡</div>
          <div style="font-size:16px;font-weight:900;color:#A78BFA;letter-spacing:-0.5px">{be_str}</div>
        </div>
      </div>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown(make_svg(sk, bK, bP, sK, sP, cur), unsafe_allow_html=True)
    st.markdown(make_ladder(sk, bK, bP, sK, sP, maxL, be, cur), unsafe_allow_html=True)

def stock_card(info, ticker):
    price  = info.get("price", 0)
    change = info.get("change", 0)
    pct    = info.get("changePct", 0)
    name   = info.get("name", ticker)
    target = info.get("target")
    lo52   = info.get("lo52")
    hi52   = info.get("hi52")
    nextER = info.get("nextER", "—")
    exch   = info.get("exchange", "")
    sector = info.get("sector", "")
    upside = round((target-price)/price*100,1) if target and price else None
    bar_pct = round((price-lo52)/(hi52-lo52)*100) if lo52 and hi52 and hi52>lo52 else 50
    bar_pct = max(0, min(100, bar_pct))
    chg_col = "#F85149" if change < 0 else "#3FB950"
    tgt_html = ""
    if target:
        uc = "#3FB950" if upside and upside >= 0 else "#F85149"
        tgt_html = f'<div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:10px;color:#8B949E;font-weight:600">分析師目標</span><div><span style="font-size:11px;font-weight:700">${target:.2f}</span><span style="font-size:10px;color:{uc};margin-left:4px;font-weight:600">{"+" if upside and upside>=0 else ""}{upside:.1f}%</span></div></div>'
    range_html = ""
    if lo52 and hi52:
        range_html = f'<div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:10px;color:#8B949E;font-weight:600">52週區間</span><div style="text-align:right"><span style="font-size:11px;font-weight:700">{lo52:.0f}–{hi52:.0f}</span><div style="background:#21262D;border-radius:100px;height:3px;margin-top:3px;width:56px;position:relative;margin-left:auto"><div style="position:absolute;left:{bar_pct}%;top:-2px;width:7px;height:7px;background:#1F6FEB;border-radius:50%;transform:translateX(-50%)"></div></div></div></div>'
    st.markdown(f'''
    <div style="background:#161B22;border:1px solid #30363D;border-radius:14px;padding:14px;margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
        <div style="display:flex;gap:10px;align-items:center">
          <div style="width:40px;height:40px;background:#1F6FEB;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;color:#fff">{ticker}</div>
          <div>
            <div style="font-size:13px;font-weight:700">{name}</div>
            <div style="display:flex;gap:5px;margin-top:3px">
              {f'<span style="font-size:10px;background:#21262D;color:#8B949E;padding:2px 6px;border-radius:4px">{exch}</span>' if exch else ""}
              {f'<span style="font-size:10px;background:#21262D;color:#8B949E;padding:2px 6px;border-radius:4px">{sector}</span>' if sector else ""}
            </div>
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:22px;font-weight:900;letter-spacing:-0.5px">${price:.2f}</div>
          <div style="font-size:12px;color:{chg_col};font-weight:600">{change:+.2f} ({pct:+.2f}%)</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
        {tgt_html}
        {range_html}
        <div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:10px;color:#8B949E;font-weight:600">下一財報</span>
          <span style="font-size:11px;font-weight:700;color:#F79000">{nextER}</span>
        </div>
        <div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:10px;color:#8B949E;font-weight:600">即時連線</span>
          <span style="font-size:11px;font-weight:700;color:#3FB950">● 已連線</span>
        </div>
      </div>
    </div>''', unsafe_allow_html=True)

# ── local storage ─────────────────────────────────────
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
    combo["_id"] = f"{combo.get('ticker','')}_{combo.get('sk','')}_{len(favs)}"
    favs.insert(0, combo); save_favs(favs)

# ── compute_strategies for AI scan ───────────────────
def compute_strategies(rows, cur, ticker, expiry):
    valid = sorted([r for r in rows if r.get("strike") is not None], key=lambda r: r["strike"])
    bulls, bears, calls_list = [], [], []
    for i in range(len(valid)):
        for j in range(i+1, len(valid)):
            lo, hi = valid[i], valid[j]
            ba = lo.get("callAsk"); sb = hi.get("callBid")
            if ba and sb and ba > 0:
                nc = ba - sb
                if nc > 0:
                    sp = hi["strike"]-lo["strike"]; maxP=(sp-nc)*100; maxL=nc*100
                    if maxP>0 and maxP/maxL>=1.0 and cur and (lo["strike"]-cur)/cur<=0.10:
                        be=lo["strike"]+nc; ror=maxP/maxL*100
                        pg=max((be-cur)/cur,0)
                        safety=(1/(1+pg*5))*100*0.5+min(ror,300)/3*0.3+(1/(1+maxL/200))*100*0.2
                        bulls.append({"type":"bull","buyStrike":lo["strike"],"buyPremium":round(ba,2),"sellStrike":hi["strike"],"sellPremium":round(sb,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_safety":safety})
            ba = hi.get("putAsk"); sb = lo.get("putBid")
            if ba and sb and ba > 0:
                nc = ba - sb
                if nc > 0:
                    sp = hi["strike"]-lo["strike"]; maxP=(sp-nc)*100; maxL=nc*100
                    if maxP>0 and maxP/maxL>=1.0 and cur and (cur-hi["strike"])/cur<=0.10:
                        be=hi["strike"]-nc; ror=maxP/maxL*100
                        pg=max((cur-be)/cur,0)
                        safety=(1/(1+pg*5))*100*0.5+min(ror,300)/3*0.3+(1/(1+maxL/200))*100*0.2
                        bears.append({"type":"bear","buyStrike":hi["strike"],"buyPremium":round(ba,2),"sellStrike":lo["strike"],"sellPremium":round(sb,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_safety":safety})
    for r in valid:
        ba = r.get("callAsk")
        if ba and ba>0 and cur and abs(r["strike"]-cur)/cur<=0.12:
            be=r["strike"]+ba; target=cur*1.20
            maxP=(target-r["strike"]-ba)*100; maxL=ba*100
            if maxP>0:
                ror=maxP/maxL*100; pg=max((be-cur)/cur,0)
                safety=(1/(1+pg*4))*100*0.6+min(ror,200)/2*0.2+(1/(1+maxL/300))*100*0.2
                calls_list.append({"type":"call","strike":r["strike"],"premium":round(ba,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_safety":safety})
    bulls.sort(key=lambda x:-x["_safety"]); bears.sort(key=lambda x:-x["_safety"]); calls_list.sort(key=lambda x:-x["_safety"])
    B,R,L = bulls[:3],bears[:3],calls_list[:2]
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
    everything = sorted(B+R+L, key=lambda x:-x["_safety"])
    for i,t in enumerate(everything[:3]): t["_medal"]=["🥇","🥈","🥉"][i]
    return {"cur":cur,"ticker":ticker,"expiry":expiry,"bull":B,"bear":R,"call":L,"top3":everything[:3]}

def render_ai_combo(it, cur, typ, key=None):
    unlimited = typ in ("call","put")
    mp = it.get("maxProfit",0); ml = it.get("maxLoss",0); be = it.get("breakeven",0)
    mp_str = "∞" if unlimited else f"${fmtm(mp)}"
    ror_str = "∞" if unlimited else f"{it.get('ror',0):.0f}%"
    st.markdown(f'''<div style="display:flex;gap:6px;margin:8px 0">
      <div style="flex:1;background:#0D4429;border:1.5px solid #1A6B36;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#86EFAC;font-weight:700;margin-bottom:3px">最大獲利</div>
        <div style="font-size:15px;font-weight:900;color:#4ADE80">{mp_str}</div></div>
      <div style="flex:1;background:#4A1015;border:1.5px solid #8B1A1A;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#FCA5A5;font-weight:700;margin-bottom:3px">最大虧損</div>
        <div style="font-size:15px;font-weight:900;color:#F87171">-${fmtm(ml)}</div></div>
      <div style="flex:1;background:#1C2128;border:1.5px solid #30363D;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#8B949E;font-weight:700;margin-bottom:3px">報酬率</div>
        <div style="font-size:15px;font-weight:900;color:#E6EDF3">{ror_str}</div></div>
      <div style="flex:1;background:#2D1F52;border:1.5px solid #6E40C9;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#C4B5FD;font-weight:700;margin-bottom:3px">損益平衡</div>
        <div style="font-size:15px;font-weight:900;color:#A78BFA">${fmt(be)}</div></div>
    </div>''', unsafe_allow_html=True)
    if it.get("pros") or it.get("cons"):
        st.markdown(f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0">
          <div style="background:#0D4429;border:1px solid #1A6B36;border-radius:9px;padding:8px 10px">
            <div style="font-size:9px;color:#3FB950;font-weight:700;margin-bottom:2px">✓ 優點</div>
            <div style="font-size:11px;color:#8B949E">{it.get("pros","")}</div></div>
          <div style="background:#4A1015;border:1px solid #8B1A1A;border-radius:9px;padding:8px 10px">
            <div style="font-size:9px;color:#F85149;font-weight:700;margin-bottom:2px">✗ 缺點</div>
            <div style="font-size:11px;color:#8B949E">{it.get("cons","")}</div></div>
        </div>''', unsafe_allow_html=True)
    legs = {}
    if typ=="bull": legs={"bK":it["buyStrike"],"bP":it["buyPremium"],"sK":it["sellStrike"],"sP":it["sellPremium"]}
    elif typ=="bear": legs={"bK":it["buyStrike"],"bP":it["buyPremium"],"sK":it["sellStrike"],"sP":it["sellPremium"]}
    elif typ=="call": legs={"bK":it["strike"],"bP":it["premium"],"sK":0,"sP":0}
    if legs:
        st.markdown(make_svg(typ,legs["bK"],legs["bP"],legs.get("sK",0),legs.get("sP",0),cur), unsafe_allow_html=True)
    if key and st.button("⭐ 收藏", key=key):
        add_fav({**it,"ticker":st.session_state.get("scan_ticker",""),"sk":typ})
        st.success("已收藏！")

# ── header ─────────────────────────────────────────────
st.markdown('''
<div style="background:#161B22;padding:14px 16px 10px;border-bottom:1px solid #30363D;display:flex;justify-content:space-between;align-items:center;margin:0 -16px">
  <div style="display:flex;align-items:center;gap:8px">
    <div style="width:28px;height:28px;background:#1F6FEB;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:#fff">F</div>
    <div>
      <div style="font-size:9px;color:#8B949E;font-weight:600;letter-spacing:1px">OPTIONS</div>
      <div style="font-size:16px;font-weight:800;letter-spacing:-0.5px">Strategy Pro</div>
    </div>
  </div>
</div>
''', unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["選股計算", "AI 掃描", "我的組合", "說明"])

# ══════ TAB 1: 選股計算 ══════
with tab1:
    pad = "padding:0 16px"
    st.markdown(f'<div style="{pad}">', unsafe_allow_html=True)
    c1, c2 = st.columns([1,1])
    ticker = c1.text_input("股票代號", placeholder="MU / ORCL / DKNG", key="tk").upper().strip()
    expiries = get_expiries(ticker) if ticker else []
    expiry = c2.selectbox("到期日", expiries if expiries else ["—"], key="exp") if expiries else None

    info = {}
    if ticker:
        info = get_stock_info(ticker)
        if info.get("price"):
            stock_card(info, ticker)
        elif ticker:
            st.info("載入中...")

    if ticker and expiry and expiry != "—" and info.get("price"):
        calls, puts = get_chain(ticker, expiry)
        if not calls and not puts:
            st.error("抓不到期權鏈，請稍後再試")
        else:
            cur = info["price"]
            STRAT_LABELS = {
                "bull":"看漲價差 Bull Call Spread",
                "bear":"看跌價差 Bear Put Spread",
                "call":"單買 Call (Long Call)",
                "put": "單買 Put (Long Put)",
            }
            STRAT_TIPS = {
                "bull":"買低Call賣高Call，看漲限風險，最大獲利固定。",
                "bear":"買高Put賣低Put，看跌限風險，最大獲利固定。",
                "call":"直接買入Call，無限獲利潛力，最多虧損全部權利金。",
                "put": "直接買入Put，跌越多賺越多，最多虧損全部權利金。",
            }
            c1,c2 = st.columns([4,1])
            sk_label = c1.selectbox("策略選擇", list(STRAT_LABELS.values()), key="sk_sel", label_visibility="collapsed")
            sk = [k for k,v in STRAT_LABELS.items() if v==sk_label][0]
            # small tip toggle
            if "show_tip" not in st.session_state: st.session_state["show_tip"] = False
            if c2.button("ⓘ", key="tip_btn"):
                st.session_state["show_tip"] = not st.session_state["show_tip"]
            if st.session_state.get("show_tip"):
                st.markdown(f'<div style="background:#0C2D6B;border:1px solid #1F6FEB;border-radius:10px;padding:10px 14px;margin-bottom:10px;font-size:12px;color:#8B949E;line-height:1.6">{STRAT_TIPS[sk]}</div>', unsafe_allow_html=True)

            # Filter: only show strikes within ±30% of current price
            arr_b_all = calls if sk in ("bull","call") else puts
            arr_s_all = calls if sk == "bull" else puts if sk == "bear" else []
            arr_b = [r for r in arr_b_all if 0.70*cur <= r["k"] <= 1.30*cur]
            arr_s = [r for r in arr_s_all if 0.70*cur <= r["k"] <= 1.30*cur]
            # Sort by closeness to current price first for UX
            arr_b.sort(key=lambda r: abs(r["k"]-cur))
            arr_s.sort(key=lambda r: abs(r["k"]-cur))
            opts_b = {f"${r['k']:.0f}  (Ask ${r['ask']:.2f})": r for r in sorted(arr_b, key=lambda r: r["k"])}
            opts_s = {f"${r['k']:.0f}  (Bid ${r['bid']:.2f})": r for r in sorted(arr_s, key=lambda r: r["k"])} if arr_s else {}

            if sk in ("bull","bear"):
                b_lbl = "買入 Call" if sk=="bull" else "買入 Put"
                s_lbl = "賣出 Call" if sk=="bull" else "賣出 Put"
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f'''<div style="background:#0C2D6B;border:1.5px solid #1F6FEB;border-radius:14px;padding:12px;margin-bottom:10px">
                      <div style="font-size:11px;font-weight:700;color:#1F6FEB;margin-bottom:8px">{b_lbl} (Long)</div>''', unsafe_allow_html=True)
                    sel_b = st.selectbox("買入", ["請選擇"]+list(opts_b.keys()), key="sel_b", label_visibility="collapsed")
                    bR = opts_b.get(sel_b)
                    if bR:
                        st.markdown(f'<div style="font-size:10px;color:#8B949E;margin:4px 0 2px">Ask 權利金</div><div style="font-size:22px;font-weight:900;color:#E6EDF3">${bR["ask"]:.2f}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f'''<div style="background:#0D4429;border:1.5px solid #1A6B36;border-radius:14px;padding:12px;margin-bottom:10px">
                      <div style="font-size:11px;font-weight:700;color:#3FB950;margin-bottom:8px">{s_lbl} (Short)</div>''', unsafe_allow_html=True)
                    sel_s = st.selectbox("賣出", ["請選擇"]+list(opts_s.keys()), key="sel_s", label_visibility="collapsed")
                    sR = opts_s.get(sel_s)
                    if sR:
                        st.markdown(f'<div style="font-size:10px;color:#8B949E;margin:4px 0 2px">Bid 權利金</div><div style="font-size:22px;font-weight:900;color:#E6EDF3">${sR["bid"]:.2f}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                b_lbl = "買入 Call" if sk=="call" else "買入 Put"
                st.markdown(f'''<div style="background:#0C2D6B;border:1.5px solid #1F6FEB;border-radius:14px;padding:12px;margin-bottom:10px">
                  <div style="font-size:11px;font-weight:700;color:#1F6FEB;margin-bottom:8px">{b_lbl} (Long)</div>''', unsafe_allow_html=True)
                sel_b = st.selectbox("行權價", ["請選擇"]+list(opts_b.keys()), key="sel_b2", label_visibility="collapsed")
                bR = opts_b.get(sel_b)
                if bR:
                    st.markdown(f'<div style="font-size:10px;color:#8B949E;margin:4px 0 2px">Ask 權利金</div><div style="font-size:22px;font-weight:900;color:#E6EDF3">${bR["ask"]:.2f}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                sel_s = "請選擇"; sR = None

            # Calculate button
            st.markdown('''<style>
            div[data-testid="stButton"] button {
                background: linear-gradient(135deg,#1F6FEB,#0C54C7) !important;
            }
            </style>''', unsafe_allow_html=True)
            if st.button("計算損益", key="calc_btn"):
                b_sel = "sel_b" if sk in ("bull","bear") else "sel_b2"
                sel_b_val = st.session_state.get(b_sel, "請選擇")
                sel_s_val = st.session_state.get("sel_s", "請選擇") if sk in ("bull","bear") else "請選擇"

                if sel_b_val == "請選擇" or sel_b_val not in opts_b:
                    st.error("請選擇買入行權價")
                elif sk in ("bull","bear") and (sel_s_val == "請選擇" or sel_s_val not in opts_s):
                    st.error("請選擇賣出行權價")
                else:
                    bR = opts_b[sel_b_val]
                    bK = bR["k"]; bP = bR["ask"]
                    if sk in ("bull","bear"):
                        sR = opts_s[sel_s_val]
                        sK = sR["k"]; sP = sR["bid"]
                    else:
                        sK = 0; sP = 0

                    if sk == "bull":
                        nc=bP-sP; maxP=(sK-bK-nc)*100; maxL=nc*100; be_val=bK+nc
                    elif sk == "bear":
                        nc=bP-sP; maxP=(bK-sK-nc)*100; maxL=nc*100; be_val=bK-nc
                    elif sk == "call":
                        maxP=None; maxL=bP*100; be_val=bK+bP
                    else:
                        maxP=None; maxL=bP*100; be_val=bK-bP

                    show_result(sk, bK, bP, sK, sP, maxP, maxL, be_val, cur)

                    if st.button("⭐ 收藏這個組合", key="fav_calc"):
                        add_fav({"sk":sk,"ticker":ticker,"expiry":expiry,"currentPrice":cur,
                                 "bK":bK,"bP":bP,"sK":sK,"sP":sP,
                                 "maxProfit":maxP,"maxLoss":maxL,"breakeven":be_val})
                        st.success("已收藏！")

    st.markdown('</div>', unsafe_allow_html=True)

# ══════ TAB 2: AI 掃描 ══════
with tab2:
    st.markdown('''<div style="background:#0D4429;border:1px solid #1A6B36;border-radius:12px;padding:14px;margin:0 16px 16px">
      <div style="font-size:13px;color:#3FB950;font-weight:700;margin-bottom:4px">🤖 AI 智能分析</div>
      <div style="font-size:12px;color:#484F58;line-height:1.5">上傳 1-3 張期權鏈截圖，AI 讀取數字，程式精算損益<br>自動排除盈虧比過低的組合</div></div>''', unsafe_allow_html=True)
    st.session_state["scan_ticker"] = st.text_input("股票代號", placeholder="DKNG / ORCL", key="stk").upper()
    scan_expiry = st.text_input("到期日", placeholder="2026-08-21", key="exp2")
    scan_info = get_stock_info(st.session_state["scan_ticker"]) if st.session_state.get("scan_ticker") else {}
    scan_price = scan_info.get("price")
    if st.session_state.get("scan_ticker") and scan_price:
        stock_card(scan_info, st.session_state["scan_ticker"])
    uploaded = st.file_uploader("上傳截圖（最多3張）", type=["png","jpg","jpeg","webp"], accept_multiple_files=True)
    if uploaded:
        b64s = [compress_image(f) for f in uploaded[:3]]
        with st.expander(f"📷 已上傳 {len(uploaded[:3])} 張（點擊查看）"):
            cols = st.columns(min(len(uploaded),3))
            for i,f in enumerate(uploaded[:3]):
                with cols[i]: st.image(f, use_container_width=True)
        if st.button("🤖 AI 分析最佳組合", key="scan_btn"):
            if not api_key:
                st.error("請先設定 API Key")
            else:
                with st.spinner("AI 讀取數據中..."):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        ph = f"現價 ${scan_price}。" if scan_price else "請從截圖讀取現價。"
                        if scan_expiry: ph += f" 到期日：{scan_expiry}。"
                        prompt = f"""讀取期權鏈截圖（{st.session_state.get('scan_ticker','未知')}）。{ph}
讀取每個行權價的 callBid/callAsk/putBid/putAsk。
只回純JSON：{{"currentPrice":29.0,"rows":[{{"strike":30,"callBid":2.36,"callAsk":2.42,"putBid":3.10,"putAsk":3.20}}]}}"""
                        parts = [{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b}} for b in b64s]
                        parts.append({"type":"text","text":prompt})
                        msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=2000, messages=[{"role":"user","content":parts}])
                        text = msg.content[0].text.strip()
                        m = re.search(r'\{[\s\S]*\}', text)
                        if not m: st.error("讀取失敗："+text[:200])
                        else:
                            chain = json.loads(m.group())
                            cur2 = scan_price or chain.get("currentPrice",0)
                            st.session_state["scan_result"] = compute_strategies(chain.get("rows",[]), cur2, st.session_state.get("scan_ticker",""), scan_expiry)
                    except Exception as e: st.error(f"失敗：{e}")

    if st.session_state.get("scan_result"):
        res = st.session_state["scan_result"]; cur2=res["cur"]; tkr=res["ticker"]
        allc = res["bull"]+res["bear"]+res["call"]
        if not allc: st.error("找不到有效組合")
        else:
            max_ror = max(x["ror"] for x in allc)
            st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:flex-end;padding:6px 16px 12px;border-bottom:1px solid #30363D;margin-bottom:12px"><div><div style="font-size:20px;font-weight:900;letter-spacing:-0.5px">{tkr}</div><div style="font-size:11px;color:#8B949E">現價 ${fmt(cur2)}</div></div><div style="text-align:right"><div style="font-size:10px;color:#8B949E;font-weight:700">最高投資報酬率</div><div style="font-size:18px;font-weight:800;color:#3FB950">{max_ror:.0f}%</div></div></div>', unsafe_allow_html=True)
            top3 = res.get("top3",[])
            if top3:
                st.markdown('<div style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin:0 16px 8px">整體最佳 Top 3</div>', unsafe_allow_html=True)
                for t3 in top3:
                    typ=t3["type"]; medal=t3.get("_medal","")
                    medal_txt={"🥇":"金牌","🥈":"銀牌","🥉":"銅牌"}.get(medal,"")
                    tname={"bull":"看漲價差","bear":"看跌價差","call":"單買Call"}.get(typ,"")
                    strikes=f"${fmt(t3.get('buyStrike',0))} / ${fmt(t3.get('sellStrike',0))}" if typ in ("bull","bear") else f"${fmt(t3.get('strike',0))} Call"
                    with st.expander(f"{medal_txt}｜{tname} {strikes}｜{t3['ror']:.0f}%", expanded=(medal=="🥇")):
                        st.markdown(f'<div style="font-size:22px;text-align:center;margin-bottom:4px">{medal}</div>', unsafe_allow_html=True)
                        render_ai_combo(t3, cur2, typ, save_key=f"save_top_{medal}")
            def show_group(items, label):
                if not items: return
                st.markdown(f'<div style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 16px 8px">{label}</div>', unsafe_allow_html=True)
                for idx,it in enumerate(items):
                    typ=it["type"]; tname={"bull":"看漲價差","bear":"看跌價差","call":"單買Call"}.get(typ,"")
                    strikes=f"${fmt(it.get('buyStrike',0))} / ${fmt(it.get('sellStrike',0))}" if typ in ("bull","bear") else f"${fmt(it.get('strike',0))} Call"
                    with st.expander(f"{tname} {strikes} · 平衡${fmt(it.get('breakeven',0))} · {it['ror']:.0f}%"):
                        render_ai_combo(it, cur2, typ, save_key=f"save_{typ}_{idx}")
            show_group(res["bull"],"📈 看漲價差 Bull Call — Top 3")
            show_group(res["bear"],"📉 看跌價差 Bear Put — Top 3")
            show_group(res["call"],"📞 單買 Call — Top 2")

# ══════ TAB 3: 我的組合 ══════
with tab3:
    favs = load_favs()
    if not favs:
        st.markdown('<div style="background:#161B22;border-radius:12px;padding:28px;text-align:center;color:#8B949E;font-size:13px;margin:0 16px">尚無收藏<br><span style="font-size:11px">在選股計算或AI掃描後點 ⭐ 收藏</span></div>', unsafe_allow_html=True)
    else:
        groups = {}
        for f in favs: groups.setdefault(f.get("ticker","未命名"),[]).append(f)
        for tk, items in groups.items():
            st.markdown(f'<div style="font-size:15px;font-weight:800;margin:14px 16px 8px">📌 {tk} <span style="font-size:11px;color:#8B949E;font-weight:400">{len(items)} 個</span></div>', unsafe_allow_html=True)
            for f in items:
                typ=f.get("sk",""); tname={"bull":"看漲價差","bear":"看跌價差","call":"單買Call","put":"單買Put"}.get(typ,"")
                bK=f.get("bK",0); sK=f.get("sK",0)
                strikes=f"${bK} / ${sK}" if sK else f"${bK} {typ.upper()}"
                ror_v = f.get("maxProfit",0)/f.get("maxLoss",1)*100 if f.get("maxProfit") and f.get("maxLoss") else 0
                with st.expander(f"{tname} {strikes} · {ror_v:.0f}%"):
                    if f.get("maxProfit") is not None:
                        show_result(typ,bK,f.get("bP",0),sK,f.get("sP",0),f.get("maxProfit"),f.get("maxLoss",0),f.get("breakeven"),f.get("currentPrice",0))
                    if st.button("🗑 移除", key=f"del_{f.get('_id','')}"):
                        save_favs([x for x in load_favs() if x.get("_id")!=f.get("_id")]); st.rerun()

# ══════ TAB 4: 說明 ══════
with tab4:
    st.markdown('''<div style="padding:0 16px;color:#E6EDF3">
    <div style="background:#161B22;border-radius:12px;padding:14px;margin-bottom:12px">
      <div style="font-size:11px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">策略說明</div>
      <div style="font-size:13px;color:#8B949E;line-height:1.6"><b style="color:#E6EDF3">看漲價差</b> — 買低Call賣高Call，限定獲利和風險<br><br><b style="color:#E6EDF3">看跌價差</b> — 買高Put賣低Put，限定獲利和風險<br><br><b style="color:#E6EDF3">單買Call/Put</b> — 無限獲利潛力，最多虧損全部權利金</div></div>
    <div style="background:#161B22;border-radius:12px;padding:14px;margin-bottom:12px">
      <div style="font-size:11px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">AI 排序原則</div>
      <div style="font-size:13px;color:#8B949E;line-height:1.6">以「最不容易賠錢」優先：<br>1. 損益平衡接近現價<br>2. 成本（最大虧損）低<br>3. 盈虧比合理</div></div>
    </div>''', unsafe_allow_html=True)
