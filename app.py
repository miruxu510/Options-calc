import streamlit as st
import streamlit.components.v1 as components
import anthropic, base64, json, math, re, io, urllib.request
from PIL import Image

try:
    import yfinance as yf; HAS_YF=True
except: HAS_YF=False
try:
    from streamlit_local_storage import LocalStorage; HAS_LS=True
except: HAS_LS=False

st.set_page_config(page_title="Options Pro",page_icon="📈",layout="centered",initial_sidebar_state="collapsed")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
*{font-family:Inter,-apple-system,sans-serif!important;box-sizing:border-box}
.stApp{background:#0D1117;color:#E6EDF3}.stApp>div{padding-top:0!important}.block-container{padding-top:0!important}[data-testid="stAppViewContainer"]>section{padding-top:0!important}
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
""",unsafe_allow_html=True)

POLY_KEY=st.secrets.get("POLYGON_API_KEY","")
API_KEY=st.secrets.get("ANTHROPIC_API_KEY","")

def s(v,d=2):
    try: return f"{float(v):.{d}f}"
    except: return "—"
def sm(v):
    try:
        f=float(v); return f"{f:.0f}" if f==int(f) else f"{f:.2f}"
    except: return "—"
def compress(uf):
    img=Image.open(uf)
    if img.width>1200: img=img.resize((1200,int(img.height*1200/img.width)),Image.LANCZOS)
    if img.mode!="RGB": img=img.convert("RGB")
    buf=io.BytesIO(); img.save(buf,format="JPEG",quality=75); buf.seek(0)
    return base64.b64encode(buf.read()).decode()
def hd(tag,style,content):
    return f'<{tag} style="{style}">{content}</{tag}>'
def div(style,content):
    return hd("div",style,content)
def span(style,content):
    return hd("span",style,content)

@st.cache_data(ttl=60)
def get_info(sym):
    if not sym: return {}
    out={}
    if POLY_KEY:
        try:
            req=urllib.request.Request(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{sym}?apiKey={POLY_KEY}",headers={"User-Agent":"Mozilla/5.0"})
            d=json.loads(urllib.request.urlopen(req,timeout=8).read())
            t=d.get("ticker",{}); day=t.get("day",{}); prev=t.get("prevDay",{})
            price=t.get("lastTrade",{}).get("p") or day.get("c")
            prev_c=prev.get("c")
            if price:
                out["price"]=round(float(price),2)
                if prev_c and float(prev_c)>0:
                    out["change"]=round(float(price)-float(prev_c),2)
                    out["pct"]=round((float(price)-float(prev_c))/float(prev_c)*100,2)
        except: pass
    if HAS_YF:
        try:
            t=yf.Ticker(sym)
            if not out.get("price"):
                try:
                    fi=t.fast_info
                    p=fi.get("lastPrice") or fi.get("last_price")
                    if p:
                        out["price"]=round(float(p),2)
                        prev=fi.get("previousClose") or fi.get("previous_close")
                        if prev and float(prev)>0:
                            out["change"]=round(float(p)-float(prev),2)
                            out["pct"]=round((float(p)-float(prev))/float(prev)*100,2)
                except: pass
            try:
                info=t.info
                out["name"]=info.get("longName") or info.get("shortName") or sym
                out["sector"]=info.get("sector","")
                out["exchange"]=info.get("exchange","")
                tp=info.get("targetMeanPrice")
                if tp: out["target"]=round(float(tp),2)
                lo=info.get("fiftyTwoWeekLow"); hi=info.get("fiftyTwoWeekHigh")
                if lo: out["lo52"]=float(lo)
                if hi: out["hi52"]=float(hi)
            except: pass
            try:
                cal=t.calendar
                if isinstance(cal,dict):
                    ed=cal.get("Earnings Date")
                    if ed: out["nextER"]=str(ed[0] if isinstance(ed,list) else ed)[:10]
            except: pass
        except: pass
    return out

@st.cache_data(ttl=120)
def get_expiries(sym):
    if not HAS_YF or not sym: return []
    try: return list(yf.Ticker(sym).options)
    except: return []

@st.cache_data(ttl=60)
def get_chain(sym,exp):
    if not sym or not exp: return [],[]
    calls,puts=[],[]
    if POLY_KEY:
        try:
            for ct,store in [("call",calls),("put",puts)]:
                req=urllib.request.Request(f"https://api.polygon.io/v3/snapshot/options/{sym}?expiration_date={exp}&contract_type={ct}&limit=100&apiKey={POLY_KEY}",headers={"User-Agent":"Mozilla/5.0"})
                d=json.loads(urllib.request.urlopen(req,timeout=8).read())
                for r in d.get("results",[]):
                    k=r.get("details",{}).get("strike_price",0)
                    q=r.get("last_quote",{}); day=r.get("day",{})
                    bid=float(q.get("bid",0) or 0); ask=float(q.get("ask",0) or 0)
                    last=float(day.get("close",0) or 0)
                    if bid==0 and ask==0 and last>0: bid=round(last*0.95,2); ask=round(last*1.05,2)
                    if k>0 and (bid>0 or ask>0): store.append({"k":round(float(k),1),"bid":round(bid,2),"ask":round(ask,2)})
            if calls or puts:
                calls.sort(key=lambda r:r["k"]); puts.sort(key=lambda r:r["k"])
                return calls,puts
        except: pass
    if HAS_YF:
        try:
            opt=yf.Ticker(sym).option_chain(exp)
            def pr(df):
                rows=[]
                for r in df.to_dict("records"):
                    k=float(r.get("strike",0)); bid=float(r.get("bid",0) or 0)
                    ask=float(r.get("ask",0) or 0); last=float(r.get("lastPrice",0) or 0)
                    if bid==0 and ask==0 and last>0: bid=round(last*0.95,2); ask=round(last*1.05,2)
                    if k>0 and (bid>0 or ask>0): rows.append({"k":k,"bid":round(bid,2),"ask":round(ask,2)})
                return rows
            cc=[c for c in ["strike","bid","ask","lastPrice"] if c in opt.calls.columns]
            pc=[c for c in ["strike","bid","ask","lastPrice"] if c in opt.puts.columns]
            calls=pr(opt.calls[cc].dropna(subset=["strike"]))
            puts=pr(opt.puts[pc].dropna(subset=["strike"]))
            calls.sort(key=lambda r:r["k"]); puts.sort(key=lambda r:r["k"])
            return calls,puts
        except: pass
    return [],[]

def calc_pnl(sk,bK,bP,sK,sP,price):
    if sk=="bull":
        nc=bP-sP
        if price<=bK: return round(-nc*100,2)
        if price>=sK: return round((sK-bK-nc)*100,2)
        return round((price-bK-nc)*100,2)
    if sk=="bear":
        nc=bP-sP
        if price>=bK: return round(-nc*100,2)
        if price<=sK: return round((bK-sK-nc)*100,2)
        return round((bK-price-nc)*100,2)
    if sk=="call": return round((max(price-bK,0)-bP)*100,2)
    if sk=="put":  return round((max(bK-price,0)-bP)*100,2)
    return 0

def make_svg_py(sk,bK,bP,sK,sP,cur):
    unlimited=sk in("call","put"); pr=sk in("bull","call")
    lo2=min(bK,sK or bK,cur)*0.75; hi2=max(bK,sK or bK,cur)*1.35
    prev=calc_pnl(sk,bK,bP,sK,sP,lo2); be=None
    for i in range(1,601):
        p=lo2+(hi2-lo2)*i/600; c=calc_pnl(sk,bK,bP,sK,sP,p)
        if(prev<=0 and c>0)or(prev>=0 and c<0):
            f=abs(prev)/(abs(prev)+abs(c)); be=lo2+(hi2-lo2)*(i-1+f)/600; break
        prev=c
    allk=[bK,cur]+([sK]if sK else[])+([be]if be else[])
    center=be or cur; span=max(max(allk)-min(allk),cur*0.20)*1.6
    lo_ratio=0.65 if (unlimited and sk=="put") else 0.55
    hi_ratio=0.45 if (unlimited and sk=="put") else 0.55
    lo=center-span*lo_ratio; hi=center+span*hi_ratio
    pts=[lo+(hi-lo)*i/200 for i in range(201)]
    pnls=[calc_pnl(sk,bK,bP,sK,sP,p) for p in pts]
    maxV=max(pnls); minV=min(pnls)
    W,H,pX,pTop,pBot,lH=380,230,14,26,10,34
    pH=H-pTop-pBot-lH; vpad=(maxV-minV)*0.18
    vT=maxV+vpad; vR=(vT-(minV-vpad)) or 1
    cx=lambda p:pX+((p-lo)/(hi-lo))*(W-2*pX)
    cy=lambda v:pTop+(vT-v)/vR*pH
    zY=cy(0)
    ld=" ".join(("M" if i==0 else "L")+f"{cx(pts[i]):.1f},{cy(pnls[i]):.1f}" for i in range(len(pts)))
    fd=f"{ld} L{cx(hi):.1f},{zY:.1f} L{cx(lo):.1f},{zY:.1f} Z"
    tks="".join(f'<line x1="{cx(lo+(hi-lo)*i/5):.1f}" y1="{zY:.1f}" x2="{cx(lo+(hi-lo)*i/5):.1f}" y2="{zY+4:.1f}" stroke="#444" stroke-width=".8"/><text x="{cx(lo+(hi-lo)*i/5):.1f}" y="{zY+13:.1f}" fill="#444" font-size="7.5" text-anchor="middle">${lo+(hi-lo)*i/5:.0f}</text>' for i in range(6))
    cl=(f'<line x1="{cx(cur):.1f}" y1="{pTop}" x2="{cx(cur):.1f}" y2="{H-pBot-lH}" stroke="#1F6FEB" stroke-width="1" stroke-dasharray="4 3" opacity=".5"/>'
        f'<text x="{cx(cur):.1f}" y="{pTop-4}" fill="#1F6FEB" font-size="9" text-anchor="middle" font-weight="600">現價 ${cur:.2f}</text>') if lo<cur<hi else ""
    ds=""
    for dk,buy in [(bK,True)]+([( sK,False)]if sK else[]):
        if not(lo<dk<hi): continue
        dy=cy(calc_pnl(sk,bK,bP,sK,sP,dk)); sx=cx(dk); mc="#60A5FA" if buy else "#FB923C"
        lbl=("買入" if buy else "賣出")+f" ${dk:.0f}"; by2=dy-30 if buy else dy+14
        ds+=(f'<rect x="{sx-34:.1f}" y="{by2:.1f}" width="68" height="14" rx="3" fill="#0A0A0A" opacity=".92"/>'
             f'<text x="{sx:.1f}" y="{by2+11:.1f}" fill="{mc}" font-size="9" text-anchor="middle" font-weight="700">{lbl}</text>'
             f'<circle cx="{sx:.1f}" cy="{dy:.1f}" r="5" fill="{mc}"/><circle cx="{sx:.1f}" cy="{dy:.1f}" r="9" fill="{mc}" opacity=".18"/>')
    be_s=""
    if be and lo<be<hi:
        bx=cx(be)
        be_s=(f'<rect x="{bx-36:.1f}" y="{zY-32:.1f}" width="72" height="24" rx="4" fill="#0A0A0A" opacity=".92"/>'
              f'<text x="{bx:.1f}" y="{zY-20:.1f}" fill="#F0B429" font-size="8" text-anchor="middle" font-weight="600">損益平衡</text>'
              f'<text x="{bx:.1f}" y="{zY-9:.1f}" fill="#F0B429" font-size="10" text-anchor="middle" font-weight="800">${be:.2f}</text>'
              f'<circle cx="{bx:.1f}" cy="{zY:.1f}" r="5" fill="#F0B429"/><circle cx="{bx:.1f}" cy="{zY:.1f}" r="9" fill="#F0B429" opacity=".22"/>')
    bY=H-lH+14; bY2=H-lH+27
    pX1=W-pX-4 if pr else pX+4; pA1="end" if pr else "start"
    lX1=pX+4 if pr else W-pX-4; lA1="start" if pr else "end"
    mp="∞" if unlimited else f"+${maxV:.0f}"; ml=f"-${abs(minV):.0f}"
    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block;background:#0D1117;border-radius:14px;margin-top:10px">'
            f'<defs><clipPath id="cpp"><rect x="{pX}" y="{pTop}" width="{W-2*pX}" height="{max(zY-pTop,0):.1f}"/></clipPath>'
            f'<clipPath id="cpl"><rect x="{pX}" y="{zY:.1f}" width="{W-2*pX}" height="{max(pH-(zY-pTop)+pBot+4,0):.1f}"/></clipPath></defs>'
            f'<line x1="{pX}" y1="{zY:.1f}" x2="{W-pX}" y2="{zY:.1f}" stroke="#2A2A2A" stroke-width="1" stroke-dasharray="4 3"/>'
            f'{tks}{cl}'
            f'<path d="{fd}" fill="#4ADE80" opacity=".18" clip-path="url(#cpp)"/>'
            f'<path d="{fd}" fill="#F87171" opacity=".18" clip-path="url(#cpl)"/>'
            f'<path d="{ld}" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cpp)"/>'
            f'<path d="{ld}" fill="none" stroke="#F87171" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cpl)"/>'
            f'{ds}{be_s}'
            f'<text x="{pX1}" y="{bY}" fill="#4ADE80" font-size="8" font-weight="700" text-anchor="{pA1}">最大獲利</text>'
            f'<text x="{pX1}" y="{bY2}" fill="#4ADE80" font-size="12" font-weight="800" text-anchor="{pA1}">{mp}</text>'
            f'<text x="{lX1}" y="{bY}" fill="#F87171" font-size="8" font-weight="700" text-anchor="{lA1}">最大虧損</text>'
            f'<text x="{lX1}" y="{bY2}" fill="#F87171" font-size="12" font-weight="800" text-anchor="{lA1}">{ml}</text>'
            f'</svg>')

def make_ladder_py(sk,bK,bP,sK,sP,maxL,be,cur):
    if sK:
        spread=abs(bK-sK)
        step=1 if spread<5 else 1 if spread<=10 else 2.5 if spread<=20 else 5 if spread<=50 else 10
        lo=math.floor(min(bK,sK,cur)*0.88/step)*step
        hi=math.ceil( max(bK,sK,cur)*1.12/step)*step
    else:
        # Single leg: step by price level, center on BE
        step=5 if cur>500 else 2.5 if cur>200 else 2 if cur>100 else 1
        be_price=bK+bP if sk=="call" else bK-bP
        if sk=="call":
            lo=math.floor((be_price-step*3)/step)*step
            hi=math.ceil( (be_price+step*17)/step)*step
        else:
            lo=math.floor((be_price-step*17)/step)*step
            hi=math.ceil( (be_price+step*3)/step)*step
    rows=[]; p=lo
    while p<=hi+0.001:
        v=calc_pnl(sk,bK,bP,sK,sP,p); ret=v/maxL*100 if maxL else 0
        nb=be is not None and abs(p-be)<=step*0.55
        im=(sk=="bull" and sK and p>=sK)or(sk=="bear" and sK and p<=sK)
        rows.append({"p":p,"v":v,"ret":ret,"nb":nb,"im":im})
        p=round(p+step,3)
    if sK:
        if sk=="bull":
            # bull: trim low repeating floor at start, MAX+5 at end
            mi=0
            for i in range(1,len(rows)):
                if rows[i]["v"]!=rows[0]["v"]: mi=max(0,i-1); break
            mxi=len(rows)-1
            for i,r in enumerate(rows):
                if r["im"]: mxi=min(i+5,len(rows)-1); break
        else:
            # bear: MAX is at low prices (start), trim repeating MAX at start, floor at end
            first_non_max=len(rows)-1
            for i in range(len(rows)):
                if not rows[i]["im"]: first_non_max=i; break
            mi=max(0,first_non_max-5)
            mxi=len(rows)-1
            floor_val=rows[-1]["v"]
            for i in range(len(rows)-1,0,-1):
                if rows[i]["v"]!=floor_val: mxi=min(i+1,len(rows)-1); break
        rows=rows[mi:mxi+1]
    ss=sm(step)
    h=('<div style="background:#1C2128;border-radius:12px;overflow:hidden;margin-top:12px">'
       '<div style="padding:8px 12px;display:flex;justify-content:space-between;border-bottom:1px solid #30363D">'
       '<span style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px">損益對照表</span>'
       '<span style="font-size:10px;color:#484F58;background:#21262D;padding:1px 8px;border-radius:100px">每 $'+ss+'</span></div>'
       '<table style="width:100%;border-collapse:collapse">'
       '<thead><tr style="background:#21262D">'
       '<th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:left;font-weight:700;text-transform:uppercase">股價</th>'
       '<th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:right;font-weight:700;text-transform:uppercase">損益/張</th>'
       '<th style="font-size:9px;color:#484F58;padding:5px 12px;text-align:right;font-weight:700;text-transform:uppercase">報酬率</th>'
       '</tr></thead><tbody>')
    for r in rows:
        col="#4ADE80" if r["v"]>0 else "#F87171" if r["v"]<0 else "#F0B429"
        bg="rgba(74,222,128,.05)" if r["v"]>1 else "rgba(248,113,113,.05)" if r["v"]<-1 else "rgba(240,180,41,.06)"
        ps=("$"+f"{r['p']:.0f}") if r['p']%1==0 else ("$"+f"{r['p']:.2f}")
        tags=(('<span style="font-size:8px;background:#1A1000;color:#F0B429;padding:1px 5px;border-radius:100px;margin-left:4px;font-weight:700">平衡</span>' if r["nb"] else "")+
              ('<span style="font-size:8px;background:#0D2010;color:#4ADE80;padding:1px 5px;border-radius:100px;margin-left:4px;font-weight:700">MAX</span>' if r["im"] else ""))
        pstr=("+" if r["v"]>=0 else "")+"$"+f"{abs(r['v']):.0f}"
        rstr=("+" if r["ret"]>=0 else "")+f"{r['ret']:.0f}%"
        h+=(f'<tr style="background:{bg};border-bottom:1px solid #161B22">'
            f'<td style="font-size:12px;color:#E6EDF3;padding:6px 12px;font-weight:500">{ps}{tags}</td>'
            f'<td style="font-size:12px;color:{col};padding:6px 12px;text-align:right;font-weight:600">{pstr}</td>'
            f'<td style="font-size:12px;color:{col};padding:6px 12px;text-align:right;font-weight:600">{rstr}</td>'
            f'</tr>')
    h+="</tbody></table></div>"
    return h

def show_result(sk,bK,bP,sK,sP,maxP,maxL,be,cur):
    unlimited=sk in("call","put")
    mp_s="∞" if unlimited else "$"+sm(maxP)
    mp_sub="" if unlimited else "+"+f"{maxP/maxL*100:.0f}%"
    ror_s="∞" if unlimited else f"{maxP/maxL*100:.0f}%"
    be_s="$"+s(be) if be else "—"
    ml_pct=f"{maxL/(maxL+(maxP or maxL))*100:.0f}%"
    h=('<div style="background:#161B22;border:1px solid #30363D;border-radius:14px;padding:14px;margin-top:8px">'
       '<div style="font-size:14px;font-weight:700;margin-bottom:12px">損益總覽</div>'
       '<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:12px">'
       '<div style="background:#0D4429;border:1.5px solid #1A6B36;border-radius:10px;padding:10px 8px">'
       '<div style="font-size:9px;color:#86EFAC;font-weight:700;margin-bottom:3px">最大獲利</div>'
       '<div style="font-size:16px;font-weight:900;color:#4ADE80">'+mp_s+'</div>'
       '<div style="font-size:9px;color:#4ADE80;margin-top:1px">'+mp_sub+'</div></div>'
       '<div style="background:#4A1015;border:1.5px solid #8B1A1A;border-radius:10px;padding:10px 8px">'
       '<div style="font-size:9px;color:#FCA5A5;font-weight:700;margin-bottom:3px">最大虧損</div>'
       '<div style="font-size:16px;font-weight:900;color:#F87171">-$'+sm(maxL)+'</div>'
       '<div style="font-size:9px;color:#F87171;margin-top:1px">-'+ml_pct+'</div></div>'
       '<div style="background:#1C2128;border:1.5px solid #30363D;border-radius:10px;padding:10px 8px">'
       '<div style="font-size:9px;color:#8B949E;font-weight:700;margin-bottom:3px">報酬率</div>'
       '<div style="font-size:16px;font-weight:900;color:#E6EDF3">'+ror_s+'</div></div>'
       '<div style="background:#2D1F52;border:1.5px solid #6E40C9;border-radius:10px;padding:10px 8px">'
       '<div style="font-size:9px;color:#C4B5FD;font-weight:700;margin-bottom:3px">損益平衡</div>'
       '<div style="font-size:16px;font-weight:900;color:#A78BFA">'+be_s+'</div></div>'
       '</div></div>')
    st.markdown(h,unsafe_allow_html=True)
    st.markdown(make_svg_py(sk,bK,bP,sK,sP,cur),unsafe_allow_html=True)
    st.markdown(make_ladder_py(sk,bK,bP,sK,sP,maxL,be,cur),unsafe_allow_html=True)

def stock_card(info,ticker):
    p=float(info.get("price") or 0); chg=float(info.get("change") or 0); pct=float(info.get("pct") or 0)
    name=str(info.get("name") or ticker); tgt=info.get("target")
    lo52=info.get("lo52"); hi52=info.get("hi52"); nextER=str(info.get("nextER") or "—")
    exch=str(info.get("exchange") or ""); sec=str(info.get("sector") or "")
    cc="#F85149" if chg<0 else "#3FB950"
    up=round((float(tgt)-p)/p*100,1) if tgt and p else None
    uc="#3FB950" if up is not None and up>=0 else "#F85149"
    lo52f=float(lo52) if lo52 else None; hi52f=float(hi52) if hi52 else None
    bar=max(0,min(100,round((p-lo52f)/(hi52f-lo52f)*100))) if lo52f and hi52f and hi52f>lo52f else 50
    badges="".join('<span style="font-size:10px;background:#21262D;color:#8B949E;padding:2px 6px;border-radius:4px;margin-right:4px">'+str(x)+'</span>' for x in[exch,sec] if x and str(x).strip())
    tgt_cell=""
    if tgt:
        up_str=("+" if up and up>=0 else "")+(f"{up:.1f}%" if up is not None else "")
        tgt_cell=('<div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center">'
                  '<span style="font-size:10px;color:#8B949E;font-weight:600">分析師目標</span>'
                  '<div><span style="font-size:11px;font-weight:700">$'+f"{float(tgt):.2f}"+'</span>'
                  '<span style="font-size:10px;color:'+uc+';margin-left:4px;font-weight:600">'+up_str+'</span></div></div>')
    rng_cell=""
    if lo52f and hi52f:
        rng_cell=('<div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center">'
                  '<span style="font-size:10px;color:#8B949E;font-weight:600">52週區間</span>'
                  '<div style="text-align:right"><span style="font-size:11px;font-weight:700">'+f"{lo52f:.0f}"+'–'+f"{hi52f:.0f}"+'</span>'
                  '<div style="background:#21262D;border-radius:100px;height:3px;margin-top:3px;width:56px;position:relative;margin-left:auto">'
                  '<div style="position:absolute;left:'+str(bar)+'%;top:-2px;width:7px;height:7px;background:#1F6FEB;border-radius:50%;transform:translateX(-50%)"></div>'
                  '</div></div></div>')
    er_cell=('<div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center">'
             '<span style="font-size:10px;color:#8B949E;font-weight:600">下一財報</span>'
             '<span style="font-size:11px;font-weight:700;color:#F79000">'+nextER+'</span></div>')
    live_cell=('<div style="background:#1C2128;border-radius:9px;padding:7px 10px;display:flex;justify-content:space-between;align-items:center">'
               '<span style="font-size:10px;color:#8B949E;font-weight:600">即時連線</span>'
               '<span style="font-size:11px;font-weight:700;color:#3FB950">● 已連線</span></div>')
    h=('<div style="background:#161B22;border:1px solid #30363D;border-radius:14px;padding:14px;margin-bottom:12px">'
       '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">'
       '<div style="display:flex;gap:10px;align-items:center">'
       '<div style="width:40px;height:40px;background:#1F6FEB;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;color:#fff;flex-shrink:0">'+ticker+'</div>'
       '<div><div style="font-size:13px;font-weight:700">'+name+'</div>'
       '<div style="display:flex;gap:5px;margin-top:3px;flex-wrap:wrap">'+badges+'</div></div></div>'
       '<div style="text-align:right;flex-shrink:0">'
       '<div style="font-size:22px;font-weight:900;letter-spacing:-.5px">$'+f"{p:.2f}"+'</div>'
       '<div style="font-size:12px;color:'+cc+';font-weight:600">'+f"{chg:+.2f}"+'('+f"{pct:+.2f}"+'%)</div>'
       '</div></div>'
       '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">'
       +tgt_cell+rng_cell+er_cell+live_cell+
       '</div></div>')
    st.markdown(h,unsafe_allow_html=True)

if HAS_LS:
    try: ls=LocalStorage()
    except: ls=None
else: ls=None

def load_favs():
    if ls:
        try: raw=ls.getItem("opt_favs"); return json.loads(raw) if raw else []
        except: return []
    return st.session_state.get("_favs",[])
def save_favs(favs):
    if ls:
        try: ls.setItem("opt_favs",json.dumps(favs))
        except: pass
    st.session_state["_favs"]=favs
def add_fav(combo):
    favs=load_favs(); combo["_id"]=f"{combo.get('ticker','')}_{len(favs)}"; favs.insert(0,combo); save_favs(favs)

def compute(rows,cur,ticker,expiry):
    valid=sorted([r for r in rows if r.get("strike") is not None],key=lambda r:r["strike"])
    bulls,bears,calls_l=[],[],[]
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
                        sc=(1/(1+pg*5))*100*.5+min(ror,300)/3*.3+(1/(1+maxL/200))*100*.2
                        bulls.append({"type":"bull","buyStrike":lo["strike"],"buyPremium":round(ba,2),"sellStrike":hi["strike"],"sellPremium":round(sb,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_s":sc})
            ba=hi.get("putAsk"); sb=lo.get("putBid")
            if ba and sb and ba>0:
                nc=ba-sb
                if nc>0:
                    sp=hi["strike"]-lo["strike"]; maxP=(sp-nc)*100; maxL=nc*100
                    if maxP>0 and maxP/maxL>=1 and cur and(cur-hi["strike"])/cur<=.10:
                        be=hi["strike"]-nc; ror=maxP/maxL*100; pg=max((cur-be)/cur,0)
                        sc=(1/(1+pg*5))*100*.5+min(ror,300)/3*.3+(1/(1+maxL/200))*100*.2
                        bears.append({"type":"bear","buyStrike":hi["strike"],"buyPremium":round(ba,2),"sellStrike":lo["strike"],"sellPremium":round(sb,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_s":sc})
    for r in valid:
        ba=r.get("callAsk")
        if ba and ba>0 and cur and abs(r["strike"]-cur)/cur<=.12:
            be=r["strike"]+ba; maxP=(cur*1.2-r["strike"]-ba)*100; maxL=ba*100
            if maxP>0:
                ror=maxP/maxL*100; pg=max((be-cur)/cur,0)
                sc=(1/(1+pg*4))*100*.6+min(ror,200)/2*.2+(1/(1+maxL/300))*100*.2
                calls_l.append({"type":"call","strike":r["strike"],"premium":round(ba,2),"maxProfit":round(maxP),"maxLoss":round(maxL),"breakeven":round(be,2),"ror":round(ror),"rr":round(maxP/maxL,2),"_s":sc})
    bulls.sort(key=lambda x:-x["_s"]); bears.sort(key=lambda x:-x["_s"]); calls_l.sort(key=lambda x:-x["_s"])
    B,R,L=bulls[:3],bears[:3],calls_l[:2]
    def asgn(items):
        for it in items:
            it["stars"]=5 if it["_s"]>=90 else 4 if it["_s"]>=70 else 3 if it["_s"]>=50 else 2
            pros,cons=[],[]
            bd=abs(it["breakeven"]-cur)/cur*100 if cur else 0
            if it["rr"]>=2: pros.append("盈虧比佳")
            if it["maxLoss"]<=150: pros.append("成本低")
            if bd<=5: pros.append("接近現價")
            if it["rr"]<1.5: cons.append("盈虧比偏低")
            if it["maxLoss"]>300: cons.append("成本較高")
            if bd>8: cons.append(f"需變動{bd:.0f}%")
            it["pros"]="、".join(pros) or "風險可控"; it["cons"]="、".join(cons) or "注意時間價值"
    asgn(B); asgn(R); asgn(L)
    everything=sorted(B+R+L,key=lambda x:-x["_s"])
    for i,t in enumerate(everything[:3]): t["_medal"]=["🥇","🥈","🥉"][i]
    return{"cur":cur,"ticker":ticker,"expiry":expiry,"bull":B,"bear":R,"call":L,"top3":everything[:3]}

def render_combo(it,cur,typ,key=None):
    unlimited=typ in("call","put")
    mp=it.get("maxProfit",0); ml=it.get("maxLoss",0); be=it.get("breakeven",0); ror=it.get("ror",0)
    mp_s="∞" if unlimited else "$"+sm(mp); ror_s="∞" if unlimited else f"{ror:.0f}%"
    h=('<div style="display:flex;gap:6px;margin:8px 0">'
       '<div style="flex:1;background:#0D4429;border:1.5px solid #1A6B36;border-radius:10px;padding:10px 8px;text-align:center">'
       '<div style="font-size:9px;color:#86EFAC;font-weight:700;margin-bottom:3px">最大獲利</div>'
       '<div style="font-size:15px;font-weight:900;color:#4ADE80">'+mp_s+'</div></div>'
       '<div style="flex:1;background:#4A1015;border:1.5px solid #8B1A1A;border-radius:10px;padding:10px 8px;text-align:center">'
       '<div style="font-size:9px;color:#FCA5A5;font-weight:700;margin-bottom:3px">最大虧損</div>'
       '<div style="font-size:15px;font-weight:900;color:#F87171">-$'+sm(ml)+'</div></div>'
       '<div style="flex:1;background:#1C2128;border:1.5px solid #30363D;border-radius:10px;padding:10px 8px;text-align:center">'
       '<div style="font-size:9px;color:#8B949E;font-weight:700;margin-bottom:3px">報酬率</div>'
       '<div style="font-size:15px;font-weight:900;color:#E6EDF3">'+ror_s+'</div></div>'
       '<div style="flex:1;background:#2D1F52;border:1.5px solid #6E40C9;border-radius:10px;padding:10px 8px;text-align:center">'
       '<div style="font-size:9px;color:#C4B5FD;font-weight:700;margin-bottom:3px">損益平衡</div>'
       '<div style="font-size:15px;font-weight:900;color:#A78BFA">$'+s(be)+'</div></div>'
       '</div>')
    st.markdown(h,unsafe_allow_html=True)
    if it.get("pros") or it.get("cons"):
        ph=('<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0">'
            '<div style="background:#0D4429;border:1px solid #1A6B36;border-radius:9px;padding:8px 10px">'
            '<div style="font-size:9px;color:#3FB950;font-weight:700;margin-bottom:2px">✓ 優點</div>'
            '<div style="font-size:11px;color:#8B949E">'+it.get("pros","")+'</div></div>'
            '<div style="background:#4A1015;border:1px solid #8B1A1A;border-radius:9px;padding:8px 10px">'
            '<div style="font-size:9px;color:#F85149;font-weight:700;margin-bottom:2px">✗ 缺點</div>'
            '<div style="font-size:11px;color:#8B949E">'+it.get("cons","")+'</div></div>'
            '</div>')
        st.markdown(ph,unsafe_allow_html=True)
    legs={}
    if typ=="bull": legs={"bK":it["buyStrike"],"bP":it["buyPremium"],"sK":it["sellStrike"],"sP":it["sellPremium"]}
    elif typ=="bear": legs={"bK":it["buyStrike"],"bP":it["buyPremium"],"sK":it["sellStrike"],"sP":it["sellPremium"]}
    elif typ=="call": legs={"bK":it["strike"],"bP":it["premium"],"sK":0,"sP":0}
    if legs: st.markdown(make_svg_py(typ,legs["bK"],legs["bP"],legs.get("sK",0),legs.get("sP",0),cur),unsafe_allow_html=True)
    if key and st.button("⭐ 收藏",key=key):
        add_fav({**it,"ticker":st.session_state.get("scan_tkr",""),"sk":typ}); st.success("已收藏！")

st.markdown('<div style="background:#161B22;padding:12px 16px 10px;border-bottom:1px solid #30363D;display:flex;align-items:center;gap:10px"><div style="width:28px;height:28px;background:#1F6FEB;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:#fff;flex-shrink:0">F</div><div><div style="font-size:9px;color:#8B949E;font-weight:600;letter-spacing:1px">OPTIONS</div><div style="font-size:16px;font-weight:800;letter-spacing:-.5px">Strategy Pro</div></div></div>',unsafe_allow_html=True)

tab1,tab2,tab3,tab4=st.tabs(["選股計算","AI 掃描","我的組合","說明"])

with tab1:
    WL=["MU","NVDA","ORCL","DKNG","AAPL","TSLA","AMZN","MSFT","IBIT","SRAD","FLUT","META"]
    cs="display:inline-block;background:#1C2128;border:1px solid #30363D;border-radius:100px;padding:5px 12px;color:#8B949E;font-size:12px;font-weight:700;margin:2px;text-decoration:none;white-space:nowrap"
    chips="".join(f'<a href="?t={t}" style="{cs}">{t}</a>' for t in WL)
    st.markdown('<div style="overflow-x:auto;white-space:nowrap;padding:12px 16px 8px">'+chips+'</div>',unsafe_allow_html=True)

    qp=st.query_params; default_t=qp.get("t","").upper()
    c1,c2=st.columns([2,1])
    ticker=c1.text_input("股票代號",placeholder="MU / ORCL / DKNG",key="tk",value=default_t).upper().strip()
    expiries=get_expiries(ticker) if ticker else []
    expiry=c2.selectbox("到期日",expiries if expiries else["—"],key="exp") if expiries else None

    info={}; calls_d=[]; puts_d=[]
    if ticker:
        with st.spinner("載入中..."): info=get_info(ticker)
        if info.get("price"):
            stock_card(info,ticker)
            if expiry and expiry!="—":
                with st.spinner("載入期權鏈..."): calls_d,puts_d=get_chain(ticker,expiry)
        elif ticker: st.error(f"找不到 {ticker}")

    if (calls_d or puts_d) and info.get("price",0)>0:
        cur=float(info["price"])
        # Show all strikes with valid prices (no range filter)
        calls_f=sorted([r for r in calls_d if r["bid"]>0 or r["ask"]>0],key=lambda r:r["k"])
        puts_f=sorted([r for r in puts_d  if r["bid"]>0 or r["ask"]>0],key=lambda r:r["k"])
        if not calls_f: calls_f=sorted(calls_d,key=lambda r:r["k"])
        if not puts_f:  puts_f=sorted(puts_d, key=lambda r:r["k"])

        data_js=json.dumps({"cur":cur,"calls":calls_f,"puts":puts_f})

        # Build component HTML as a single string with placeholder
        chtml=('<style>'
'*{box-sizing:border-box;margin:0;padding:0;font-family:Inter,-apple-system,sans-serif}'
'body{background:transparent;color:#E6EDF3;padding:0 16px 20px}'
'select{-webkit-appearance:none;appearance:none;background:#1C2128;border:1px solid #30363D;border-radius:10px;color:#E6EDF3;font-size:14px;font-weight:700;width:100%;padding:10px 14px;cursor:pointer}'
'.sr{background:#1C2128;border:1px solid #30363D;border-radius:12px;padding:12px 14px;margin-bottom:10px;display:flex;align-items:center;gap:10px}'
'.sr select{flex:1;border:none;background:transparent;font-size:14px;padding:0}'
'.tb{background:#0C2D6B;border:1px solid #1F6FEB;border-radius:8px;padding:6px 12px;color:#1F6FEB;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;flex-shrink:0}'
'.tbox{background:#0C2D6B;border:1px solid #1F6FEB;border-radius:10px;padding:10px 14px;margin-bottom:10px;font-size:12px;color:#8B949E;line-height:1.6;display:none}'
'.legs{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}'
'.leg{border-radius:14px;padding:12px}'
'.buy{background:#0C2D6B;border:1.5px solid #1F6FEB}'
'.sell{background:#0D4429;border:1.5px solid #1A6B36}'
'.sput{background:#3D2400;border:1.5px solid #F79000}'
'.ltitle{font-size:11px;font-weight:700;margin-bottom:8px}'
'.buy .ltitle{color:#1F6FEB}.sell .ltitle{color:#3FB950}.sput .ltitle{color:#F79000}'
'.llbl{font-size:10px;color:#8B949E;margin-bottom:4px}'
'.plbl{font-size:10px;color:#8B949E;margin-top:6px;margin-bottom:2px}'
'.pval{font-size:22px;font-weight:900;color:#E6EDF3}'
'.ph{font-size:13px;color:#484F58;margin:6px 0}'
'.qrow{display:flex;align-items:center;justify-content:space-between;margin-top:10px}'
'.ql{font-size:10px;color:#8B949E}'
'.qc{display:flex;align-items:center;gap:8px}'
'.qb{width:28px;height:28px;background:#21262D;border:1px solid #30363D;border-radius:7px;color:#E6EDF3;font-size:16px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}'
'.qv{font-size:14px;font-weight:700;min-width:20px;text-align:center}'
'.qu{font-size:12px;color:#8B949E}'
'.sw{width:100%;background:#1C2128;border:1px solid #30363D;border-radius:10px;padding:9px 0;color:#8B949E;font-size:13px;cursor:pointer;margin-bottom:10px}'
'.cb{width:100%;background:linear-gradient(135deg,#1F6FEB,#0C54C7);border:none;border-radius:14px;padding:17px 0;color:#fff;font-size:16px;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:14px}'
'.mt{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:12px}'
'.mc{border-radius:10px;padding:10px 8px}'
'.mg{background:#0D4429;border:1.5px solid #1A6B36}.mr{background:#4A1015;border:1.5px solid #8B1A1A}'
'.mgr{background:#1C2128;border:1.5px solid #30363D}.mp{background:#2D1F52;border:1.5px solid #6E40C9}'
'.ml{font-size:9px;font-weight:700;margin-bottom:3px;letter-spacing:.5px}'
'.mg .ml{color:#86EFAC}.mr .ml{color:#FCA5A5}.mgr .ml{color:#8B949E}.mp .ml{color:#C4B5FD}'
'.mv{font-size:15px;font-weight:900;letter-spacing:-.5px}'
'.mg .mv{color:#4ADE80}.mr .mv{color:#F87171}.mgr .mv{color:#E6EDF3}.mp .mv{color:#A78BFA}'
'.ms{font-size:9px;font-weight:600;margin-top:1px}'
'.mg .ms{color:#4ADE80}.mr .ms{color:#F87171}'
'.rb{background:#161B22;border:1px solid #30363D;border-radius:14px;padding:14px}'
'.rt{font-size:14px;font-weight:700;margin-bottom:12px}'
'.ld{background:#1C2128;border-radius:12px;overflow:hidden;margin-top:12px}'
'.lh{padding:8px 12px;display:flex;justify-content:space-between;border-bottom:1px solid #30363D}'
'.lhl{font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px}'
'.lhr{font-size:10px;color:#484F58;background:#21262D;padding:1px 8px;border-radius:100px}'
'.lc{display:grid;grid-template-columns:1fr 1fr 1fr;background:#21262D;padding:5px 12px;border-bottom:1px solid #30363D}'
'.lch{font-size:9px;color:#484F58;font-weight:700;text-transform:uppercase;letter-spacing:.5px}'
'.lch:not(:first-child){text-align:right}'
'.lrw{display:grid;grid-template-columns:1fr 1fr 1fr;padding:6px 12px;border-bottom:1px solid #161B22}'
'.lp{font-size:12px;color:#E6EDF3;font-weight:500;display:flex;align-items:center;gap:4px}'
'.lv,.lrt{font-size:12px;font-weight:600;text-align:right}'
'.tag{font-size:8px;padding:1px 5px;border-radius:100px;font-weight:700}'
'.tbe{background:#1A1000;color:#F0B429}.tmax{background:#0D2010;color:#4ADE80}'
'.sb{width:100%;margin-top:10px;padding:10px 0;background:transparent;border:1px solid #F0B429;border-radius:100px;color:#F0B429;font-size:13px;font-weight:700;cursor:pointer}'
'</style>'
'<div id="app"></div>'
'<script>'
'const D=__DP__;'
'const CA=D.calls,PU=D.puts,CUR=D.cur;'
'const ST={'
'bull:{l:"看漲價差 Bull Call Spread",t:"買低Call賣高Call，看漲限風險，最大獲利固定。"},'
'bear:{l:"看跌價差 Bear Put Spread",t:"買高Put賣低Put，看跌限風險，最大獲利固定。"},'
'call:{l:"單買 Call (Long Call)",t:"直接買入Call，無限獲利潛力，最多虧損全部權利金。"},'
'put:{l:"單買 Put (Long Put)",t:"直接買入Put，跌越多賺越多，最多虧損全部權利金。"}'
'};'
'let sk="bull",tip=false,res=null,bs="",ss2="",bq=1,sq=1;'
'function pnl(sk,bK,bP,sK,sP,p){'
'if(sk==="bull"){const n=bP-sP;if(p<=bK)return -n*100;if(p>=sK)return(sK-bK-n)*100;return(p-bK-n)*100;}'
'if(sk==="bear"){const n=bP-sP;if(p>=bK)return -n*100;if(p<=sK)return(bK-sK-n)*100;return(bK-p-n)*100;}'
'if(sk==="call")return(Math.max(p-bK,0)-bP)*100;'
'if(sk==="put")return(Math.max(bK-p,0)-bP)*100;'
'return 0;}'
'function be(sk,bK,bP,sK,sP){'
'const lo=Math.min(bK,sK||bK,CUR)*.75,hi=Math.max(bK,sK||bK,CUR)*1.35;'
'let pv=pnl(sk,bK,bP,sK,sP,lo);'
'for(let i=1;i<=600;i++){'
'const p=lo+(hi-lo)*i/600,c=pnl(sk,bK,bP,sK,sP,p);'
'if((pv<=0&&c>0)||(pv>=0&&c<0)){const f=Math.abs(pv)/(Math.abs(pv)+Math.abs(c));return lo+(hi-lo)*(i-1+f)/600;}'
'pv=c;}return null;}'
'function msvg(sk,bK,bP,sK,sP){'
'const ul=sk==="call"||sk==="put",pr=sk==="bull"||sk==="call";'
'const b=be(sk,bK,bP,sK,sP);'
'const ak=[bK,CUR,...(sK?[sK]:[]),...(b?[b]:[])];'
'const ct=b||CUR,sp=Math.max(Math.max(...ak)-Math.min(...ak),CUR*.20)*1.6;'
'const lo=ct-sp*(ul&&sk==="put"?.65:.55),hi=ct+sp*(ul&&sk==="put"?.45:.55);'
'const pts=Array.from({length:201},(_,i)=>lo+(hi-lo)*i/200);'
'const pnls=pts.map(p=>pnl(sk,bK,bP,sK,sP,p));'
'const mx=Math.max(...pnls),mn=Math.min(...pnls);'
'if(mx===mn)return null;'
'const W=340,H=220,pX=12,pT=24,pB=8,lH=32,pH=H-pT-pB-lH;'
'const vp=(mx-mn)*.18,vT=mx+vp,vR=(vT-(mn-vp))||1;'
'const cx=p=>pX+((p-lo)/(hi-lo))*(W-2*pX);'
'const cy=v=>pT+(vT-v)/vR*pH;'
'const zY=cy(0);'
'const ld=pts.map((p,i)=>(i?"L":"M")+cx(p).toFixed(1)+","+cy(pnls[i]).toFixed(1)).join(" ");'
'const fd=ld+" L"+cx(hi).toFixed(1)+","+zY.toFixed(1)+" L"+cx(lo).toFixed(1)+","+zY.toFixed(1)+" Z";'
'const tk=Array.from({length:6},(_,i)=>{const p=lo+(hi-lo)*i/5,tx=cx(p);return\'<line x1="\'+tx.toFixed(1)+\'" y1="\'+zY.toFixed(1)+\'" x2="\'+tx.toFixed(1)+\'" y2="\'+( zY+4).toFixed(1)+\'" stroke="#444" stroke-width=".8"/><text x="\'+tx.toFixed(1)+\'" y="\'+( zY+13).toFixed(1)+\'" fill="#444" font-size="7.5" text-anchor="middle">$\'+p.toFixed(0)+\'</text>\';}).join("");'
'const cl=lo<CUR&&CUR<hi?\'<line x1="\'+cx(CUR).toFixed(1)+\'" y1="\'+pT+\'" x2="\'+cx(CUR).toFixed(1)+\'" y2="\'+( H-pB-lH)+\'" stroke="#1F6FEB" stroke-width="1" stroke-dasharray="4 3" opacity=".5"/><text x="\'+cx(CUR).toFixed(1)+\'" y="\'+( pT-4)+\'" fill="#1F6FEB" font-size="9" text-anchor="middle" font-weight="600">現價 $\'+CUR+\'</text>\':"";'
'const ds=[[bK,true],...(sK?[[sK,false]]:[])].map(([dk,buy])=>{'
'if(dk<lo||dk>hi)return"";'
'const mc=buy?"#60A5FA":"#FB923C",dy=cy(pnl(sk,bK,bP,sK,sP,dk)),sx=cx(dk);'
'const bOffset=buy?-30:14;const b2=dy+bOffset;const lb=(buy?"買入":"賣出")+" $"+dk;'
'return\'<rect x="\'+( sx-34).toFixed(1)+\'" y="\'+b2.toFixed(1)+\'" width="68" height="14" rx="3" fill="#0A0A0A" opacity=".92"/><text x="\'+sx.toFixed(1)+\'" y="\'+( b2+11).toFixed(1)+\'" fill="\'+mc+\'" font-size="9" text-anchor="middle" font-weight="700">\'+lb+\'</text><circle cx="\'+sx.toFixed(1)+\'" cy="\'+dy.toFixed(1)+\'" r="5" fill="\'+mc+\'"/><circle cx="\'+sx.toFixed(1)+\'" cy="\'+dy.toFixed(1)+\'" r="9" fill="\'+mc+\'" opacity=".18"/>\';'
'}).join("");'
'const be2=b&&lo<b&&b<hi?\'<rect x="\'+( cx(b)-36).toFixed(1)+\'" y="\'+( zY-32).toFixed(1)+\'" width="72" height="24" rx="4" fill="#0A0A0A" opacity=".92"/><text x="\'+cx(b).toFixed(1)+\'" y="\'+( zY-20).toFixed(1)+\'" fill="#F0B429" font-size="8" text-anchor="middle" font-weight="600">損益平衡</text><text x="\'+cx(b).toFixed(1)+\'" y="\'+( zY-9).toFixed(1)+\'" fill="#F0B429" font-size="10" text-anchor="middle" font-weight="800">$\'+b.toFixed(2)+\'</text><circle cx="\'+cx(b).toFixed(1)+\'" cy="\'+zY.toFixed(1)+\'" r="5" fill="#F0B429"/><circle cx="\'+cx(b).toFixed(1)+\'" cy="\'+zY.toFixed(1)+\'" r="9" fill="#F0B429" opacity=".22"/>\':"";'
'const bY=H-lH+13,bY2=H-lH+26;'
'const pX1=pr?W-pX-4:pX+4,pA1=pr?"end":"start";'
'const lX1=pr?pX+4:W-pX-4,lA1=pr?"start":"end";'
'const mp=ul?"∞":("+$"+mx.toFixed(0)),ml="-$"+Math.abs(mn).toFixed(0);'
'const sv=document.createElementNS("http://www.w3.org/2000/svg","svg");'
'sv.setAttribute("viewBox","0 0 "+W+" "+H);'
'sv.style.cssText="width:100%;height:"+H+"px;display:block;background:#0D1117;border-radius:14px;margin-top:10px";'
'sv.innerHTML=\'<defs><clipPath id="cp1"><rect x="\'+pX+\'" y="\'+pT+\'" width="\'+( W-2*pX)+\'" height="\'+Math.max(zY-pT,0).toFixed(1)+\'"/></clipPath><clipPath id="cp2"><rect x="\'+pX+\'" y="\'+zY.toFixed(1)+\'" width="\'+( W-2*pX)+\'" height="\'+Math.max(pH-(zY-pT)+pB+4,0).toFixed(1)+\'"/></clipPath></defs><line x1="\'+pX+\'" y1="\'+zY.toFixed(1)+\'" x2="\'+( W-pX)+\'" y2="\'+zY.toFixed(1)+\'" stroke="#2A2A2A" stroke-width="1" stroke-dasharray="4 3"/>\'+tk+cl+\'<path d="\'+fd+\'" fill="#4ADE80" opacity=".18" clip-path="url(#cp1)"/><path d="\'+fd+\'" fill="#F87171" opacity=".18" clip-path="url(#cp2)"/><path d="\'+ld+\'" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cp1)"/><path d="\'+ld+\'" fill="none" stroke="#F87171" stroke-width="2.5" stroke-linejoin="round" clip-path="url(#cp2)"/>\'+ds+be2+\'<text x="\'+pX1+\'" y="\'+bY+\'" fill="#4ADE80" font-size="8" font-weight="700" text-anchor="\'+pA1+\'">最大獲利</text><text x="\'+pX1+\'" y="\'+bY2+\'" fill="#4ADE80" font-size="12" font-weight="800" text-anchor="\'+pA1+\'">\'+mp+\'</text><text x="\'+lX1+\'" y="\'+bY+\'" fill="#F87171" font-size="8" font-weight="700" text-anchor="\'+lA1+\'">最大虧損</text><text x="\'+lX1+\'" y="\'+bY2+\'" fill="#F87171" font-size="12" font-weight="800" text-anchor="\'+lA1+\'">\'+ml+\'</text>\';'
'return sv;}'
'function mld(sk,bK,bP,sK,sP,mL,be){'
'let st,lo,hi;'
'if(sK){'
'const sp=Math.abs(bK-sK);'
'st=sp<5?1:sp<=10?1:sp<=20?2.5:sp<=50?5:10;'
'lo=Math.floor(Math.min(bK,sK,CUR)*.88/st)*st;'
'hi=Math.ceil(Math.max(bK,sK,CUR)*1.12/st)*st;'
'}else{'
'st=CUR>500?5:CUR>200?2.5:CUR>100?2:1;'
'const bp=sk==="call"?bK+bP:bK-bP;'
'if(sk==="call"){lo=Math.floor((bp-st*3)/st)*st;hi=Math.ceil((bp+st*17)/st)*st;}'
'else{lo=Math.floor((bp-st*17)/st)*st;hi=Math.ceil((bp+st*3)/st)*st;}}'
'const ar=[];'
'for(let p=lo;p<=hi+.001;p=Math.round((p+st)*1000)/1000){'
'const v=pnl(sk,bK,bP,sK,sP,p),rt=mL?v/mL*100:0;'
'const nb=be!=null&&Math.abs(p-be)<=st*.55;'
'const im=(sk==="bull"&&sK&&p>=sK)||(sk==="bear"&&sK&&p<=sK);'
'ar.push({p,v,rt,nb,im});}'
'let mi=0,mxi=ar.length-1;'
'if(sK){'
'if(sk==="bull"){'
'for(let i=1;i<ar.length;i++){if(ar[i].v!==ar[0].v){mi=Math.max(0,i-1);break;}}'
'for(let i=0;i<ar.length;i++){if(ar[i].im){mxi=Math.min(i+5,ar.length-1);break;}}}'
'else{'
'let fnm=ar.length-1;for(let i=0;i<ar.length;i++){if(!ar[i].im){fnm=i;break;}}'
'mi=Math.max(0,fnm-5);'
'const fv=ar[ar.length-1].v;'
'for(let i=ar.length-1;i>0;i--){if(ar[i].v!==fv){mxi=Math.min(i+1,ar.length-1);break;}}}}'
'const rw=ar.slice(mi,mxi+1);'
'const ss=st%1===0?st.toFixed(0):st.toFixed(1);'
'const w=document.createElement("div");w.className="ld";'
'w.innerHTML=\'<div class="lh"><span class="lhl">損益對照表</span><span class="lhr">每 $\'+ss+\'</span></div><div class="lc"><span class="lch">股價</span><span class="lch">損益/張</span><span class="lch">報酬率</span></div>\';'
'rw.forEach(r=>{'
'const c=r.v>0?"#4ADE80":r.v<0?"#F87171":"#F0B429";'
'const bg=r.v>1?"rgba(74,222,128,.05)":r.v<-1?"rgba(248,113,113,.05)":"rgba(240,180,41,.06)";'
'const ps="$"+(r.p%1===0?r.p.toFixed(0):r.p.toFixed(2));'
'const tg=(r.nb?\'<span class="tag tbe">平衡</span>\':"\")+(r.im?\'<span class="tag tmax">MAX</span>\':\"\");'
'const pv=(r.v>=0?"+":" ")+r.v.toFixed(0),rv=(r.rt>=0?"+":" ")+r.rt.toFixed(0)+"%";'
'const ro=document.createElement("div");ro.className="lrw";ro.style.background=bg;'
'ro.innerHTML=\'<span class="lp">\'+ps+tg+\'</span><span class="lv" style="color:\'+c+\'">\'+pv+\'</span><span class="lrt" style="color:\'+c+\'">\'+rv+\'</span>\';'
'w.appendChild(ro);});'
'return w;}'
'function ga(){return(sk==="bear"||sk==="put")?PU:CA;}'
'function gs(){return sk==="bear"?PU:sk==="bull"?CA:[];}'
'function rnd(){'
'const iS=sk==="call"||sk==="put";'
'const bA=ga(),sA=gs();'
'const bL=sk==="bull"?"買入 Call":sk==="bear"?"買入 Put":sk==="call"?"買入 Call":"買入 Put";'
'const sL=sk==="bull"?"賣出 Call":"賣出 Put";'
'const bC=sk==="put"?"leg sput":"leg buy";'
'const ap=document.getElementById("app");ap.innerHTML="";'
'const sr=document.createElement("div");sr.className="sr";'
'const sl=document.createElement("select");sl.id="sl";'
'Object.entries(ST).forEach(([k,v])=>{const o=document.createElement("option");o.value=k;o.textContent=v.l;if(k===sk)o.selected=true;sl.appendChild(o);});'
'sl.onchange=e=>{sk=e.target.value;bs="";ss2="";res=null;rnd();};'
'const tb=document.createElement("button");tb.className="tb";tb.textContent="ⓘ 說明";'
'tb.onclick=()=>{tip=!tip;document.getElementById("tb2").style.display=tip?"block":"none";};'
'sr.appendChild(sl);sr.appendChild(tb);ap.appendChild(sr);'
'const tb2=document.createElement("div");tb2.className="tbox";tb2.id="tb2";'
'tb2.textContent=ST[sk].t;tb2.style.display=tip?"block":"none";ap.appendChild(tb2);'
'const lg=document.createElement("div");lg.className=iS?"":"legs";ap.appendChild(lg);'
'function ml2(arr,cls,ti,sid,sv,side,oc){'
'const c=document.createElement("div");c.className=cls;'
'const t=document.createElement("div");t.className="ltitle";t.textContent=ti;c.appendChild(t);'
'const lb=document.createElement("div");lb.className="llbl";lb.textContent="履約價 (Strike)";c.appendChild(lb);'
'const se=document.createElement("select");se.id=sid;'
'const o0=document.createElement("option");o0.value="";o0.textContent="點此選擇行權價";se.appendChild(o0);'
'const atm=arr.reduce((a,b)=>Math.abs(b.k-CUR)<Math.abs(a.k-CUR)?b:a,arr[0]||{k:0});'
'arr.forEach(r=>{'
'const o=document.createElement("option");o.value=r.k;'
'const ia=Math.abs(r.k-CUR)<0.01;'
'o.textContent=(ia?"▶ ":"")+"$"+r.k+"  ("+side+" $"+(side==="Ask"?r.ask.toFixed(2):r.bid.toFixed(2))+")";'
'if(r.k==sv)o.selected=true;se.appendChild(o);'
'});'
'se.onchange=oc;c.appendChild(se);'
'if(!sv&&atm.k){setTimeout(()=>{const os=Array.from(se.options);const ix=os.findIndex(o=>parseFloat(o.value)===atm.k);if(ix>0)se.selectedIndex=ix;},0);}'
'const rw=arr.find(r=>r.k==sv);'
'if(rw){const pl=document.createElement("div");pl.className="plbl";pl.textContent=side+" 權利金";c.appendChild(pl);'
'const pv=document.createElement("div");pv.className="pval";pv.textContent="$"+(side==="Ask"?rw.ask.toFixed(2):rw.bid.toFixed(2));c.appendChild(pv);}'
'else{const ph=document.createElement("div");ph.className="ph";ph.textContent="選擇後顯示權利金";c.appendChild(ph);}'
'const qr=document.createElement("div");qr.className="qrow";'
'const ql=document.createElement("div");ql.className="ql";ql.textContent="數量";'
'const qc=document.createElement("div");qc.className="qc";'
'const qm=document.createElement("button");qm.className="qb";qm.textContent="−";'
'qm.onclick=()=>{if(sid==="sb"&&bq>1)bq--;else if(sid==="ss2"&&sq>1)sq--;rnd();};'
'const qv=document.createElement("div");qv.className="qv";qv.textContent=sid==="sb"?bq:sq;'
'const qp=document.createElement("button");qp.className="qb";qp.textContent="+";'
'qp.onclick=()=>{if(sid==="sb")bq++;else sq++;rnd();};'
'const qu=document.createElement("div");qu.className="qu";qu.textContent="張";'
'qc.append(qm,qv,qp,qu);qr.append(ql,qc);c.appendChild(qr);'
'return c;}'
'lg.appendChild(ml2(bA,bC,bL,"sb",bs,"Ask",e=>{bs=e.target.value;res=null;rnd();}));'
'if(!iS){'
'lg.appendChild(ml2(sA,"leg sell",sL,"ss2",ss2,"Bid",e=>{ss2=e.target.value;res=null;rnd();}));'
'const sw=document.createElement("button");sw.className="sw";sw.textContent="⇄ 互換行權價";'
'sw.onclick=()=>{const t=bs;bs=ss2;ss2=t;res=null;rnd();};ap.appendChild(sw);}'
'const cb=document.createElement("button");cb.className="cb";'
'cb.innerHTML=\'<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><polyline points="2,14 7,8 11,11 18,4" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><polyline points="14,4 18,4 18,8" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>計 算 損 益</span>\';'
'cb.onclick=dc;ap.appendChild(cb);'
'if(res){'
'const{mP,mL,be2,bK,bP,sK,sP}=res;'
'const ul=sk==="call"||sk==="put";'
'const mPs=ul?"∞":"$"+mP.toFixed(0);'
'const mPsb=ul?"":"+"+((mP/mL)*100).toFixed(0)+"%";'
'const rs=ul?"∞":((mP/mL)*100).toFixed(0)+"%";'
'const bs2=be2!=null?"$"+be2.toFixed(2):"—";'
'const rb=document.createElement("div");rb.className="rb";'
'const rt=document.createElement("div");rt.className="rt";rt.textContent="損益總覽";rb.appendChild(rt);'
'const mt=document.createElement("div");mt.className="mt";'
'[{c:"mg",l:"最大獲利",v:mPs,sb:mPsb},{c:"mr",l:"最大虧損",v:"-$"+mL.toFixed(0),sb:"-"+((mL/(mL+(mP||mL)))*100).toFixed(0)+"%"},{c:"mgr",l:"報酬率",v:rs,sb:""},{c:"mp",l:"損益平衡",v:bs2,sb:""}].forEach(m=>{'
'const md=document.createElement("div");md.className="mc "+m.c;'
'md.innerHTML=\'<div class="ml">\'+m.l+\'</div><div class="mv">\'+m.v+\'</div>\'+(m.sb?\'<div class="ms">\'+m.sb+\'</div>\':\"\");'
'mt.appendChild(md);});'
'rb.appendChild(mt);'
'const sv=msvg(sk,bK,bP,sK,sP);if(sv)rb.appendChild(sv);'
'rb.appendChild(mld(sk,bK,bP,sK,sP,mL,be2));'
'const sb=document.createElement("button");sb.className="sb";sb.textContent="⭐ 收藏這個組合";'
'rb.appendChild(sb);ap.appendChild(rb);}}'
'function dc(){'
'const bA=ga(),sA=gs();'
'const bR=bA.find(r=>r.k==bs),sR=sA.find(r=>r.k==ss2);'
'if(!bR){alert("請選擇買入行權價");return;}'
'if((sk==="bull"||sk==="bear")&&!sR){alert("請選擇賣出行權價");return;}'
'const bK=bR.k,bP=bR.ask,sK=sR?sR.k:0,sP=sR?sR.bid:0;'
'let mP,mL,be2;'
'if(sk==="bull"){const n=bP-sP;mP=(sK-bK-n)*100;mL=n*100;be2=bK+n;}'
'else if(sk==="bear"){const n=bP-sP;mP=(bK-sK-n)*100;mL=n*100;be2=bK-n;}'
'else if(sk==="call"){mP=null;mL=bP*100;be2=bK+bP;}'
'else{mP=null;mL=bP*100;be2=bK-bP;}'
'res={mP,mL,be2,bK,bP,sK,sP};rnd();}'
'rnd();'
'</script>')

        chtml=chtml.replace("__DP__",data_js)
        components.html(chtml,height=900,scrolling=True)

with tab2:
    st.markdown('<div style="background:#0D4429;border:1px solid #1A6B36;border-radius:12px;padding:14px;margin:12px 16px"><div style="font-size:13px;color:#3FB950;font-weight:700;margin-bottom:4px">🤖 AI 智能分析</div><div style="font-size:12px;color:#484F58;line-height:1.5">上傳1-3張期權鏈截圖，AI讀取數字，程式精算損益</div></div>',unsafe_allow_html=True)
    st.session_state["scan_tkr"]=st.text_input("股票代號",placeholder="DKNG / ORCL",key="stk").upper()
    scan_exp=st.text_input("到期日（選填）",placeholder="2026-08-21",key="exp2")
    scan_info=get_info(st.session_state["scan_tkr"]) if st.session_state.get("scan_tkr") else {}
    scan_price=scan_info.get("price")
    if st.session_state.get("scan_tkr") and scan_price: stock_card(scan_info,st.session_state["scan_tkr"])
    uploaded=st.file_uploader("上傳截圖（最多3張）",type=["png","jpg","jpeg","webp"],accept_multiple_files=True)
    if uploaded:
        b64s=[compress(f) for f in uploaded[:3]]
        with st.expander(f"📷 已上傳{len(uploaded[:3])}張"):
            cols=st.columns(min(len(uploaded),3))
            for i,f in enumerate(uploaded[:3]):
                with cols[i]: st.image(f,use_container_width=True)
        if st.button("🤖 AI 分析",key="scan"):
            if not API_KEY: st.error("請先設定 ANTHROPIC_API_KEY")
            else:
                with st.spinner("AI 讀取中..."):
                    try:
                        client=anthropic.Anthropic(api_key=API_KEY)
                        ph=f"現價${scan_price}。" if scan_price else "請從截圖讀取現價。"
                        if scan_exp: ph+=f"到期：{scan_exp}。"
                        prompt=(f"讀取期權鏈截圖（{st.session_state.get('scan_tkr','未知')}）。{ph}"
                                "讀每個行權價的callBid/callAsk/putBid/putAsk。"
                                '只回純JSON：{"currentPrice":29.0,"rows":[{"strike":30,"callBid":2.36,"callAsk":2.42,"putBid":3.10,"putAsk":3.20}]}')
                        parts=[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b}} for b in b64s]
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
            mr=max(x["ror"] for x in allc)
            st.markdown('<div style="display:flex;justify-content:space-between;align-items:flex-end;padding:6px 16px 12px;border-bottom:1px solid #30363D;margin-bottom:12px"><div><div style="font-size:20px;font-weight:900">'+tkr+'</div><div style="font-size:11px;color:#8B949E">現價 $'+s(cur2)+'</div></div><div style="text-align:right"><div style="font-size:10px;color:#8B949E;font-weight:700">最高報酬率</div><div style="font-size:18px;font-weight:800;color:#3FB950">'+f"{mr:.0f}%"+'</div></div></div>',unsafe_allow_html=True)
            top3=res.get("top3",[])
            if top3:
                st.markdown('<div style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin:0 16px 8px">整體最佳 Top 3</div>',unsafe_allow_html=True)
                for t3 in top3:
                    typ=t3["type"]; medal=t3.get("_medal","")
                    mt={"🥇":"金牌","🥈":"銀牌","🥉":"銅牌"}.get(medal,"")
                    tn={"bull":"看漲價差","bear":"看跌價差","call":"單買Call"}.get(typ,"")
                    sk2=f"${s(t3.get('buyStrike',0))} / ${s(t3.get('sellStrike',0))}" if typ in("bull","bear") else f"${s(t3.get('strike',0))} Call"
                    with st.expander(f"{mt}｜{tn} {sk2}｜{t3['ror']:.0f}%",expanded=(medal=="🥇")):
                        st.markdown(f'<div style="font-size:22px;text-align:center;margin-bottom:4px">{medal}</div>',unsafe_allow_html=True)
                        render_combo(t3,cur2,typ,f"stop_{medal}")
            def sg(items,label):
                if not items: return
                st.markdown('<div style="font-size:10px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 16px 8px">'+label+'</div>',unsafe_allow_html=True)
                for idx,it in enumerate(items):
                    tn={"bull":"看漲價差","bear":"看跌價差","call":"單買Call"}.get(it["type"],"")
                    sk2=f"${s(it.get('buyStrike',0))} / ${s(it.get('sellStrike',0))}" if it["type"] in("bull","bear") else f"${s(it.get('strike',0))} Call"
                    with st.expander(f"{tn} {sk2} · 平衡${s(it.get('breakeven',0))} · {it['ror']:.0f}%"):
                        render_combo(it,cur2,it["type"],f"s_{it['type']}_{idx}")
            sg(res["bull"],"📈 看漲價差 Bull Call — Top 3")
            sg(res["bear"],"📉 看跌價差 Bear Put — Top 3")
            sg(res["call"],"📞 單買 Call — Top 2")

with tab3:
    favs=load_favs()
    if not favs:
        st.markdown('<div style="background:#161B22;border-radius:12px;padding:28px;text-align:center;color:#8B949E;font-size:13px;margin:16px">尚無收藏<br><span style="font-size:11px">計算後點 ⭐ 收藏</span></div>',unsafe_allow_html=True)
    else:
        groups={}
        for f in favs: groups.setdefault(f.get("ticker","未命名"),[]).append(f)
        for tk,items in groups.items():
            st.markdown('<div style="font-size:15px;font-weight:800;margin:14px 16px 8px">📌 '+tk+' <span style="font-size:11px;color:#8B949E;font-weight:400">'+str(len(items))+'個</span></div>',unsafe_allow_html=True)
            for f in items:
                typ=f.get("sk",""); tn={"bull":"看漲價差","bear":"看跌價差","call":"單買Call","put":"單買Put"}.get(typ,"")
                bK=f.get("bK",0); sK=f.get("sK",0)
                sk2=f"${bK}/${sK}" if sK else f"${bK} {typ.upper()}"
                with st.expander(f"{tn} {sk2}"):
                    if f.get("maxProfit") is not None:
                        show_result(typ,bK,f.get("bP",0),sK,f.get("sP",0),f.get("maxProfit"),f.get("maxLoss",0),f.get("breakeven"),f.get("currentPrice",0))
                    if st.button("🗑 移除",key=f"del_{f.get('_id','')}"):
                        save_favs([x for x in load_favs() if x.get("_id")!=f.get("_id")]); st.rerun()

with tab4:
    h4=('<div style="padding:0 16px;color:#E6EDF3">'
        '<div style="background:#161B22;border-radius:12px;padding:14px;margin-bottom:12px">'
        '<div style="font-size:11px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">策略說明</div>'
        '<div style="font-size:13px;color:#8B949E;line-height:1.6">'
        '<b style="color:#E6EDF3">看漲價差</b> — 買低Call賣高Call，限定獲利和風險<br><br>'
        '<b style="color:#E6EDF3">看跌價差</b> — 買高Put賣低Put，限定獲利和風險<br><br>'
        '<b style="color:#E6EDF3">單買Call/Put</b> — 無限獲利潛力，最多虧損全部權利金'
        '</div></div>'
        '<div style="background:#161B22;border-radius:12px;padding:14px">'
        '<div style="font-size:11px;color:#8B949E;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">使用說明</div>'
        '<div style="font-size:13px;color:#8B949E;line-height:1.6">'
        '1. 點上方快捷或輸入股票代號<br>2. 選到期日<br>3. 選策略<br>4. 選行權價<br>5. 按計算損益'
        '</div></div></div>')
    st.markdown(h4,unsafe_allow_html=True)
