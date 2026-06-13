import streamlit as st
import anthropic
import base64
import json
import math
import re
from PIL import Image
import io

st.set_page_config(page_title="Options Pro", page_icon="📈", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', -apple-system, sans-serif !important; }
.stApp { background: #000000; color: #FFFFFF; }
.main .block-container { padding: 0 16px 80px; max-width: 430px; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.stTabs [data-baseweb="tab-list"] { background:#1A1A1A;border-radius:100px;padding:3px;gap:0;border:none;margin-bottom:20px; }
.stTabs [data-baseweb="tab"] { background:transparent!important;border-radius:100px;color:#666666;font-size:13px;font-weight:600;padding:8px 16px;border:none!important; }
.stTabs [aria-selected="true"] { background:#FFFFFF!important;color:#000000!important;border-radius:100px; }
.stTabs [data-baseweb="tab-highlight"],[data-baseweb="tab-border"] { display:none; }
.stTextInput>div>div,.stNumberInput>div>div>div { background:#1A1A1A!important;border:none!important;border-radius:12px!important; }
.stTextInput input,.stNumberInput input { background:#1A1A1A!important;border:none!important;border-radius:12px!important;color:#FFFFFF!important;font-size:16px!important;font-weight:500!important;padding:14px 16px!important;caret-color:#00C805; }
.stTextInput input:focus,.stNumberInput input:focus { outline:none!important;box-shadow:0 0 0 2px #00C805!important; }
.stTextInput label,.stNumberInput label { color:#666666!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }
.stButton>button { background:#00C805!important;color:#000000!important;border:none!important;border-radius:100px!important;font-size:15px!important;font-weight:700!important;padding:14px 24px!important;width:100%!important;letter-spacing:-0.2px; }
.stButton>button:hover { background:#00B504!important; }
[data-testid="stMetric"] { background:#1A1A1A;border:none;border-radius:16px;padding:16px; }
[data-testid="stMetricLabel"] { font-size:11px!important;color:#666666!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }
[data-testid="stMetricValue"] { font-size:22px!important;font-weight:700!important;color:#FFFFFF!important;letter-spacing:-0.5px; }
[data-testid="stMetricDelta"] { display:none; }
[data-testid="stFileUploader"] { background:#1A1A1A;border:1.5px dashed #333333;border-radius:16px;padding:8px; }
[data-testid="stExpander"] { background:#1A1A1A!important;border:none!important;border-radius:16px!important;margin-bottom:10px;overflow:hidden; }
[data-testid="stExpander"] summary { background:#1A1A1A!important;border-radius:16px!important;color:#FFFFFF!important;font-weight:600!important;padding:16px!important; }
[data-testid="stExpander"]>div>div { background:#111111!important;border-top:1px solid #222222!important; }
.stRadio>label { color:#666666!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase;letter-spacing:0.8px; }
[data-testid="stRadio"]>div { background:#1A1A1A;border-radius:100px;padding:3px;display:flex;gap:0; }
[data-testid="stRadio"] label { background:transparent!important;border-radius:100px!important;padding:8px 14px!important;color:#666666!important;font-size:12px!important;font-weight:600!important;flex:1;text-align:center;cursor:pointer; }
[data-testid="stRadio"] label:has(input:checked) { background:#FFFFFF!important;color:#000000!important; }
.stSuccess { background:#001A00!important;border:1px solid #00C805!important;border-radius:12px!important;color:#00C805!important; }
.stError { background:#1A0000!important;border:1px solid #FF3B30!important;border-radius:12px!important;color:#FF3B30!important; }
.stInfo { background:#00001A!important;border:1px solid #007AFF!important;border-radius:12px!important;color:#007AFF!important; }
hr { border-color:#1A1A1A!important;margin:20px 0!important; }
table { width:100%;border-collapse:collapse;font-size:13px; }
thead th { background:#000000;color:#444444;font-size:10px;font-weight:700;padding:10px 14px;text-align:left;border-bottom:1px solid #1A1A1A;text-transform:uppercase;letter-spacing:1px; }
tbody td { padding:10px 14px;border-bottom:1px solid #111111; }
tr.profit { background:rgba(0,200,5,0.04); }
tr.loss { background:rgba(255,59,48,0.04); }
tr.breakeven { background:rgba(255,159,10,0.05); }
td.green { color:#00C805;font-weight:600; }
td.red { color:#FF3B30;font-weight:600; }
td.yellow { color:#FF9F0A;font-weight:600; }
td.price { color:#FFFFFF;font-weight:500; }
.pill { font-size:9px;padding:2px 6px;border-radius:100px;margin-left:5px;font-weight:700;letter-spacing:0.3px; }
.pill-be { background:#1A1000;color:#FF9F0A; }
.pill-max { background:#001A00;color:#00C805; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding:28px 0 20px;text-align:center;border-bottom:1px solid #1A1A1A;margin:0 -16px 24px">
  <div style="font-size:11px;color:#444444;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">OPTIONS</div>
  <div style="font-size:28px;font-weight:900;color:#FFFFFF;letter-spacing:-1.5px">Strategy Pro</div>
</div>
""", unsafe_allow_html=True)

api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

def get_step(s): return 1 if s < 20 else 5 if s <= 50 else 10

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

def fmt(v, decimals=None):
    if v is None: return "N/A"
    if decimals is not None: return f"{v:.{decimals}f}"
    return f"{v:.2f}" if isinstance(v, float) and abs(v) < 10 else f"{v:.0f}"

def compress_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.width > 1200:
        img = img.resize((1200, int(img.height*1200/img.width)), Image.LANCZOS)
    if img.mode != "RGB": img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    buf.seek(0)
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
        near_be = abs(p-be)<=step*0.55
        is_max = (t=="bull" and p>=ss) or (t=="bear" and p<=ss)
        tag = '<span class="pill pill-be">平衡點</span>' if near_be else ('<span class="pill pill-max">MAX</span>' if is_max else "")
        rc = "profit" if v>1 else "loss" if v<-1 else "breakeven"
        vc = "green" if v>0 else "red" if v<0 else "yellow"
        s1="+" if v>=0 else ""; s2="+" if ret>=0 else ""
        rows.append(f'<tr class="{rc}"><td class="price">${p:.0f}{tag}</td><td class="{vc}">{s1}${fmt(v)}</td><td class="{vc}">{s2}{ret:.0f}%</td></tr>')
        p = round(p+step, 3)
    st.markdown(f"""
    <div style="background:#1A1A1A;border-radius:16px;overflow:hidden;margin-top:12px">
      <div style="padding:12px 14px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #111111">
        <span style="font-size:10px;font-weight:700;color:#444444;text-transform:uppercase;letter-spacing:1px">損益對照表</span>
        <span style="font-size:10px;font-weight:700;background:#111111;color:#555555;padding:3px 10px;border-radius:100px">每 ${step}</span>
      </div>
      <table><thead><tr><th>股價</th><th>損益 / 張</th><th>報酬率</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>
    </div>""", unsafe_allow_html=True)

def show_calc_results(t, max_p, max_l, be, nc, bs=0, ss=0, spread=0, strike=0, premium=0):
    ror = (max_p/max_l*100) if max_l and max_p else 0
    rr = (max_p/max_l) if max_l and max_p else 0
    move = f"+{((be-bs)/bs*100):.1f}%" if t=="bull" else f"-{((bs-be)/bs*100):.1f}%" if t=="bear" else f"+{((be-strike)/strike*100):.1f}%"
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:8px">
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;text-align:center">
        <div style="font-size:10px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">最大獲利</div>
        <div style="font-size:20px;font-weight:700;color:#00C805">+${fmt(max_p)}</div>
      </div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;text-align:center">
        <div style="font-size:10px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">最大虧損</div>
        <div style="font-size:20px;font-weight:700;color:#FF3B30">-${fmt(max_l)}</div>
      </div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;text-align:center">
        <div style="font-size:10px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">損益平衡</div>
        <div style="font-size:20px;font-weight:700;color:#FFFFFF">${fmt(be)}</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:16px">
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;text-align:center">
        <div style="font-size:10px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">報酬率</div>
        <div style="font-size:20px;font-weight:700;color:{'#00C805' if ror>0 else '#FF3B30'}">{ror:.0f}%</div>
      </div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;text-align:center">
        <div style="font-size:10px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">盈虧比</div>
        <div style="font-size:20px;font-weight:700;color:#FFFFFF">{rr:.2f}x</div>
      </div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;text-align:center">
        <div style="font-size:10px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">需漲跌</div>
        <div style="font-size:20px;font-weight:700;color:#FFFFFF">{move}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    show_ladder(t, bs, ss, nc, max_l, be, spread, strike, premium)

# ── Tabs ──────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["計算", "比較", "AI 掃描", "說明"])

# ══════════════════════════
# TAB 1: CALC
# ══════════════════════════
with tab1:
    ticker = st.text_input("股票代號", placeholder="ORCL  /  DKNG  /  IBIT", key="t1").upper()
    calc_type = st.radio("策略", ["📈 Bull Call", "📉 Bear Put", "📞 單 Call"], horizontal=True)

    if "Bull" in calc_type:
        st.markdown('<p style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">買入 Call（低行權價）</p>', unsafe_allow_html=True)
        c1,c2=st.columns(2)
        buy_s=c1.number_input("行權價",key="b_bs",min_value=0.0,format="%.2f")
        buy_p=c2.number_input("權利金",key="b_bp",min_value=0.0,format="%.2f")
        st.markdown('<p style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">賣出 Call（高行權價）</p>', unsafe_allow_html=True)
        c1,c2=st.columns(2)
        sell_s=c1.number_input("行權價",key="b_ss",min_value=0.0,format="%.2f")
        sell_p=c2.number_input("權利金",key="b_sp",min_value=0.0,format="%.2f")
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("計算損益",key="cb"):
            if buy_s and buy_p and sell_s and sell_p:
                nc=buy_p-sell_p;sp=sell_s-buy_s;mp=(sp-nc)*100;ml=nc*100
                st.divider()
                show_calc_results("bull",mp,ml,buy_s+nc,nc,bs=buy_s,ss=sell_s,spread=sp)
            else: st.error("請填入所有數值")

    elif "Bear" in calc_type:
        st.markdown('<p style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">買入 Put（高行權價）</p>', unsafe_allow_html=True)
        c1,c2=st.columns(2)
        buy_s=c1.number_input("行權價",key="p_bs",min_value=0.0,format="%.2f")
        buy_p=c2.number_input("權利金",key="p_bp",min_value=0.0,format="%.2f")
        st.markdown('<p style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">賣出 Put（低行權價）</p>', unsafe_allow_html=True)
        c1,c2=st.columns(2)
        sell_s=c1.number_input("行權價",key="p_ss",min_value=0.0,format="%.2f")
        sell_p=c2.number_input("權利金",key="p_sp",min_value=0.0,format="%.2f")
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("計算損益",key="cp"):
            if buy_s and buy_p and sell_s and sell_p:
                nc=buy_p-sell_p;sp=buy_s-sell_s;mp=(sp-nc)*100;ml=nc*100
                st.divider()
                show_calc_results("bear",mp,ml,buy_s-nc,nc,bs=buy_s,ss=sell_s,spread=sp)
            else: st.error("請填入所有數值")

    else:
        st.markdown('<p style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">買入 Call</p>', unsafe_allow_html=True)
        c1,c2,c3=st.columns(3)
        strike=c1.number_input("行權價",key="c_ks",min_value=0.0,format="%.2f")
        premium=c2.number_input("權利金",key="c_pp",min_value=0.0,format="%.2f")
        target=c3.number_input("目標價",key="c_tp",min_value=0.0,format="%.2f")
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("計算損益",key="cc"):
            if strike and premium:
                ml=premium*100;be=strike+premium
                mp=(target-strike-premium)*100 if target else None
                st.divider()
                show_calc_results("call",mp or 0,ml,be,premium,strike=strike,premium=premium)
            else: st.error("請填入行權價和權利金")

# ══════════════════════════
# TAB 2: COMPARE
# ══════════════════════════
with tab2:
    c1,c2,c3=st.columns(3)
    cmp_ticker=c1.text_input("股票",key="cmp_t",placeholder="ORCL").upper()
    cmp_cur=c2.number_input("現價",key="cmp_c",min_value=0.0,format="%.2f")
    cmp_target=c3.number_input("目標價",key="cmp_tg",min_value=0.0,format="%.2f")
    st.markdown('<p style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">📈 Bull Call Spread</p>', unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    cbbs=c1.number_input("買入價",key="cbbs",min_value=0.0,format="%.2f")
    cbbp=c2.number_input("買入金",key="cbbp",min_value=0.0,format="%.2f")
    cbss=c3.number_input("賣出價",key="cbss",min_value=0.0,format="%.2f")
    cbsp=c4.number_input("賣出金",key="cbsp",min_value=0.0,format="%.2f")
    st.markdown('<p style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">📉 Bear Put Spread</p>', unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    cpbs=c1.number_input("買入價",key="cpbs",min_value=0.0,format="%.2f")
    cpbp=c2.number_input("買入金",key="cpbp",min_value=0.0,format="%.2f")
    cpss=c3.number_input("賣出價",key="cpss",min_value=0.0,format="%.2f")
    cpsp=c4.number_input("賣出金",key="cpsp",min_value=0.0,format="%.2f")
    st.markdown('<p style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">📞 單買 Call</p>', unsafe_allow_html=True)
    c1,c2=st.columns(2)
    ccks=c1.number_input("行權價",key="ccks",min_value=0.0,format="%.2f")
    ccpp=c2.number_input("權利金",key="ccpp",min_value=0.0,format="%.2f")
    st.markdown("<br>",unsafe_allow_html=True)
    if st.button("比較三種策略",key="cmp_btn"):
        results={}
        if cbbs and cbbp and cbss and cbsp:
            nc=cbbp-cbsp;sp=cbss-cbbs;ml=nc*100;mp=(sp-nc)*100
            pat=spread_pnl("bull",cmp_target,cbbs,cbss,nc,ml)
            results["Bull Call"]={"最大獲利":f"+${fmt(mp)}","最大虧損":f"-${fmt(ml)}","損益平衡":f"${fmt(cbbs+nc)}","目標損益":f"{'+' if pat>=0 else ''}${fmt(pat)}","報酬率":f"{mp/ml*100:.0f}%","成本":f"${fmt(ml)}","_ror":mp/ml*100}
        if cpbs and cpbp and cpss and cpsp:
            nc=cpbp-cpsp;sp=cpbs-cpss;ml=nc*100;mp=(sp-nc)*100
            pat=spread_pnl("bear",cmp_target,cpbs,cpss,nc,ml)
            results["Bear Put"]={"最大獲利":f"+${fmt(mp)}","最大虧損":f"-${fmt(ml)}","損益平衡":f"${fmt(cpbs-nc)}","目標損益":f"{'+' if pat>=0 else ''}${fmt(pat)}","報酬率":f"{mp/ml*100:.0f}%","成本":f"${fmt(ml)}","_ror":mp/ml*100}
        if ccks and ccpp:
            ml=ccpp*100;pat=call_pnl(cmp_target,ccks,ccpp)
            results["單Call"]={"最大獲利":f"+${fmt(max(pat,0))}","最大虧損":f"-${fmt(ml)}","損益平衡":f"${fmt(ccks+ccpp)}","目標損益":f"{'+' if pat>=0 else ''}${fmt(pat)}","報酬率":f"{pat/ml*100:.0f}%","成本":f"${fmt(ml)}","_ror":pat/ml*100}
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
            st.divider()
            st.markdown("\n".join(rows_md))
            st.success(f"🏆 最佳策略：**{best}** — {results[best]['報酬率']}")

# ══════════════════════════
# TAB 3: AI SCAN
# ══════════════════════════
with tab3:
    st.markdown("""
    <div style="background:#0A1A0A;border:1px solid #00C805;border-radius:16px;padding:16px;margin-bottom:20px">
      <div style="font-size:13px;color:#00C805;font-weight:700;margin-bottom:4px">🤖 AI 智能分析</div>
      <div style="font-size:12px;color:#555555;line-height:1.5">上傳 1-3 張期權鏈截圖，AI 自動找出<br>Bull x3、Bear x3、Call x2，共 8 個最佳組合</div>
    </div>
    """, unsafe_allow_html=True)

    scan_ticker = st.text_input("股票代號", placeholder="DKNG  /  ORCL  /  IBIT", key="stk").upper()
    uploaded_files = st.file_uploader("上傳截圖（最多3張）", type=["png","jpg","jpeg","webp"], accept_multiple_files=True)

    if uploaded_files:
        cols = st.columns(len(uploaded_files))
        all_b64s = []
        for i, f in enumerate(uploaded_files[:3]):
            with cols[i]:
                st.image(f, use_container_width=True)
            b64 = compress_image(f)
            all_b64s.append(b64)
            kb = len(b64)*3//4//1024
            st.caption(f"圖{i+1}：{kb} KB")

        if st.button("🤖  AI 分析 8 個最佳組合", key="scan_btn"):
            if not api_key:
                st.error("請先設定 API Key")
            else:
                with st.spinner("AI 深度分析中，約 20-30 秒..."):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        prompt = f"""你是頂級期權策略分析師。分析這些期權鏈截圖（股票：{scan_ticker or '未知'}）。

第一步：從所有截圖仔細讀取每個行權價對應的 Call 賣盤價、Call 買盤價、Put 賣盤價、Put 買盤價。把所有數據列出來再計算。

第二步：按以下公式計算每個可能組合：
- Bull Call Spread：淨成本 = 低Call賣盤 - 高Call買盤，最大獲利 = (行權價差-淨成本)×100，報酬率 = 最大獲利/最大虧損×100
- Bear Put Spread：淨成本 = 高Put賣盤 - 低Put買盤，最大獲利 = (行權價差-淨成本)×100，報酬率同上
- Single Call：損益平衡 = 行權價+賣盤價，報酬率用(行權價×1.15-行權價-賣盤價)/賣盤價×100

第三步：選出報酬率最高且合理的：Bull 前3名、Bear 前3名、Call 前2名（共8個）

第四步：為每個組合寫優點和缺點各1句（20字內）

第五步：從8個組合中選出整體最佳Top3，考慮報酬率、風險、成功概率

回傳純JSON，不含任何說明文字：
{{
  "currentPrice": 29.0,
  "ticker": "DKNG",
  "bull": [
    {{"rank":1,"buyStrike":30,"buyPremium":2.42,"sellStrike":35,"sellPremium":0.95,"maxProfit":358,"maxLoss":147,"breakeven":31.47,"ror":243,"pros":"報酬率高，成本低","cons":"需漲幅超過8%","stars":5}},
    {{"rank":2,"buyStrike":30,"buyPremium":2.42,"sellStrike":37.5,"sellPremium":0.60,"maxProfit":558,"maxLoss":182,"breakeven":31.82,"ror":307,"pros":"獲利空間大","cons":"需漲幅更高","stars":4}},
    {{"rank":3,"buyStrike":32.5,"buyPremium":1.56,"sellStrike":37.5,"sellPremium":0.60,"maxProfit":404,"maxLoss":96,"breakeven":33.46,"ror":421,"pros":"成本極低","cons":"需先漲才有利","stars":4}}
  ],
  "bear": [
    {{"rank":1,"buyStrike":27.5,"buyPremium":1.94,"sellStrike":25,"sellPremium":1.06,"maxProfit":212,"maxLoss":88,"breakeven":26.62,"ror":241,"pros":"看跌保護好","cons":"Put流動性低","stars":4}},
    {{"rank":2,"buyStrike":25,"buyPremium":1.10,"sellStrike":22.5,"sellPremium":0.51,"maxProfit":309,"maxLoss":59,"breakeven":24.41,"ror":524,"pros":"報酬率極高","cons":"需大跌才獲利","stars":5}},
    {{"rank":3,"buyStrike":27.5,"buyPremium":1.94,"sellStrike":22.5,"sellPremium":0.51,"breakeven":26.57,"maxProfit":357,"maxLoss":143,"ror":250,"pros":"價差大獲利高","cons":"成本較高","stars":4}}
  ],
  "call": [
    {{"rank":1,"strike":32.5,"premium":1.56,"breakeven":34.06,"ror":85,"pros":"成本低槓桿高","cons":"虛值需大漲","stars":3}},
    {{"rank":2,"strike":30,"premium":2.42,"breakeven":32.42,"ror":52,"pros":"較接近現價","cons":"成本相對高","stars":3}}
  ],
  "top3Overall": [
    {{"overallRank":1,"type":"bear","ref_rank":2,"medal":"🥇","summary":"最高報酬率524%，風險極低，最值得考慮"}},
    {{"overallRank":2,"type":"bull","ref_rank":3,"medal":"🥈","summary":"Bull中報酬率最高421%，成本僅$96"}},
    {{"overallRank":3,"type":"bull","ref_rank":1,"medal":"🥉","summary":"均衡選擇，報酬率243%，損益平衡較易達到"}}
  ]
}}"""

                        content_parts = []
                        for b64 in all_b64s:
                            content_parts.append({"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":b64}})
                        content_parts.append({"type":"text","text":prompt})

                        msg = client.messages.create(
                            model="claude-sonnet-4-6", max_tokens=3000,
                            messages=[{"role":"user","content":content_parts}]
                        )
                        text = msg.content[0].text.strip()
                        match = re.search(r'\{[\s\S]*\}', text)
                        if not match:
                            st.error("格式錯誤：" + text[:300])
                        else:
                            data = json.loads(match.group())
                            cur = data.get("currentPrice", 0)
                            tkr = data.get("ticker", scan_ticker)

                            st.markdown(f"""
                            <div style="display:flex;justify-content:space-between;align-items:center;margin:20px 0 16px">
                              <div>
                                <div style="font-size:22px;font-weight:900;color:#FFFFFF;letter-spacing:-0.5px">{tkr}</div>
                                <div style="font-size:13px;color:#555555">現價 ${fmt(cur)}</div>
                              </div>
                              <div style="background:#1A1A1A;border-radius:12px;padding:8px 14px;text-align:right">
                                <div style="font-size:10px;color:#444;font-weight:700;letter-spacing:1px">分析結果</div>
                                <div style="font-size:14px;font-weight:700;color:#00C805">8 個組合</div>
                              </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # ── TOP 3 OVERALL ──
                            top3 = data.get("top3Overall", [])
                            if top3:
                                st.markdown('<div style="font-size:11px;color:#FFD700;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin:0 0 12px">🏆 整體最佳 Top 3</div>', unsafe_allow_html=True)
                                for t3 in top3:
                                    medal = t3.get("medal","")
                                    t3type = t3.get("type","")
                                    t3ref = t3.get("ref_rank",1)
                                    summary = t3.get("summary","")
                                    # find the actual entry
                                    ref_list = data.get(t3type, [])
                                    ref_entry = next((x for x in ref_list if x.get("rank")==t3ref), {})
                                    if not ref_entry and ref_list: ref_entry = ref_list[0]
                                    tc = "#007AFF" if t3type=="bull" else "#FF3B30" if t3type=="bear" else "#00C805"
                                    tl = "Bull Call" if t3type=="bull" else "Bear Put" if t3type=="bear" else "Single Call"
                                    if t3type in ["bull","bear"]:
                                        strikes = f"${fmt(ref_entry.get('buyStrike',0))} / ${fmt(ref_entry.get('sellStrike',0))}"
                                    else:
                                        strikes = f"${fmt(ref_entry.get('strike',0))} Call"
                                    ror_v = ref_entry.get("ror",0)
                                    stars = ref_entry.get("stars",3)
                                    star_str = "★"*stars + "☆"*(5-stars)
                                    st.markdown(f"""
                                    <div style="background:linear-gradient(135deg,#1A1A1A,#111111);border:1px solid #2A2A2A;border-radius:16px;padding:16px;margin-bottom:10px">
                                      <div style="display:flex;justify-content:space-between;align-items:flex-start">
                                        <div>
                                          <div style="font-size:22px;margin-bottom:4px">{medal}</div>
                                          <div style="font-size:16px;font-weight:800;color:#FFFFFF;letter-spacing:-0.3px">{strikes}</div>
                                          <div style="font-size:11px;color:{tc};font-weight:600;margin-top:2px;text-transform:uppercase;letter-spacing:0.5px">{tl}</div>
                                          <div style="font-size:13px;color:#FFD700;margin-top:4px">{star_str}</div>
                                        </div>
                                        <div style="text-align:right">
                                          <div style="font-size:28px;font-weight:900;color:#00C805;letter-spacing:-1px">{ror_v:.0f}%</div>
                                          <div style="font-size:9px;color:#444;font-weight:700;letter-spacing:1px">ROI</div>
                                        </div>
                                      </div>
                                      <div style="margin-top:10px;padding-top:10px;border-top:1px solid #222;font-size:12px;color:#888888;line-height:1.5">{summary}</div>
                                    </div>
                                    """, unsafe_allow_html=True)

                            # ── OVERVIEW TABLE ──
                            st.markdown('<div style="font-size:11px;color:#666666;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin:24px 0 12px">全部 8 個組合總覽</div>', unsafe_allow_html=True)

                            all_combos = []
                            for item in data.get("bull",[]): all_combos.append(("bull",item))
                            for item in data.get("bear",[]): all_combos.append(("bear",item))
                            for item in data.get("call",[]): all_combos.append(("call",item))

                            overview_rows = ""
                            for typ, item in all_combos:
                                tc = "#007AFF" if typ=="bull" else "#FF3B30" if typ=="bear" else "#00C805"
                                tl = "Bull" if typ=="bull" else "Bear" if typ=="bear" else "Call"
                                ror_v = item.get("ror",0)
                                mp = item.get("maxProfit") or item.get("ror",0)
                                ml = item.get("maxLoss",0)
                                stars = item.get("stars",3)
                                star_str = "★"*stars+"☆"*(5-stars)
                                if typ in ["bull","bear"]:
                                    strikes = f"${fmt(item.get('buyStrike',0))}/${fmt(item.get('sellStrike',0))}"
                                else:
                                    strikes = f"${fmt(item.get('strike',0))}"
                                ror_color = "#00C805" if ror_v >= 200 else "#FF9F0A" if ror_v >= 100 else "#FFFFFF"
                                overview_rows += f"""<tr>
                                  <td><span style="color:{tc};font-weight:700;font-size:11px">{tl}</span><br><span style="font-size:12px;color:#FFFFFF;font-weight:600">{strikes}</span></td>
                                  <td style="color:{ror_color};font-weight:700;font-size:14px">{ror_v:.0f}%</td>
                                  <td style="color:#00C805;font-size:12px">+${fmt(item.get('maxProfit',0))}</td>
                                  <td style="color:#FF3B30;font-size:12px">-${fmt(ml)}</td>
                                  <td style="color:#FFD700;font-size:11px">{star_str}</td>
                                </tr>"""

                            st.markdown(f"""
                            <div style="background:#1A1A1A;border-radius:16px;overflow:hidden;margin-bottom:24px">
                              <table style="width:100%;border-collapse:collapse;font-size:12px">
                                <thead><tr style="background:#111111">
                                  <th style="padding:10px 12px;color:#444;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;border-bottom:1px solid #222">組合</th>
                                  <th style="padding:10px 8px;color:#444;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;border-bottom:1px solid #222">ROI</th>
                                  <th style="padding:10px 8px;color:#444;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;border-bottom:1px solid #222">最大獲利</th>
                                  <th style="padding:10px 8px;color:#444;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;border-bottom:1px solid #222">最大虧損</th>
                                  <th style="padding:10px 8px;color:#444;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;border-bottom:1px solid #222">評分</th>
                                </tr></thead>
                                <tbody style="color:#FFFFFF">{overview_rows}</tbody>
                              </table>
                            </div>
                            """, unsafe_allow_html=True)

                            # ── DETAIL SECTIONS ──
                            def show_detail_group(items, typ, header_color, header_label):
                                if not items: return
                                st.markdown(f'<div style="font-size:11px;color:{header_color};font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin:8px 0 12px">{header_label}</div>', unsafe_allow_html=True)
                                rank_medals = ["🥇","🥈","🥉"]
                                for i, r in enumerate(items):
                                    ror_v = r.get("ror",0)
                                    mp = r.get("maxProfit",0)
                                    ml_v = r.get("maxLoss",0)
                                    be = r.get("breakeven",0)
                                    stars = r.get("stars",3)
                                    pros = r.get("pros","")
                                    cons = r.get("cons","")
                                    star_str = "★"*stars+"☆"*(5-stars)
                                    medal = rank_medals[i] if i < 3 else ""
                                    if typ in ["bull","bear"]:
                                        bs=r.get("buyStrike",0); ss=r.get("sellStrike",0)
                                        bp=r.get("buyPremium",0); sp2=r.get("sellPremium",0)
                                        title = f"{medal} ${fmt(bs)} / ${fmt(ss)}  |  ROI {ror_v:.0f}%"
                                    else:
                                        bs=r.get("strike",0); bp=r.get("premium",0)
                                        ss=0; sp2=0
                                        title = f"{medal} ${fmt(bs)} Call  |  ROI {ror_v:.0f}%"

                                    with st.expander(title, expanded=(i==0)):
                                        st.markdown(f"""
                                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
                                          <div>
                                            <div style="font-size:20px;font-weight:800;color:#FFFFFF;letter-spacing:-0.5px">
                                              {"$"+fmt(bs)+" / $"+fmt(ss) if typ in ["bull","bear"] else "$"+fmt(bs)+" Call"}
                                            </div>
                                            <div style="color:#FFD700;font-size:14px;margin-top:4px">{star_str}</div>
                                          </div>
                                          <div style="text-align:right">
                                            <div style="font-size:28px;font-weight:900;color:#00C805;letter-spacing:-1px">{ror_v:.0f}%</div>
                                            <div style="font-size:9px;color:#444;font-weight:700;letter-spacing:1px">ROI</div>
                                          </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                        c1,c2,c3=st.columns(3)
                                        c1.metric("最大獲利", f"+${fmt(mp)}")
                                        c2.metric("最大虧損", f"-${fmt(ml_v)}")
                                        c3.metric("損益平衡", f"${fmt(be)}")
                                        if typ in ["bull","bear"]:
                                            c1,c2=st.columns(2)
                                            c1.metric("買入金", f"${fmt(bp)}")
                                            c2.metric("賣出金", f"${fmt(sp2)}")
                                        else:
                                            st.metric("權利金", f"${fmt(bp)}")

                                        # Pros/Cons
                                        st.markdown(f"""
                                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0">
                                          <div style="background:#0A1A0A;border:1px solid #1A3A1A;border-radius:12px;padding:10px 12px">
                                            <div style="font-size:9px;color:#00C805;font-weight:700;letter-spacing:1px;margin-bottom:4px">✅ 優點</div>
                                            <div style="font-size:12px;color:#AAAAAA;line-height:1.4">{pros}</div>
                                          </div>
                                          <div style="background:#1A0A0A;border:1px solid #3A1A1A;border-radius:12px;padding:10px 12px">
                                            <div style="font-size:9px;color:#FF3B30;font-weight:700;letter-spacing:1px;margin-bottom:4px">⚠️ 缺點</div>
                                            <div style="font-size:12px;color:#AAAAAA;line-height:1.4">{cons}</div>
                                          </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                        # Ladder
                                        if typ in ["bull","bear"] and bs and ss and bp and sp2:
                                            nc = bp-sp2
                                            show_ladder(typ, bs, ss, nc, nc*100, be, abs(bs-ss), bs, bp)
                                        elif typ=="call" and bs and bp:
                                            show_ladder("call", 0, 0, bp, bp*100, be, 0, bs, bp)

                            show_detail_group(data.get("bull",[]), "bull", "#007AFF", "📈 Bull Call Spread — Top 3")
                            show_detail_group(data.get("bear",[]), "bear", "#FF3B30", "📉 Bear Put Spread — Top 3")
                            show_detail_group(data.get("call",[]), "call", "#00C805", "📞 Single Call — Top 2")

                    except Exception as e:
                        st.error(f"分析失敗：{e}")

# ══════════════════════════
# TAB 4: HELP
# ══════════════════════════
with tab4:
    st.markdown("""
    <div style="color:#FFFFFF">
    <div style="margin-bottom:20px">
      <div style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">策略說明</div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;font-size:13px;color:#AAAAAA;line-height:1.6">
        <b style="color:#FFFFFF">Bull Call Spread</b> — 看漲。買低Call賣高Call，限定獲利和風險。<br><br>
        <b style="color:#FFFFFF">Bear Put Spread</b> — 看跌。買高Put賣低Put，限定獲利和風險。<br><br>
        <b style="color:#FFFFFF">單買 Call</b> — 看漲。理論上無限獲利，最多虧損全部權利金。
      </div>
    </div>
    <div style="margin-bottom:20px">
      <div style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">步距規則</div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;font-size:13px;color:#AAAAAA;line-height:1.8">
        價差 &lt; $20 → 每 $1<br>
        價差 $20–50 → 每 $5<br>
        價差 &gt; $50 → 每 $10
      </div>
    </div>
    <div>
      <div style="font-size:11px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">AI 分析說明</div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;font-size:13px;color:#AAAAAA;line-height:1.6">
        每次分析費用約 $0.02–0.05<br>
        可上傳最多 3 張截圖合併分析<br>
        報酬率 = 最大獲利 ÷ 最大成本 × 100%
      </div>
    </div>
    </div>
    """, unsafe_allow_html=True)
