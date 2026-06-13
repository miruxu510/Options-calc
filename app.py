import streamlit as st
import anthropic
import base64
import json
import math
import re
from PIL import Image
import io

st.set_page_config(
    page_title="Options Pro",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&display=swap');

* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

.stApp { background: #000000; color: #FFFFFF; }
.main .block-container { padding: 0 16px 80px; max-width: 430px; }

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* Tabs — pill style */
.stTabs [data-baseweb="tab-list"] {
    background: #1A1A1A;
    border-radius: 100px;
    padding: 3px;
    gap: 0;
    border: none;
    margin-bottom: 20px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 100px;
    color: #666666;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 16px;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: #000000 !important;
    border-radius: 100px;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* Inputs */
.stTextInput > div > div, .stNumberInput > div > div > div {
    background: #1A1A1A !important;
    border: none !important;
    border-radius: 12px !important;
}
.stTextInput input, .stNumberInput input {
    background: #1A1A1A !important;
    border: none !important;
    border-radius: 12px !important;
    color: #FFFFFF !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    padding: 14px 16px !important;
    caret-color: #00C805;
}
.stTextInput input:focus, .stNumberInput input:focus {
    outline: none !important;
    box-shadow: 0 0 0 2px #00C805 !important;
}
.stTextInput label, .stNumberInput label {
    color: #666666 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 6px;
}

/* Buttons */
.stButton > button {
    background: #00C805 !important;
    color: #000000 !important;
    border: none !important;
    border-radius: 100px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    padding: 14px 24px !important;
    width: 100% !important;
    letter-spacing: -0.2px;
    transition: all 0.15s ease !important;
}
.stButton > button:hover { background: #00B504 !important; transform: scale(0.99); }
.stButton > button:active { transform: scale(0.97) !important; }

/* Metric cards */
[data-testid="stMetric"] {
    background: #1A1A1A;
    border: none;
    border-radius: 16px;
    padding: 16px;
}
[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    color: #666666 !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
[data-testid="stMetricValue"] {
    font-size: 22px !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    letter-spacing: -0.5px;
}
[data-testid="stMetricDelta"] { display: none; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: #1A1A1A;
    border: 1.5px dashed #333333;
    border-radius: 16px;
    padding: 8px;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"]:hover { border-color: #00C805; }
[data-testid="stFileUploader"] label { color: #666666 !important; }

/* Expander */
[data-testid="stExpander"] {
    background: #1A1A1A !important;
    border: none !important;
    border-radius: 16px !important;
    margin-bottom: 10px;
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    background: #1A1A1A !important;
    border-radius: 16px !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    padding: 16px !important;
}
[data-testid="stExpander"] > div > div {
    background: #111111 !important;
    border-top: 1px solid #222222 !important;
}

/* Radio */
.stRadio > label {
    color: #666666 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
.stRadio [data-testid="stMarkdownContainer"] p { display: none; }
[data-testid="stRadio"] > div {
    background: #1A1A1A;
    border-radius: 100px;
    padding: 3px;
    display: flex;
    gap: 0;
}
[data-testid="stRadio"] label {
    background: transparent !important;
    border-radius: 100px !important;
    padding: 8px 14px !important;
    color: #666666 !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    flex: 1;
    text-align: center;
    cursor: pointer;
}
[data-testid="stRadio"] label:has(input:checked) {
    background: #FFFFFF !important;
    color: #000000 !important;
}

/* Success/Error/Info */
.stSuccess {
    background: #001A00 !important;
    border: 1px solid #00C805 !important;
    border-radius: 12px !important;
    color: #00C805 !important;
}
.stError {
    background: #1A0000 !important;
    border: 1px solid #FF3B30 !important;
    border-radius: 12px !important;
    color: #FF3B30 !important;
}
.stInfo {
    background: #00001A !important;
    border: 1px solid #007AFF !important;
    border-radius: 12px !important;
    color: #007AFF !important;
}

/* Spinner */
.stSpinner > div { border-top-color: #00C805 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 0px; }

/* Divider */
hr { border-color: #1A1A1A !important; margin: 20px 0 !important; }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th {
    background: #000000;
    color: #444444;
    font-size: 10px;
    font-weight: 700;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid #1A1A1A;
    text-transform: uppercase;
    letter-spacing: 1px;
}
tbody td { padding: 10px 14px; border-bottom: 1px solid #111111; }
tr.profit { background: rgba(0,200,5,0.04); }
tr.loss { background: rgba(255,59,48,0.04); }
tr.breakeven { background: rgba(255,159,10,0.05); }
td.green { color: #00C805; font-weight: 600; }
td.red { color: #FF3B30; font-weight: 600; }
td.yellow { color: #FF9F0A; font-weight: 600; }
td.price { color: #FFFFFF; font-weight: 500; }
.pill { font-size: 9px; padding: 2px 6px; border-radius: 100px; margin-left: 5px; font-weight: 700; letter-spacing: 0.3px; }
.pill-be { background: #1A1000; color: #FF9F0A; }
.pill-max { background: #001A00; color: #00C805; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 28px 0 20px; text-align: center; border-bottom: 1px solid #1A1A1A; margin: 0 -16px 24px;">
  <div style="font-size: 13px; color: #666666; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 6px;">OPTIONS</div>
  <div style="font-size: 28px; font-weight: 800; color: #FFFFFF; letter-spacing: -1px; line-height: 1.1;">Strategy Calculator</div>
</div>
""", unsafe_allow_html=True)

# ── API Key ───────────────────────────────────────────────────────
api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── Helpers ───────────────────────────────────────────────────────
def get_step(s):
    return 1 if s < 20 else 5 if s <= 50 else 10

def spread_pnl(t, price, bs, ss, nc, ml):
    sp = abs(bs - ss); mp = (sp - nc) * 100
    if t == "bull":
        if price <= bs: return -ml
        if price >= ss: return mp
        return ((price - bs) - nc) * 100
    else:
        if price >= bs: return -ml
        if price <= ss: return mp
        return ((bs - price) - nc) * 100

def call_pnl(price, k, p):
    return -p*100 if price <= k else (price - k - p)*100

def metric_card(label, value, color="#FFFFFF"):
    return f"""<div style="background:#1A1A1A;border-radius:16px;padding:16px;text-align:center">
  <div style="font-size:10px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">{label}</div>
  <div style="font-size:22px;font-weight:700;color:{color};letter-spacing:-0.5px">{value}</div>
</div>"""

def show_metrics_html(max_p, max_l, be, ror, rr, move):
    mp_color = "#00C805" if max_p and max_p > 0 else "#FFFFFF"
    ml_color = "#FF3B30"
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:8px">
      {metric_card("最大獲利", f"+${max_p:.0f}" if max_p else "∞", "#00C805")}
      {metric_card("最大虧損", f"-${max_l:.0f}", "#FF3B30")}
      {metric_card("損益平衡", f"${be:.2f}", "#FFFFFF")}
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:16px">
      {metric_card("報酬率", f"{ror:.1f}%", "#00C805" if ror > 0 else "#FF3B30")}
      {metric_card("盈虧比", f"{rr:.2f}x", "#FFFFFF")}
      {metric_card("需漲跌", move, "#FFFFFF")}
    </div>
    """, unsafe_allow_html=True)

def show_ladder(t, bs, ss, nc, ml, be, spread=0, strike=0, premium=0):
    step = get_step(premium*5) if t=="call" else get_step(spread)
    lower = strike if t=="call" else (bs if t=="bull" else ss)
    upper = strike+premium*6 if t=="call" else (ss if t=="bull" else bs)
    start = math.floor((lower-step*3)/step)*step
    end = math.ceil((upper+step*3)/step)*step
    rows = []
    p = start
    while p <= end+0.001:
        v = call_pnl(p,strike,premium) if t=="call" else spread_pnl(t,p,bs,ss,nc,ml)
        ret = v/abs(ml)*100 if ml else 0
        near_be = abs(p-be) <= step*0.55
        is_max = (t=="bull" and p>=ss) or (t=="bear" and p<=ss)
        tag = '<span class="pill pill-be">평衡</span>' if near_be else ('<span class="pill pill-max">MAX</span>' if is_max else "")
        rc = "profit" if v>1 else "loss" if v<-1 else "breakeven"
        vc = "green" if v>0 else "red" if v<0 else "yellow"
        s1 = "+" if v>=0 else ""; s2 = "+" if ret>=0 else ""
        rows.append(f'<tr class="{rc}"><td class="price">${p:.0f}{tag}</td><td class="{vc}">{s1}${v:.2f}</td><td class="{vc}">{s2}{ret:.1f}%</td></tr>')
        p = round(p+step, 3)
    st.markdown(f"""
    <div style="background:#1A1A1A;border-radius:16px;overflow:hidden;margin-top:8px">
      <div style="padding:12px 14px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #111111">
        <span style="font-size:11px;font-weight:700;color:#444444;text-transform:uppercase;letter-spacing:1px">損益對照表</span>
        <span style="font-size:10px;font-weight:700;background:#111111;color:#444444;padding:3px 10px;border-radius:100px">每 ${step}</span>
      </div>
      <table><thead><tr><th>股價</th><th>損益 / 張</th><th>報酬率</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>
    </div>""", unsafe_allow_html=True)

def show_results(t, max_p, max_l, be, nc, bs=0, ss=0, spread=0, strike=0, premium=0, ticker=""):
    ror = (max_p/max_l*100) if ml and max_p else 0
    rr = (max_p/max_l) if max_l and max_p else 0
    move = f"+{((be-bs)/bs*100):.1f}%" if t=="bull" else f"-{((bs-be)/bs*100):.1f}%" if t=="bear" else f"+{((be-strike)/strike*100):.1f}%"
    show_metrics_html(max_p, max_l, be, ror, rr, move)
    show_ladder(t, bs, ss, nc, max_l, be, spread, strike, premium)

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["計算", "比較", "AI 掃描", "說明"])

# ══════════════════════════════════════════════════════
# TAB 1
# ══════════════════════════════════════════════════════
with tab1:
    ticker = st.text_input("股票代號", placeholder="ORCL  /  DKNG  /  IBIT", key="t1").upper()
    calc_type = st.radio("策略", ["📈 Bull Call", "📉 Bear Put", "📞 單 Call"], horizontal=True, key="ct")

    if "Bull" in calc_type:
        st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">買入 Call（低行權價）</p>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        buy_s = c1.number_input("行權價", key="b_bs", min_value=0.0, format="%.2f")
        buy_p = c2.number_input("權利金", key="b_bp", min_value=0.0, format="%.2f")
        st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">賣出 Call（高行權價）</p>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        sell_s = c1.number_input("行權價", key="b_ss", min_value=0.0, format="%.2f")
        sell_p = c2.number_input("權利金", key="b_sp", min_value=0.0, format="%.2f")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("計算損益", key="cb"):
            if buy_s and buy_p and sell_s and sell_p:
                nc=buy_p-sell_p; sp=sell_s-buy_s; mp=(sp-nc)*100; ml=nc*100
                st.divider()
                show_results("bull",mp,ml,buy_s+nc,nc,bs=buy_s,ss=sell_s,spread=sp,ticker=ticker)
            else: st.error("請填入所有數值")

    elif "Bear" in calc_type:
        st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">買入 Put（高行權價）</p>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        buy_s = c1.number_input("行權價", key="p_bs", min_value=0.0, format="%.2f")
        buy_p = c2.number_input("權利金", key="p_bp", min_value=0.0, format="%.2f")
        st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">賣出 Put（低行權價）</p>', unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        sell_s = c1.number_input("行權價", key="p_ss", min_value=0.0, format="%.2f")
        sell_p = c2.number_input("權利金", key="p_sp", min_value=0.0, format="%.2f")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("計算損益", key="cp"):
            if buy_s and buy_p and sell_s and sell_p:
                nc=buy_p-sell_p; sp=buy_s-sell_s; mp=(sp-nc)*100; ml=nc*100
                st.divider()
                show_results("bear",mp,ml,buy_s-nc,nc,bs=buy_s,ss=sell_s,spread=sp,ticker=ticker)
            else: st.error("請填入所有數值")

    else:
        st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">買入 Call</p>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        strike = c1.number_input("行權價", key="c_ks", min_value=0.0, format="%.2f")
        premium = c2.number_input("權利金", key="c_pp", min_value=0.0, format="%.2f")
        target = c3.number_input("目標價", key="c_tp", min_value=0.0, format="%.2f")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("計算損益", key="cc"):
            if strike and premium:
                ml=premium*100; be=strike+premium
                mp=(target-strike-premium)*100 if target else None
                st.divider()
                show_results("call",mp or 0,ml,be,premium,strike=strike,premium=premium,ticker=ticker)
            else: st.error("請填入行權價和權利金")

# ══════════════════════════════════════════════════════
# TAB 2
# ══════════════════════════════════════════════════════
with tab2:
    st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px">基本資料</p>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    cmp_ticker = c1.text_input("股票", key="cmp_t", placeholder="ORCL").upper()
    cmp_cur = c2.number_input("現價", key="cmp_c", min_value=0.0, format="%.2f")
    cmp_target = c3.number_input("目標價", key="cmp_tg", min_value=0.0, format="%.2f")

    st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">📈 Bull Call Spread</p>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    cbbs=c1.number_input("買入價",key="cbbs",min_value=0.0,format="%.2f")
    cbbp=c2.number_input("買入金",key="cbbp",min_value=0.0,format="%.2f")
    cbss=c3.number_input("賣出價",key="cbss",min_value=0.0,format="%.2f")
    cbsp=c4.number_input("賣出金",key="cbsp",min_value=0.0,format="%.2f")

    st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">📉 Bear Put Spread</p>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    cpbs=c1.number_input("買入價",key="cpbs",min_value=0.0,format="%.2f")
    cpbp=c2.number_input("買入金",key="cpbp",min_value=0.0,format="%.2f")
    cpss=c3.number_input("賣出價",key="cpss",min_value=0.0,format="%.2f")
    cpsp=c4.number_input("賣出金",key="cpsp",min_value=0.0,format="%.2f")

    st.markdown('<p style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px">📞 單買 Call</p>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    ccks=c1.number_input("行權價",key="ccks",min_value=0.0,format="%.2f")
    ccpp=c2.number_input("權利金",key="ccpp",min_value=0.0,format="%.2f")
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("比較三種策略", key="cmp_btn"):
        results = {}
        if cbbs and cbbp and cbss and cbsp:
            nc=cbbp-cbsp; sp=cbss-cbbs; ml=nc*100; mp=(sp-nc)*100
            pat=spread_pnl("bull",cmp_target,cbbs,cbss,nc,ml)
            results["Bull Call"]={"最大獲利":f"+${mp:.0f}","最大虧損":f"-${ml:.0f}","損益平衡":f"${cbbs+nc:.2f}","目標損益":f"{'+' if pat>=0 else ''}${pat:.0f}","報酬率":f"{mp/ml*100:.1f}%","成本":f"${ml:.0f}","_ror":mp/ml*100}
        if cpbs and cpbp and cpss and cpsp:
            nc=cpbp-cpsp; sp=cpbs-cpss; ml=nc*100; mp=(sp-nc)*100
            pat=spread_pnl("bear",cmp_target,cpbs,cpss,nc,ml)
            results["Bear Put"]={"最大獲利":f"+${mp:.0f}","最大虧損":f"-${ml:.0f}","損益平衡":f"${cpbs-nc:.2f}","目標損益":f"{'+' if pat>=0 else ''}${pat:.0f}","報酬率":f"{mp/ml*100:.1f}%","成本":f"${ml:.0f}","_ror":mp/ml*100}
        if ccks and ccpp:
            ml=ccpp*100; pat=call_pnl(cmp_target,ccks,ccpp)
            results["單Call"]={"最大獲利":f"+${max(pat,0):.0f}","最大虧損":f"-${ml:.0f}","損益平衡":f"${ccks+ccpp:.2f}","目標損益":f"{'+' if pat>=0 else ''}${pat:.0f}","報酬率":f"{pat/ml*100:.1f}%","成本":f"${ml:.0f}","_ror":pat/ml*100}
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

# ══════════════════════════════════════════════════════
# TAB 3
# ══════════════════════════════════════════════════════
with tab3:
    st.markdown("""
    <div style="background:#0A1A0A;border:1px solid #00C805;border-radius:16px;padding:16px;margin-bottom:20px">
      <div style="font-size:13px;color:#00C805;font-weight:700;margin-bottom:4px">🤖 AI 智能分析</div>
      <div style="font-size:12px;color:#444444;line-height:1.5">上傳期權鏈截圖，AI 自動讀取數據並找出 Top 3 最佳組合策略</div>
    </div>
    """, unsafe_allow_html=True)

    scan_ticker = st.text_input("股票代號", placeholder="DKNG  /  ORCL  /  IBIT", key="st").upper()
    uploaded = st.file_uploader("上傳截圖", type=["png","jpg","jpeg","webp"], label_visibility="collapsed")

    if uploaded:
        img = Image.open(uploaded)
        if img.width > 1200:
            ratio = 1200/img.width
            img = img.resize((1200, int(img.height*ratio)), Image.LANCZOS)
        if img.mode != "RGB": img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode()
        kb = len(img_b64)*3//4//1024
        st.image(uploaded, use_container_width=True)
        st.markdown(f'<p style="font-size:11px;color:#00C805;margin:6px 0 16px">✓ 已壓縮至 {kb} KB</p>', unsafe_allow_html=True)

        if st.button("🤖  分析 Top 3 組合", key="scan_btn"):
            if not api_key:
                st.error("請先設定 API Key（Manage app → Settings → Secrets）")
            else:
                with st.spinner("AI 分析中..."):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        prompt = f"""分析這張期權鏈截圖（股票：{scan_ticker or '未知'}）。
讀取所有行權價和Call/Put權利金，找出最佳Top 3期權組合。
評分：報酬率最高、盈虧比合理。
只回純JSON陣列：
[{{"rank":1,"type":"bull","buyStrike":185,"buyPremium":33.0,"sellStrike":210,"sellPremium":23.0,"reason":"中文說明","maxProfit":1700,"maxLoss":1000,"breakeven":195.0,"ror":170}}]
type只能是bull/bear/call。call時sellStrike和sellPremium為null。"""
                        msg = client.messages.create(
                            model="claude-sonnet-4-6", max_tokens=1500,
                            messages=[{"role":"user","content":[
                                {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":img_b64}},
                                {"type":"text","text":prompt}
                            ]}]
                        )
                        text = msg.content[0].text.strip()
                        match = re.search(r'\[[\s\S]*\]', text)
                        if not match:
                            st.error("格式錯誤：" + text[:200])
                        else:
                            top3 = json.loads(match.group())
                            rank_icons = ["🥇","🥈","🥉"]
                            rank_labels = ["Best Pick","2nd Choice","3rd Choice"]
                            for i, r in enumerate(top3[:3]):
                                tl = "Bull Call Spread" if r["type"]=="bull" else "Bear Put Spread" if r["type"]=="bear" else "Single Call"
                                tc = "#007AFF" if r["type"]=="bull" else "#FF3B30" if r["type"]=="bear" else "#00C805"
                                sell_info = f" / ${r['sellStrike']}" if r.get('sellStrike') else ""
                                with st.expander(f"{rank_icons[i]}  {rank_labels[i]}  ·  {r['ror']}% ROI  ·  Max +${r['maxProfit']}", expanded=(i==0)):
                                    st.markdown(f"""
                                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
                                      <div>
                                        <div style="font-size:18px;font-weight:700;color:#FFFFFF;letter-spacing:-0.3px">${r['buyStrike']}{sell_info}</div>
                                        <div style="font-size:11px;color:{tc};font-weight:600;margin-top:2px">{tl}</div>
                                      </div>
                                      <div style="text-align:right">
                                        <div style="font-size:22px;font-weight:800;color:#00C805;letter-spacing:-0.5px">{r['ror']}%</div>
                                        <div style="font-size:10px;color:#444444;font-weight:600">RETURN ON RISK</div>
                                      </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    c1,c2,c3 = st.columns(3)
                                    c1.metric("最大獲利", f"+${r['maxProfit']}")
                                    c2.metric("最大虧損", f"-${r['maxLoss']}")
                                    c3.metric("損益平衡", f"${r['breakeven']}")
                                    st.markdown(f'<div style="background:#0A1A0A;border-radius:10px;padding:10px 14px;margin:10px 0;font-size:12px;color:#00C805">💡 {r["reason"]}</div>', unsafe_allow_html=True)
                                    nc = (r["buyPremium"]-r["sellPremium"]) if r.get("sellPremium") else r["buyPremium"]
                                    ml = nc*100
                                    sp = abs(r["buyStrike"]-r["sellStrike"]) if r.get("sellStrike") else 0
                                    show_ladder(r["type"],r["buyStrike"],r.get("sellStrike",0),nc,ml,r["breakeven"],sp,r["buyStrike"],r["buyPremium"])
                    except Exception as e:
                        st.error(f"分析失敗：{e}")

# ══════════════════════════════════════════════════════
# TAB 4
# ══════════════════════════════════════════════════════
with tab4:
    st.markdown("""
    <div style="color:#FFFFFF">

    <div style="margin-bottom:20px">
      <div style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">策略說明</div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;font-size:13px;color:#AAAAAA;line-height:1.6">
        <b style="color:#FFFFFF">Bull Call Spread</b> — 看漲。買低Call賣高Call，限定獲利和風險。<br><br>
        <b style="color:#FFFFFF">Bear Put Spread</b> — 看跌。買高Put賣低Put，限定獲利和風險。<br><br>
        <b style="color:#FFFFFF">單買 Call</b> — 看漲。理論上無限獲利，最多虧損全部權利金。
      </div>
    </div>

    <div style="margin-bottom:20px">
      <div style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">步距規則</div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;font-size:13px;color:#AAAAAA;line-height:1.8">
        價差 &lt; $20 → 每 $1<br>
        價差 $20–50 → 每 $5<br>
        價差 &gt; $50 → 每 $10
      </div>
    </div>

    <div>
      <div style="font-size:11px;color:#444444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">報酬率</div>
      <div style="background:#1A1A1A;border-radius:16px;padding:16px;font-size:13px;color:#AAAAAA">
        報酬率 = 最大獲利 ÷ 最大成本 × 100%
      </div>
    </div>

    </div>
    """, unsafe_allow_html=True)
