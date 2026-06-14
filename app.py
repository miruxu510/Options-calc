import streamlit as st
import anthropic, base64, json, math, re, io
from PIL import Image
try: import yfinance as yf; HAS_YF=True
except: HAS_YF=False
try: from streamlit_local_storage import LocalStorage; HAS_LS=True
except: HAS_LS=False

st.set_page_config(page_title="Options Pro", page_icon="📈", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
*{font-family:Inter,-apple-system,sans-serif!important;box-sizing:border-box}
.stApp{background:#0D1117;color:#E6EDF3}
.main .block-container{padding:0 0 80px;max-width:430px}
#MainMenu,footer,header{visibility:hidden}
[data-testid="stToolbar"]{display:none}
.stTabs [data-baseweb="tab-list"]{background:#161B22;border-radius:0;padding:0 16px;gap:0;border:none;border-bottom:1px solid #30363D;margin-bottom:0}
.stTabs [data-baseweb="tab"]{background:transparent!important;border-radius:0!important;color:#8B949E;font-size:13px;font-weight:600;padding:12px 14px;border:none!important;border-bottom:2px solid transparent!important}
.stTabs [aria-selected="true"]{color:#E6EDF3!important;border-bottom:2px solid #1F6FEB!important}
.stTabs [data-baseweb="tab-highlight"],[data-baseweb="tab-border"]{display:none}
.stTextInput>div>div{background:#1C2128!important;border:1px solid #30363D!important;border-radius:10px!important}
.stTextInput input{background:#1C2128!important;border:none!important;color:#E6EDF3!important;font-size:15px!important;font-weight:600!important;padding:10px 14px!important}
.stTextInput label{color:#8B949E!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:.8px}
.stSelectbox>div>div{background:#1C2128!important;border:1px solid #30363D!important;border-radius:10px!important;color:#E6EDF3!important;font-size:13px!important;font-weight:600!important}
.stSelectbox label{color:#8B949E!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:.8px}
.stButton>button{background:linear-gradient(135deg,#1F6FEB,#0C54C7)!important;color:#fff!important;border:none!important;border-radius:12px!important;font-size:16px!important;font-weight:800!important;padding:14px 20px!important;width:100%!important}
[data-testid="stExpander"]{background:#161B22!important;border:1px solid #30363D!important;border-radius:12px!important;margin-bottom:8px}
[data-testid="stExpander"] summary{color:#E6EDF3!important;font-weight:600!important;font-size:13px!important}
.stSuccess{background:#0D4429!important;border:1px solid #1A6B36!important;border-radius:10px!important;color:#3FB950!important}
.stError{background:#4A1015!important;border:1px solid #8B1A1A!important;border-radius:10px!important;color:#F85149!important}
hr{border-color:#30363D!important;margin:14px 0!important}
[data-testid="stFileUploader"]{background:#1C2128!important;border:1.5px dashed #30363D!important;border-radius:12px!important}
</style>
""", unsafe_allow_html=True)

api_key = st.secrets.get("ANTHROPIC_API_KEY","")

# ── helpers ──────────────────────────────────────────
def fmt(v,d=2):
    if v is None: return "—"
    return f"{v:.{d}f}"
def fmtm(v):
    if v is None: return "—"
    return f"{v:.0f}" if isinstance(v,(int,float)) and float(v)==int(float(v)) else f"{v:.2f}"
def compress(uf):
    img=Image.open(uf)
    if img.width>1200: img=img.resize((1200,int(img.height*1200/img.width)),Image.LANCZOS)
    if img.mode!="RGB": img=img.convert("RGB")
    buf=io.BytesIO(); img.save(buf,format="JPEG",quality=75); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# ── yfinance ─────────────────────────────────────────
@st.cache_data(ttl=60)
def get_info(sym):
    if not HAS_YF or not sym: return {}
    try:
        t=yf.Ticker(sym); out={}
        try:
            fi=t.fast_info
            p=fi.get("lastPrice") or fi.get("last_price")
            if p: out["price"]=round(float(p),2)
            prev=fi.get("previousClose") or fi.get("previous_close")
            if prev and out.get("price"):
                out["change"]=round(out["price"]-float(prev),2)
                out["pct"]=round((out["price"]-float(prev))/float(prev)*100,2)
        except: pass
        if not out.get("price"):
            h=t.history(period="2d")
            if not h.empty:
                out["price"]=round(float(h["Close"].iloc[-1]),2)
                if len(h)>=2:
                    prev2=float(h["Close"].iloc[-2])
                    out["change"]=round(out["price"]-prev2,2)
                    out["pct"]=round((out["price"]-prev2)/prev2*100,2)
        try:
            info=t.info
            out["name"]=info.get("longName") or info.get("shortName") or sym
            out["sector"]=info.get("sector",""); out["exchange"]=info.get("exchange","")
            tp=info.get("targetMeanPrice")
            if tp: out["target"]=round(float(tp),2)
            out["lo52"]=info.get("fiftyTwoWeekLow"); out["hi52"]=info.get("fiftyTwoWeekHigh")
        except: pass
        try:
            cal=t.calendar
            if isinstance(cal,dict):
                ed=cal.get("Earnings Date")
                if ed: out["nextER"]=str(ed[0] if isinstance(ed,list) else ed)[:10]
        except: pass
        return out
    except: return {}

@st.cache_data(ttl=120)
def get_expiries(sym):
    if not HAS_YF or not sym: return []
    try: return list(yf.Ticker(sym).options)
    except: return []

@st.cache_data(ttl=60)
def get_chain(sym, exp):
    if not HAS_YF or not sym or not exp: return [],[]
    try:
        opt=yf.Ticker(sym).option_chain(exp)
        calls=[{"k":r["strike"],"bid":round(r["bid"],2),"ask":round(r["ask"],2)} for r in opt.calls[["strike","bid","ask"]].dropna().to_dict("records")]
        puts=[{"k":r["strike"],"bid":round(r["bid"],2),"ask":round(r["ask"],2)} for r in opt.puts[["strike","bid","ask"]].dropna().to_dict("records")]
        return calls,puts
    except: return [],[]

# ── P&L ──────────────────────────────────────────────
def pnl(sk,bK,bP,sK,sP,price):
    if sk=="bull":
        nc=bP-sP
        if price<=bK: return -nc*100
        if price>=sK: return (sK-bK-nc)*100
        return (price-bK-nc)*100
    if sk=="bear":
        nc=bP-sP
        if price>=bK: return -nc*100
        if price<=sK: return (bK-sK-nc)*100
        return (bK-price-nc)*100
    if sk=="call": return (max(price-bK,0)-bP)*100
    if sk=="put":  return (max(bK-price,0)-bP)*100
    return 0

def find_be(sk,bK,bP,sK,sP,cur):
    lo=min(bK,sK or bK,cur)*0.75; hi=max(bK,sK or bK,cur)*1.35
    pts=[lo+(hi-lo)*i/600 for i in range(601)]
    prev=pnl(sk,bK,bP,sK,sP,pts[0])
    for i in range(1,len(pts)):
        c=pnl(sk,bK,bP,sK,sP,pts[i])
        if (prev<=0 and c>0) or (prev>=0 and c<0):
            f=abs(prev)/(abs(prev)+abs(c)); return pts[i-1]+f*(pts[i]-pts[i-1])
        prev=c
    return None

def make_svg(sk,bK,bP,sK,sP,cur):
    unlimited=sk in("call","put"); pr=sk in("bull","call")
    be=find_be(sk,bK,bP,sK,sP,cur)
    allk=[bK,cur]+([sK]if sK else[])+([be]if be else[])
    center=be or cur; span=max(max(allk)-min(allk),cur*0.16)*1.5
    lo=center-span*0.55; hi=center+span*0.55
    pts=[lo+(hi-lo)*i/200 for i in range(201)]
    pnls=[pnl(sk,bK,bP,sK,sP,p) for p in pts]
    maxV=max(pnls); minV=min(pnls)
    W,H,pX,pTop,pBot,lH=380,230,14,26,10,34
    pH=H-pTop-pBot-lH; vpad=(maxV-minV)*0.18
    vT=maxV+vpad; vR=(vT-(minV-vpad)) or 1
    cx=lambda p:pX+((p-lo)/(hi-lo))*(W-2*pX)
    cy=lambda v:pTop+(vT-v)/vR*pH
    zY=cy(0)
    ld=" ".join(f"{'M'if i==0 else'L'}{cx(pts[i]):.1f},{cy(pnls[i]):.1f}" for i in range(len(pts)))
    fd=f"{ld} L{cx(hi):.1f},{zY:.1f} L{cx(lo):.1f},{zY:.1f} Z"
    tks="".join(f'<line x1="{cx(lo+(hi-lo)*i/5):.1f}" y1="{zY:.1f}" x2="{cx(lo+(hi-lo)*i/5):.1f}" y2="{zY+4:.1f}" stroke="#444" stroke-width=".8"/><text x="{cx(lo+(hi-lo)*i/5):.1f}" y="{zY+13:.1f}" fill="#444" font-size="7.5" text-anchor="middle">${lo+(hi-lo)*i/5:.0f}</text>' for i in range(6))
    cl=f'<line x1="{cx(cur):.1f}" y1="{pTop}" x2="{cx(cur):.1f}" y2="{H-pBot-lH}" stroke="#1F6FEB" stroke-width="1" stroke-dasharray="4 3" opacity=".5"/><text x="{cx(cur):.1f}" y="{pTop-4}" fill="#1F6FEB" font-size="9" text-anchor="middle" font-weight="600">現價 ${cur:.2f}</text>' if lo<cur<hi else ""
    dots=[(bK,True)]+([( sK,False)]if sK else[])
    ds=""
    for dk,buy in dots:
        if not(lo<dk<hi): continue
        dy=cy(pnl(sk,bK,bP,sK,sP,dk)); sx=cx(dk); mc="#60A5FA"if buy else"#FB923C"
        lbl=f"{'買入'if buy else'賣出'} ${dk:.0f}"; ab=dy>H*.45; by2=dy-27 if ab else dy+11
        ds+=f'<rect x="{sx-34:.1f}" y="{by2:.1f}" width="68" height="14" rx="3" fill="#0A0A0A" opacity=".92"/><text x="{sx:.1f}" y="{by2+11:.1f}" fill="{mc}" font-size="9" text-anchor="middle" font-weight="700">{lbl}</text><circle cx="{sx:.1f}" cy="{dy:.1f}" r="5" fill="{mc}"/><circle cx="{sx:.1f}" cy="{dy:.1f}" r="9" fill="{mc}" opacity=".18"/>'
    be_s=""
    if be and lo<be<hi:
        bx=cx(be)
        be_s=f'<rect x="{bx-36:.1f}" y="{zY-32:.1f}" width="72" height="24" rx="4" fill="#0A0A0A" opacity=".92"/><text x="{bx:.1f}" y="{zY-20:.1f}" fill="#F0B429" font-size="8" text-anchor="middle" font-weight="600">損益平衡</text><text x="{bx:.1f}" y="{zY-9:.1f}" fill="#F0B429" font-size="10" text-anchor="middle" font-weight="800">${be:.2f}</text><circle cx="{bx:.1f}" cy="{zY:.1f}" r="5" fill="#F0B429"/><circle cx="{bx:.1f}" cy="{zY:.1f}" r="9" fill="#F0B429" opacity=".22"/>'
    bY=H-lH+14; bY2=H-lH+27
    pX1=W-pX-4 if pr else pX+4; pA1="end"if pr else"start"
    lX1=pX+4 if pr else W-pX-4; lA1="start"if pr else"end"
    mp=("∞"if unlimited else f"+${maxV:.0f}"); ml=f"-${abs(minV):.0f}"
    return f'''<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block;background:#0D1117;border-radius:14px;margin-top:10px">
  <defs><clipPath id="cpp"><rect x="{pX}" y="{pTop}" width="{W-2*pX}" height="{max(zY-pTop,0):.1f}"/></clipPath>
  <clipPath id="cpl"><rect x="{pX}" y="{zY:.1f}" width="{W-2*pX}" height="{max(pH-(zY-pTop)+pBot+4,0):.1f}"/></clipPath></defs>
  <line x1="{pX}" y1="{zY:.1f}" x2="{W-pX}" y2="{zY:.1f}" stroke="#2A2A2A" stroke-width="1" stroke-dasharray="4 3"/>
  {tks}{cl}
  <path d="{fd}" fill="#4ADE80" opacity=".18" clip-path="url(#cpp)"/>
  <path d="{fd}" fill="#F87171" opacity=".18" clip-path="url(#cpl)"/>
  <path d="{ld}" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cpp)"/>
  <path d="{ld}" fill="none" stroke="#F87171" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cpl)"/>
  {ds}{be_s}
  <text x="{pX1}" y="{bY}" fill="#4ADE80" font-size="8" font-weight="700" text-anchor="{pA1}">最大獲利</text>
  <text x="{pX1}" y="{bY2}" fill="#4ADE80" font-size="12" font-weight="800" text-anchor="{pA1}">{mp}</text>
  <text x="{lX1}" y="{bY}" fill="#F87171" font-size="8" font-weight="700" text-anchor="{lA1}">最大虧損</text>
  <text x="{lX1}" y="{bY2}" fill="#F87171" font-size="12" font-weight="800" text-anchor="{lA1}">{ml}</text>
</svg>'''

def make_ladder(sk,bK,bP,sK,sP,maxL,be,cur):
    spread=abs(bK-sK)if sK else bP*5
    step=1 if spread<5 else 1 if spread<=10 else 2.5 if spread<=20 else 5 if spread<=50 else 10
    lo=math.floor(min([bK]+([sK]if sK else[])+[cur])*0.88/step)*step
    hi=math.ceil(max([bK]+([sK]if sK else[])+[cur])*1.12/step)*step
    rows=[]; p=lo
    while p<=hi+0.001:
        v=pnl(sk,bK,bP,sK,sP,p); ret=v/maxL*100 if maxL else 0
        nb=be is not None and abs(p-be)<=step*0.55
        im=(sk=="bull" and sK and p>=sK)or(sk=="bear" and sK and p<=sK)
        rows.append({"p":p,"v":v,"ret":ret,"nb":nb,"im":im})
        p=round(p+step,3)
    # trim
    mi=0; mxi=len(rows)-1
    for i in range(1,len(rows)):
        if rows[i]["v"]!=rows[0]["v"]: mi=max(0,i-1); break
    if sK:
        for i,r in enumerate(rows):
            if r["im"]: mxi=min(i+5,len(rows)-1); break
    rows=rows[mi:mxi+1]
    ss=fmtm(step)
    h=f'<div style="background:#1C2128;border-radius:12px;overflow:hidden;margin-top:12px"><div style="padding:8px 12px;display:flex;justify-content:space-between;border-bottom:1px solid #30363D"><span style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px">損益對照表</span><span style="font-size:10px;color:#484F58;background:#21262D;padding:1px 8px;border-radius:100px">每 ${ss}</span></div>'
    h+='<table style="width:100%;border-collapse:collapse"><thead><tr style="background:#21262D"><th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:left;font-weight:700;text-transform:uppercase">股價</th><th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:right;font-weight:700;text-transform:uppercase">損益/張</th><th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:right;font-weight:700;text-transform:uppercase">報酬率</th></tr></thead><tbody>'
    for r in rows:
        col="#4ADE80"if r["v"]>0 else"#F87171"if r["v"]<0 else"#F0B429"
        bg="rgba(74,222,128,.05)"if r["v"]>1 else"rgba(248,113,113,.05)"if r["v"]<-1 else"rgba(240,180,41,.06)"
        ps=f"${r['p']:.0f}"if r['p']%1==0 else f"${r['p']:.2f}"
        tags=('  <span style="font-size:8px;background:#1A1000;color:#F0B429;padding:1px 5px;border-radius:100px;font-weight:700">平衡</span>'if r["nb"] else"")+('  <span style="font-size:8px;background:#0D2010;color:#4ADE80;padding:1px 5px;border-radius:100px;font-weight:700">MAX</span>'if r["im"] else"")
        pstr=f"{'+'if r['v']>=0 else''}${abs(r['v']):.0f}"; rstr=f"{'+'if r['ret']>=0 else''}{r['ret']:.0f}%"
        h+=f'<tr style="background:{bg};border-bottom:1px solid #161B22"><td style="font-size:12px;color:#E6EDF3;padding:6px 12px;font-weight:500">{ps}{tags}</td><td style="font-size:12px;color:{col};padding:6px 12px;text-align:right;font-weight:600">{pstr}</td><td style="font-size:12px;color:{col};padding:6px 12px;text-align:right;font-weight:600">{rstr}</td></tr>'
    h+="</tbody></table></div>"
    return h

def show_result(sk,bK,bP,sK,sP,maxP,maxL,be,cur):
    unlimited=sk in("call","put")
    mp=("∞"if unlimited else f"${fmtm(maxP)}"); mps="" if unlimited else f"+{maxP/maxL*100:.0f}%"
    ror=("∞"if unlimited else f"{maxP/maxL*100:.0f}%"); be_s=f"${fmt(be)}"if be else"—"
    st.markdown(f'''
    <div style="background:#161B22;border:1px solid #30363D;border-radius:14px;padding:14px;margin-top:8px">
      <div style="font-size:14px;font-weight:700;margin-bottom:12px">損益總覽</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:12px">
        <div style="background:#0D4429;border:1.5px solid #1A6B36;border-radius:10px;padding:10px 8px">
          <div style="font-size:9px;color:#86EFAC;font-weight:700;margin-bottom:3px">最大獲利</div>
          <div style="font-size:16px;font-weight:900;color:#4ADE80">{mp}</div>
          <div style="font-size:9px;color:#4ADE80;margin-top:1px">{mps}</div></div>
        <div style="background:#4A1015;border:1.5px solid #8B1A1A;border-radius:10px;padding:10px 8px">
          <div style="font-size:9px;color:#FCA5A5;font-weight:700;margin-bottom:3px">最大虧損</div>
          <div style="font-size:16px;font-weight:900;color:#F87171">-${fmtm(maxL)}</div>
          <div style="font-size:9px;color:#F87171;margin-top:1px">-{maxL/(maxL+(maxP or maxL))*100:.0f}%</div></div>
        <div style="background:#1C2128;border:1.5px solid #30363D;border-radius:10px;padding:10px 8px">
          <div style="font-size:9px;color:#8B949E;font-weight:700;margin-bottom:3px">報酬率</div>
          <div style="font-size:16px;font-weight:900;color:#E6EDF3">{ror}</div></div>
        <div style="background:#2D1F52;border:1.5px solid #6E40C9;border-radius:10px;padding:10px 8px">
          <div style="font-size:9px;color:#C4B5FD;font-weight:700;margin-bottom:3px">損益平衡</div>
          <div style="font-size:16px;font-weight:900;color:#A78BFA">{be_s}</div></div>
      </div>
    </div>''', unsafe_allow_html=True)
    st.markdown(make_svg(sk,bK,bP,sK,sP,cur), unsafe_allow_html=True)
    st.markdown(make_ladder(sk,bK,bP,sK,sP,maxL,be,cur), unsafe_allow_html=True)

def stock_card(info, ticker):
    p=info.get("price",0); chg=info.get("change",0); pct=info.get("pct",0)
    name=info.get("name",ticker); tgt=info.get("target"); lo52=info.get("lo52"); hi52=info.get("hi52")
    nextER=info.get("nextER","—"); exch=info.get("exchange",""); sec=info.get("sector","")
    cc="#F85149"if chg<0 else"#3FB950"
    up=round((tgt-p)/p*100,1)if tgt and p else None; uc="#3FB950"if up and up>=0 else"#F85149"
    bar=round((p-lo52)/(hi52-lo52)*100)if lo52 and hi52 and hi52>lo52 else 50
    bar=max(0,min(100,bar))
    tgt_html=f'<div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:10px;color:#8B949E;font-weight:600">分析師目標</span><div><span style="font-size:11px;font-weight:700">${tgt:.2f}</span><span style="font-size:10px;color:{uc};margin-left:4px;font-weight:600">{"+" if up and up>=0 else""}{up:.1f}%</span></div></div>'if tgt else""
    rng_html=f'<div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:10px;color:#8B949E;font-weight:600">52週區間</span><div style="text-align:right"><span style="font-size:11px;font-weight:700">{lo52:.0f}–{hi52:.0f}</span><div style="background:#21262D;border-radius:100px;height:3px;margin-top:3px;width:56px;position:relative;margin-left:auto"><div style="position:absolute;left:{bar}%;top:-2px;width:7px;height:7px;background:#1F6FEB;border-radius:50%;transform:translateX(-50%)"></div></div></div></div>'if lo52 and hi52 else""
    badges="".join([f'<span style="font-size:10px;background:#21262D;color:#8B949E;padding:2px 6px;border-radius:4px">{x}</span>'for x in[exch,sec]if x])
    st.markdown(f'''<div style="background:#161B22;border:1px solid #30363D;border-radius:14px;padding:14px;margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
        <div style="display:flex;gap:10px;align-items:center">
          <div style="width:40px;height:40px;background:#1F6FEB;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;color:#fff;flex-shrink:0">{ticker}</div>
          <div><div style="font-size:13px;font-weight:700">{name}</div><div style="display:flex;gap:5px;margin-top:3px;flex-wrap:wrap">{badges}</div></div>
        </div>
        <div style="text-align:right;flex-shrink:0">
          <div style="font-size:22px;font-weight:900;letter-spacing:-.5px">${p:.2f}</div>
          <div style="font-size:12px;color:{cc};font-weight:600">{chg:+.2f} ({pct:+.2f}%)</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
        {tgt_html}{rng_html}
        <div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:10px;color:#8B949E;font-weight:600">下一財報</span><span style="font-size:11px;font-weight:700;color:#F79000">{nextER}</span></div>
        <div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center"><span style="font-size:10px;color:#8B949E;font-weight:600">即時連線</span><span style="font-size:11px;font-weight:700;color:#3FB950">● 已連線</span></div>
      </div></div>''', unsafe_allow_html=True)

# ── local storage ─────────────────────────────────────
if HAS_LS:
    try: ls=LocalStorage()
    except: ls=None
else: ls=None

def load_favs():
    if ls:
        try:
            raw=ls.getItem("opt_favs"); return json.loads(raw)if raw else[]
        except: return[]
    return st.session_state.get("_favs",[])

def save_favs(favs):
    if ls:
        try: ls.setItem("opt_favs",json.dumps(favs))
        except: pass
    st.session_state["_favs"]=favs

def add_fav(combo):
    favs=load_favs(); combo["_id"]=f"{combo.get('ticker','')}_{len(favs)}"; favs.insert(0,combo); save_favs(favs)

# ── compute for AI scan ───────────────────────────────
def compute(rows,cur,ticker,expiry):
    valid=sorted([r for r in rows if r.get("strike")is not None],key=lambda r:r["strike"])
    bulls,bears,calls=[],[],[]
    for i in range(len(valid)):
        for j in range(i+1,len(valid)):
            lo,hi=valid[i],valid[j]
            ba=lo.get("callAsk"); sb=hi.get("callBid")
            if ba and sb and ba>0:
                nc=ba-sb
                if nc>0:
                    sp=hi["strike"]-lo["strike"]; maxP=(sp-nc)*100; maxL=nc*100
                    if maxP>0 and maxP/maxL>=1 and cur and(lo["strike"]-cur)/cur<=.10:
                        be=lo["strike"]+nc; ror=maxP/maxL*100; pg=max((be-cur)/cur,0)
                        s=(1/(1+pg*5))*100*.5+min(ror,300)/3*.3+(1/(1+maxL/200))*100*.2
                        bulls.append({"type":"bull","buyStrike":lo["strike"],"buyPremium":round(ba,2),"sellStrike":hi["strike"],"sellPremium":round(sb,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_s":s})
            ba=hi.get("putAsk"); sb=lo.get("putBid")
            if ba and sb and ba>0:
                nc=ba-sb
                if nc>0:
                    sp=hi["strike"]-lo["strike"]; maxP=(sp-nc)*100; maxL=nc*100
                    if maxP>0 and maxP/maxL>=1 and cur and(cur-hi["strike"])/cur<=.10:
                        be=hi["strike"]-nc; ror=maxP/maxL*100; pg=max((cur-be)/cur,0)
                        s=(1/(1+pg*5))*100*.5+min(ror,300)/3*.3+(1/(1+maxL/200))*100*.2
                        bears.append({"type":"bear","buyStrike":hi["strike"],"buyPremium":round(ba,2),"sellStrike":lo["strike"],"sellPremium":round(sb,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_s":s})
    for r in valid:
        ba=r.get("callAsk")
        if ba and ba>0 and cur and abs(r["strike"]-cur)/cur<=.12:
            be=r["strike"]+ba; maxP=(cur*1.2-r["strike"]-ba)*100; maxL=ba*100
            if maxP>0:
                ror=maxP/maxL*100; pg=max((be-cur)/cur,0)
                s=(1/(1+pg*4))*100*.6+min(ror,200)/2*.2+(1/(1+maxL/300))*100*.2
                calls.append({"type":"call","strike":r["strike"],"premium":round(ba,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_s":s})
    bulls.sort(key=lambda x:-x["_s"]); bears.sort(key=lambda x:-x["_s"]); calls.sort(key=lambda x:-x["_s"])
    B,R,L=bulls[:3],bears[:3],calls[:2]
    def asgn(items):
        for it in items:
            it["stars"]=5 if it["_s"]>=90 else 4 if it["_s"]>=70 else 3 if it["_s"]>=50 else 2
            pros=[]; cons=[]
            if it["rr"]>=2: pros.append("盈虧比佳")
            if it["maxLoss"]<=150: pros.append("成本低")
            bd=abs(it["breakeven"]-cur)/cur*100 if cur else 0
            if bd<=5: pros.append("接近現價")
            if it["rr"]<1.5: cons.append("盈虧比偏低")
            if it["maxLoss"]>300: cons.append("成本較高")
            if bd>8: cons.append(f"需變動{bd:.0f}%")
            it["pros"]="、".join(pros)or"風險可控"; it["cons"]="、".join(cons)or"注意時間價值"
    asgn(B);asgn(R);asgn(L)
    everything=sorted(B+R+L,key=lambda x:-x["_s"])
    for i,t in enumerate(everything[:3]): t["_medal"]=["🥇","🥈","🥉"][i]
    return{"cur":cur,"ticker":ticker,"expiry":expiry,"bull":B,"bear":R,"call":L,"top3":everything[:3]}

def render_combo(it,cur,typ,key=None):
    unlimited=typ in("call","put")
    mp=it.get("maxProfit",0);ml=it.get("maxLoss",0);be=it.get("breakeven",0);ror=it.get("ror",0)
    mp_s="∞"if unlimited else f"${fmtm(mp)}"; ror_s="∞"if unlimited else f"{ror:.0f}%"
    st.markdown(f'''<div style="display:flex;gap:6px;margin:8px 0">
      <div style="flex:1;background:#0D4429;border:1.5px solid #1A6B36;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#86EFAC;font-weight:700;margin-bottom:3px">最大獲利</div>
        <div style="font-size:15px;font-weight:900;color:#4ADE80">{mp_s}</div></div>
      <div style="flex:1;background:#4A1015;border:1.5px solid #8B1A1A;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#FCA5A5;font-weight:700;margin-bottom:3px">最大虧損</div>
        <div style="font-size:15px;font-weight:900;color:#F87171">-${fmtm(ml)}</div></div>
      <div style="flex:1;background:#1C2128;border:1.5px solid #30363D;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#8B949E;font-weight:700;margin-bottom:3px">報酬率</div>
        <div style="font-size:15px;font-weight:900;color:#E6EDF3">{ror_s}</div></div>
      <div style="flex:1;background:#2D1F52;border:1.5px solid #6E40C9;border-radius:10px;padding:10px 8px;text-align:center">
        <div style="font-size:9px;color:#C4B5FD;font-weight:700;margin-bottom:3px">損益平衡</div>
        <div style="font-size:15px;font-weight:900;color:#A78BFA">${fmt(be)}</div></div>
    </div>''',unsafe_allow_html=True)
    if it.get("pros")or it.get("cons"):
        st.markdown(f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0">
          <div style="background:#0D4429;border:1px solid #1A6B36;border-radius:9px;padding:8px 10px">
            <div style="font-size:9px;color:#3FB950;font-weight:700;margin-bottom:2px">✓ 優點</div>
            <div style="font-size:11px;color:#8B949E">{it.get("pros","")}</div></div>
          <div style="background:#4A1015;border:1px solid #8B1A1A;border-radius:9px;padding:8px 10px">
            <div style="font-size:9px;color:#F85149;font-weight:700;margin-bottom:2px">✗ 缺點</div>
            <div style="font-size:11px;color:#8B949E">{it.get("cons","")}</div></div>
        </div>''',unsafe_allow_html=True)
    legs={}
    if typ=="bull": legs={"bK":it["buyStrike"],"bP":it["buyPremium"],"sK":it["sellStrike"],"sP":it["sellPremium"]}
    elif typ=="bear": legs={"bK":it["buyStrike"],"bP":it["buyPremium"],"sK":it["sellStrike"],"sP":it["sellPremium"]}
    elif typ=="call": legs={"bK":it["strike"],"bP":it["premium"],"sK":0,"sP":0}
    if legs: st.markdown(make_svg(typ,legs["bK"],legs["bP"],legs.get("sK",0),legs.get("sP",0),cur),unsafe_allow_html=True)
    if key and st.button("⭐ 收藏",key=key):
        add_fav({**it,"ticker":st.session_state.get("scan_tkr",""),"sk":typ}); st.success("已收藏！")

# ── header ────────────────────────────────────────────
st.markdown('''<div style="background:#161B22;padding:12px 16px 10px;border-bottom:1px solid #30363D;display:flex;align-items:center;gap:10px;margin:0 -1px">
  <div style="width:28px;height:28px;background:#1F6FEB;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:#fff;flex-shrink:0">F</div>
  <div><div style="font-size:9px;color:#8B949E;font-weight:600;letter-spacing:1px">OPTIONS</div><div style="font-size:16px;font-weight:800;letter-spacing:-.5px">Strategy Pro</div></div>
</div>''',unsafe_allow_html=True)

tab1,tab2,tab3,tab4=st.tabs(["選股計算","AI 掃描","我的組合","說明"])

# ══════ TAB 1 ══════
with tab1:
    st.markdown('<div style="padding:12px 16px 0">',unsafe_allow_html=True)

    # Watchlist — horizontal scroll chips using HTML
    WATCHLIST=["MU","NVDA","ORCL","DKNG","AAPL","TSLA","AMZN","MSFT","IBIT","SRAD","FLUT","META"]
    chip_style="display:inline-block;background:#1C2128;border:1px solid #30363D;border-radius:100px;padding:5px 12px;color:#8B949E;font-size:12px;font-weight:700;margin:2px;cursor:pointer;text-decoration:none;white-space:nowrap"
    chips="".join(f'<a href="?t={t}" style="{chip_style}">{t}</a>' for t in WATCHLIST)
    st.markdown(f'<div style="overflow-x:auto;white-space:nowrap;margin-bottom:10px;padding-bottom:4px">{chips}</div>',unsafe_allow_html=True)

    # Read ticker from query params (set by chip click)
    qp=st.query_params
    default_ticker=qp.get("t","").upper()

    c1,c2=st.columns([2,1])
    ticker=c1.text_input("股票代號",placeholder="MU / ORCL / DKNG",key="tk",value=default_ticker).upper().strip()
    expiries=get_expiries(ticker)if ticker else[]
    expiry=c2.selectbox("到期日",expiries if expiries else["—"],key="exp")if expiries else None

    info={}; calls_d,puts_d=[],[]
    if ticker:
        with st.spinner("載入中..."):
            info=get_info(ticker)
        if info.get("price"):
            stock_card(info,ticker)
            if expiry and expiry!="—":
                calls_d,puts_d=get_chain(ticker,expiry)
        elif ticker:
            st.error(f"找不到 {ticker} 的資料")

    if calls_d or puts_d:
        cur=info.get("price",0)
        calls_f=[r for r in calls_d if cur*0.7<=r["k"]<=cur*1.3]
        puts_f=[r for r in puts_d if cur*0.7<=r["k"]<=cur*1.3]

        STRAT_MAP={"看漲價差 Bull Call Spread":"bull","看跌價差 Bear Put Spread":"bear","單買 Call":"call","單買 Put":"put"}
        TIPS={"bull":"買低Call賣高Call，看漲限風險，最大獲利固定。","bear":"買高Put賣低Put，看跌限風險，最大獲利固定。","call":"直接買入Call，無限獲利潛力，最多虧損全部權利金。","put":"直接買入Put，跌越多賺越多，最多虧損全部權利金。"}

        sc1,sc2=st.columns([4,1])
        sk_lbl=sc1.selectbox("策略",list(STRAT_MAP.keys()),key="sk",label_visibility="collapsed")
        sk=STRAT_MAP[sk_lbl]
        if sc2.button("ⓘ",key="tip"):
            st.info(TIPS[sk])

        arr_b=calls_f if sk in("bull","call") else puts_f
        arr_s=calls_f if sk=="bull" else puts_f if sk=="bear" else[]
        opts_b={f"${r['k']:.0f} · Ask ${r['ask']:.2f}":r for r in sorted(arr_b,key=lambda r:r["k"])}
        opts_s={f"${r['k']:.0f} · Bid ${r['bid']:.2f}":r for r in sorted(arr_s,key=lambda r:r["k"])} if arr_s else{}

        # Leg cards using HTML table for side-by-side on mobile
        if sk in("bull","bear"):
            b_lbl="買入 Call"if sk=="bull"else"買入 Put"
            s_lbl="賣出 Call"if sk=="bull"else"賣出 Put"
            st.markdown(f'''<table style="width:100%;border-collapse:separate;border-spacing:8px 0;margin:8px -8px;width:calc(100% + 16px)">
              <tr>
                <td style="background:#0C2D6B;border:1.5px solid #1F6FEB;border-radius:14px;padding:12px;width:50%;vertical-align:top">
                  <div style="font-size:11px;font-weight:700;color:#1F6FEB;margin-bottom:8px">{b_lbl} (Long)</div>
                </td>
                <td style="background:#0D4429;border:1.5px solid #1A6B36;border-radius:14px;padding:12px;width:50%;vertical-align:top">
                  <div style="font-size:11px;font-weight:700;color:#3FB950;margin-bottom:8px">{s_lbl} (Short)</div>
                </td>
              </tr>
            </table>''',unsafe_allow_html=True)
            c1,c2=st.columns(2)
            with c1:
                sel_b=st.selectbox("買入",["請選擇"]+list(opts_b.keys()),key="selb",label_visibility="collapsed")
                bR=opts_b.get(sel_b)
                if bR: st.markdown(f'<div style="font-size:10px;color:#8B949E">Ask 權利金</div><div style="font-size:22px;font-weight:900">${bR["ask"]:.2f}</div>',unsafe_allow_html=True)
            with c2:
                sel_s=st.selectbox("賣出",["請選擇"]+list(opts_s.keys()),key="sels",label_visibility="collapsed")
                sR=opts_s.get(sel_s)
                if sR: st.markdown(f'<div style="font-size:10px;color:#8B949E">Bid 權利金</div><div style="font-size:22px;font-weight:900">${sR["bid"]:.2f}</div>',unsafe_allow_html=True)
        else:
            b_lbl="買入 Call"if sk=="call"else"買入 Put"
            st.markdown(f'<div style="background:#0C2D6B;border:1.5px solid #1F6FEB;border-radius:14px;padding:12px;margin-bottom:10px"><div style="font-size:11px;font-weight:700;color:#1F6FEB;margin-bottom:8px">{b_lbl} (Long)</div></div>',unsafe_allow_html=True)
            sel_b=st.selectbox("行權價",["請選擇"]+list(opts_b.keys()),key="selb",label_visibility="collapsed")
            bR=opts_b.get(sel_b)
            if bR: st.markdown(f'<div style="font-size:10px;color:#8B949E">Ask 權利金</div><div style="font-size:22px;font-weight:900">${bR["ask"]:.2f}</div>',unsafe_allow_html=True)
            sel_s="請選擇"; sR=None

        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("計算損益",key="calc"):
            bR=opts_b.get(st.session_state.get("selb",""))
            sR=opts_s.get(st.session_state.get("sels",""))if sk in("bull","bear")else None
            if not bR: st.error("請選擇買入行權價")
            elif sk in("bull","bear")and not sR: st.error("請選擇賣出行權價")
            else:
                bK=bR["k"];bP=bR["ask"]
                sK=sR["k"]if sR else 0;sP=sR["bid"]if sR else 0
                if sk=="bull": nc=bP-sP;maxP=(sK-bK-nc)*100;maxL=nc*100;be=bK+nc
                elif sk=="bear": nc=bP-sP;maxP=(bK-sK-nc)*100;maxL=nc*100;be=bK-nc
                elif sk=="call": maxP=None;maxL=bP*100;be=bK+bP
                else: maxP=None;maxL=bP*100;be=bK-bP
                show_result(sk,bK,bP,sK,sP,maxP,maxL,be,cur)
                if st.button("⭐ 收藏",key="fav_c"):
                    add_fav({"sk":sk,"ticker":ticker,"expiry":expiry,"currentPrice":cur,"bK":bK,"bP":bP,"sK":sK,"sP":sP,"maxProfit":maxP,"maxLoss":maxL,"breakeven":be})
                    st.success("已收藏！")

    st.markdown('</div>',unsafe_allow_html=True)

# ══════ TAB 2 ══════
with tab2:
    st.markdown('<div style="padding:0 16px">',unsafe_allow_html=True)
    st.markdown('''<div style="background:#0D4429;border:1px solid #1A6B36;border-radius:12px;padding:14px;margin-bottom:16px">
      <div style="font-size:13px;color:#3FB950;font-weight:700;margin-bottom:4px">🤖 AI 智能分析</div>
      <div style="font-size:12px;color:#484F58;line-height:1.5">上傳1-3張期權鏈截圖，AI讀取數字，程式精算損益</div></div>''',unsafe_allow_html=True)
    st.session_state["scan_tkr"]=st.text_input("股票代號",placeholder="DKNG / ORCL",key="stk").upper()
    scan_exp=st.text_input("到期日（選填）",placeholder="2026-08-21",key="exp2")
    scan_info=get_info(st.session_state["scan_tkr"])if st.session_state.get("scan_tkr")else{}
    scan_price=scan_info.get("price")
    if st.session_state.get("scan_tkr")and scan_price:
        stock_card(scan_info,st.session_state["scan_tkr"])
    uploaded=st.file_uploader("上傳截圖（最多3張）",type=["png","jpg","jpeg","webp"],accept_multiple_files=True)
    if uploaded:
        b64s=[compress(f)for f in uploaded[:3]]
        with st.expander(f"📷 已上傳{len(uploaded[:3])}張（點擊查看）"):
            cols=st.columns(min(len(uploaded),3))
            for i,f in enumerate(uploaded[:3]):
                with cols[i]: st.image(f,use_container_width=True)
        if st.button("🤖 AI 分析",key="scan"):
            if not api_key: st.error("請先設定 API Key")
            else:
                with st.spinner("AI 讀取中..."):
                    try:
                        client=anthropic.Anthropic(api_key=api_key)
                        ph=f"現價${scan_price}。"if scan_price else"請從截圖讀取現價。"
                        if scan_exp: ph+=f"到期：{scan_exp}。"
                        prompt=f"""讀取期權鏈截圖（{st.session_state.get('scan_tkr','未知')}）。{ph}
讀每個行權價的callBid/callAsk/putBid/putAsk。只回純JSON：{{"currentPrice":29.0,"rows":[{{"strike":30,"callBid":2.36,"callAsk":2.42,"putBid":3.10,"putAsk":3.20}}]}}"""
                        parts=[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b}}for b in b64s]
                        parts.append({"type":"text","text":prompt})
                        msg=client.messages.create(model="claude-sonnet-4-6",max_tokens=2000,messages=[{"role":"user","content":parts}])
                        text=msg.content[0].text.strip()
                        m=re.search(r'\{[\s\S]*\}',text)
                        if not m: st.error("讀取失敗："+text[:200])
                        else:
                            chain=json.loads(m.group())
                            cur2=scan_price or chain.get("currentPrice",0)
                            st.session_state["scan_res"]=compute(chain.get("rows",[]),cur2,st.session_state.get("scan_tkr",""),scan_exp)
                    except Exception as e: st.error(f"失敗：{e}")

    if st.session_state.get("scan_res"):
        res=st.session_state["scan_res"]; cur2=res["cur"]; tkr=res["ticker"]
        allc=res["bull"]+res["bear"]+res["call"]
        if not allc: st.error("找不到有效組合")
        else:
            mr=max(x["ror"]for x in allc)
            st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:flex-end;padding:6px 0 12px;border-bottom:1px solid #30363D;margin-bottom:12px"><div><div style="font-size:20px;font-weight:900;letter-spacing:-.5px">{tkr}</div><div style="font-size:11px;color:#8B949E">現價 ${fmt(cur2)}</div></div><div style="text-align:right"><div style="font-size:10px;color:#8B949E;font-weight:700">最高報酬率</div><div style="font-size:18px;font-weight:800;color:#3FB950">{mr:.0f}%</div></div></div>',unsafe_allow_html=True)
            top3=res.get("top3",[])
            if top3:
                st.markdown('<div style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:8px">整體最佳 Top 3</div>',unsafe_allow_html=True)
                for t3 in top3:
                    typ=t3["type"]; medal=t3.get("_medal","")
                    mt={"🥇":"金牌","🥈":"銀牌","🥉":"銅牌"}.get(medal,"")
                    tn={"bull":"看漲價差","bear":"看跌價差","call":"單買Call"}.get(typ,"")
                    sk2=f"${fmt(t3.get('buyStrike',0))} / ${fmt(t3.get('sellStrike',0))}"if typ in("bull","bear")else f"${fmt(t3.get('strike',0))} Call"
                    with st.expander(f"{mt}｜{tn} {sk2}｜{t3['ror']:.0f}%",expanded=(medal=="🥇")):
                        st.markdown(f'<div style="font-size:22px;text-align:center;margin-bottom:4px">{medal}</div>',unsafe_allow_html=True)
                        render_combo(t3,cur2,typ,f"stop_{medal}")
            def sg(items,label):
                if not items: return
                st.markdown(f'<div style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">{label}</div>',unsafe_allow_html=True)
                for idx,it in enumerate(items):
                    tn={"bull":"看漲價差","bear":"看跌價差","call":"單買Call"}.get(it["type"],"")
                    sk2=f"${fmt(it.get('buyStrike',0))} / ${fmt(it.get('sellStrike',0))}"if it["type"]in("bull","bear")else f"${fmt(it.get('strike',0))} Call"
                    with st.expander(f"{tn} {sk2} · 平衡${fmt(it.get('breakeven',0))} · {it['ror']:.0f}%"):
                        render_combo(it,cur2,it["type"],f"s_{it['type']}_{idx}")
            sg(res["bull"],"📈 看漲價差 Bull Call — Top 3")
            sg(res["bear"],"📉 看跌價差 Bear Put — Top 3")
            sg(res["call"],"📞 單買 Call — Top 2")
    st.markdown('</div>',unsafe_allow_html=True)

# ══════ TAB 3 ══════
with tab3:
    favs=load_favs()
    if not favs:
        st.markdown('<div style="background:#161B22;border-radius:12px;padding:28px;text-align:center;color:#8B949E;font-size:13px;margin:0 16px">尚無收藏<br><span style="font-size:11px">計算後點 ⭐ 收藏</span></div>',unsafe_allow_html=True)
    else:
        groups={}
        for f in favs: groups.setdefault(f.get("ticker","未命名"),[]).append(f)
        for tk,items in groups.items():
            st.markdown(f'<div style="font-size:15px;font-weight:800;margin:14px 16px 8px">📌 {tk} <span style="font-size:11px;color:#8B949E;font-weight:400">{len(items)}個</span></div>',unsafe_allow_html=True)
            for f in items:
                typ=f.get("sk",""); tn={"bull":"看漲價差","bear":"看跌價差","call":"單買Call","put":"單買Put"}.get(typ,"")
                bK=f.get("bK",0); sK=f.get("sK",0)
                sk2=f"${bK}/${sK}"if sK else f"${bK} {typ.upper()}"
                with st.expander(f"{tn} {sk2}"):
                    if f.get("maxProfit")is not None:
                        show_result(typ,bK,f.get("bP",0),sK,f.get("sP",0),f.get("maxProfit"),f.get("maxLoss",0),f.get("breakeven"),f.get("currentPrice",0))
                    if st.button("🗑 移除",key=f"del_{f.get('_id','')}"):
                        save_favs([x for x in load_favs()if x.get("_id")!=f.get("_id")]); st.rerun()

# ══════ TAB 4 ══════
with tab4:
    st.markdown('''<div style="padding:0 16px;color:#E6EDF3">
    <div style="background:#161B22;border-radius:12px;padding:14px;margin-bottom:12px">
      <div style="font-size:11px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">策略說明</div>
      <div style="font-size:13px;color:#8B949E;line-height:1.6"><b style="color:#E6EDF3">看漲價差</b> — 買低Call賣高Call，限定獲利和風險<br><br><b style="color:#E6EDF3">看跌價差</b> — 買高Put賣低Put，限定獲利和風險<br><br><b style="color:#E6EDF3">單買Call/Put</b> — 無限獲利潛力，最多虧損全部權利金</div></div>
    <div style="background:#161B22;border-radius:12px;padding:14px">
      <div style="font-size:11px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">使用說明</div>
      <div style="font-size:13px;color:#8B949E;line-height:1.6">1. 點上方快捷或輸入股票代號<br>2. 選到期日<br>3. 選策略<br>4. 選行權價<br>5. 按計算損益</div></div>
    </div>''',unsafe_allow_html=True)
