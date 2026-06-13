import streamlit as st
import anthropic
import base64
import json
import math
from PIL import Image
import io

st.set_page_config(page_title="期權組合計算器", page_icon="📊", layout="centered")

# ── CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
.main { background: #0d1117; }
.stApp { background: #0d1117; color: #e6edf3; }
div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 700; }
.metric-green { color: #3fb950 !important; }
.metric-red { color: #f85149 !important; }
table { width: 100%; border-collapse: collapse; }
th { background: #161b22; color: #7d8590; font-size: 12px; padding: 8px 12px; text-align: left; border-bottom: 1px solid #21262d; }
td { padding: 8px 12px; border-bottom: 1px solid #1a1f27; font-size: 13px; }
tr.profit { background: rgba(63,185,80,0.05); }
tr.loss { background: rgba(248,81,73,0.05); }
tr.breakeven { background: rgba(227,179,65,0.08); }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────
def get_step(spread):
    if spread < 20: return 1
    elif spread <= 50: return 5
    else: return 10

def spread_pnl(type_, price, buy_s, sell_s, net_cost, max_l):
    spread = abs(buy_s - sell_s)
    max_p = (spread - net_cost) * 100
    if type_ == "bull":
        if price <= buy_s: return -max_l
        if price >= sell_s: return max_p
        return ((price - buy_s) - net_cost) * 100
    else:
        if price >= buy_s: return -max_l
        if price <= sell_s: return max_p
        return ((buy_s - price) - net_cost) * 100

def call_pnl(price, strike, premium):
    return -premium * 100 if price <= strike else (price - strike - premium) * 100

def show_results(type_, max_p, max_l, be, net_cost, buy_s=None, sell_s=None, spread=None, strike=None, premium=None, ticker=""):
    ror = (max_p / max_l * 100) if max_l else 0
    rr = (max_p / max_l) if max_l else 0
    if type_ == "bull":
        move = f"+{((be - buy_s) / buy_s * 100):.1f}%"
    elif type_ == "bear":
        move = f"-{((buy_s - be) / buy_s * 100):.1f}%"
    else:
        move = f"+{((be - strike) / strike * 100):.1f}%"

    label = ("Bull Call Spread" if type_ == "bull" else "Bear Put Spread" if type_ == "bear" else "單買 Call")
    if ticker:
        st.subheader(f"{ticker} · {label}")
    else:
        st.subheader(label)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("最大獲利", f"+${max_p:.0f}" if max_p else "∞")
        st.metric("報酬率", f"{ror:.1f}%")
    with col2:
        st.metric("最大虧損", f"-${max_l:.0f}")
        st.metric("盈虧比", f"{rr:.2f}x")
    with col3:
        st.metric("損益平衡", f"${be:.2f}")
        st.metric("需漲跌幅", move)

    # Ladder
    st.markdown("#### 價格損益對照表")
    if type_ == "call":
        step = get_step(premium * 5)
        lower, upper = strike, strike + premium * 6
    else:
        step = get_step(spread)
        lower = buy_s if type_ == "bull" else sell_s
        upper = sell_s if type_ == "bull" else buy_s

    start = math.floor((lower - step * 3) / step) * step
    end = math.ceil((upper + step * 3) / step) * step

    rows = []
    p = start
    while p <= end + 0.001:
        if type_ == "call":
            v = call_pnl(p, strike, premium)
        else:
            v = spread_pnl(type_, p, buy_s, sell_s, net_cost, max_l)
        ret = v / abs(max_l) * 100 if max_l else 0
        near_be = abs(p - be) <= step * 0.55
        is_max = (type_ == "bull" and p >= sell_s) or (type_ == "bear" and p <= sell_s)
        tag = " 🟡平衡" if near_be else (" 🟢最大獲利" if is_max else "")
        color = "profit" if v > 1 else "loss" if v < -1 else "breakeven"
        sign = "+" if v >= 0 else ""
        rsign = "+" if ret >= 0 else ""
        rows.append(f'<tr class="{color}"><td>${p:.0f}{tag}</td><td>{sign}${v:.2f}</td><td>{rsign}{ret:.1f}%</td></tr>')
        p = round(p + step, 3)

    table_html = f"""
    <table>
    <thead><tr><th>股價</th><th>損益/張</th><th>報酬率</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    </table>"""
    st.markdown(table_html, unsafe_allow_html=True)

# ── Sidebar / API Key ─────────────────────────────────────────────
api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
if not api_key:
    api_key = st.sidebar.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["🧮 計算", "⚖️ 比較", "🤖 AI掃描", "📖 說明"])

# ════════════════════════════════════════════════════════
# TAB 1: CALC
# ════════════════════════════════════════════════════════
with tab1:
    st.markdown("### 期權組合計算")
    ticker = st.text_input("股票代號（選填）", placeholder="ORCL、DKNG", key="calc_ticker").upper()
    calc_type = st.radio("策略類型", ["📈 Bull Call Spread", "📉 Bear Put Spread", "📞 單買 Call"], horizontal=True)

    if "Bull" in calc_type:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**買入 Call（低行權價）**")
            buy_s = st.number_input("行權價", key="b_bs", min_value=0.0, format="%.2f")
            buy_p = st.number_input("權利金", key="b_bp", min_value=0.0, format="%.2f")
        with col2:
            st.markdown("**賣出 Call（高行權價）**")
            sell_s = st.number_input("行權價", key="b_ss", min_value=0.0, format="%.2f")
            sell_p = st.number_input("權利金", key="b_sp", min_value=0.0, format="%.2f")
        if st.button("計算損益", type="primary", key="calc_bull"):
            if buy_s and buy_p and sell_s and sell_p:
                nc = buy_p - sell_p
                sp = sell_s - buy_s
                max_p = (sp - nc) * 100
                max_l = nc * 100
                be = buy_s + nc
                show_results("bull", max_p, max_l, be, nc, buy_s=buy_s, sell_s=sell_s, spread=sp, ticker=ticker)
            else:
                st.error("請填入所有數值")

    elif "Bear" in calc_type:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**買入 Put（高行權價）**")
            buy_s = st.number_input("行權價", key="p_bs", min_value=0.0, format="%.2f")
            buy_p = st.number_input("權利金", key="p_bp", min_value=0.0, format="%.2f")
        with col2:
            st.markdown("**賣出 Put（低行權價）**")
            sell_s = st.number_input("行權價", key="p_ss", min_value=0.0, format="%.2f")
            sell_p = st.number_input("權利金", key="p_sp", min_value=0.0, format="%.2f")
        if st.button("計算損益", type="primary", key="calc_bear"):
            if buy_s and buy_p and sell_s and sell_p:
                nc = buy_p - sell_p
                sp = buy_s - sell_s
                max_p = (sp - nc) * 100
                max_l = nc * 100
                be = buy_s - nc
                show_results("bear", max_p, max_l, be, nc, buy_s=buy_s, sell_s=sell_s, spread=sp, ticker=ticker)
            else:
                st.error("請填入所有數值")

    else:
        st.markdown("**買入 Call**")
        strike = st.number_input("行權價", key="c_ks", min_value=0.0, format="%.2f")
        premium = st.number_input("權利金", key="c_pp", min_value=0.0, format="%.2f")
        target = st.number_input("目標價（選填）", key="c_tp", min_value=0.0, format="%.2f")
        if st.button("計算損益", type="primary", key="calc_call"):
            if strike and premium:
                max_l = premium * 100
                be = strike + premium
                max_p = (target - strike - premium) * 100 if target else None
                show_results("call", max_p or 0, max_l, be, premium, strike=strike, premium=premium, ticker=ticker)
            else:
                st.error("請填入行權價和權利金")

# ════════════════════════════════════════════════════════
# TAB 2: COMPARE
# ════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 三種策略比較")
    col1, col2, col3 = st.columns(3)
    with col1:
        cmp_ticker = st.text_input("股票代號", key="cmp_ticker", placeholder="ORCL").upper()
    with col2:
        cmp_cur = st.number_input("現價", key="cmp_cur", min_value=0.0, format="%.2f")
    with col3:
        cmp_target = st.number_input("目標價", key="cmp_target", min_value=0.0, format="%.2f")

    st.markdown("**Bull Call Spread**")
    c1, c2, c3, c4 = st.columns(4)
    cbbs = c1.number_input("買入價", key="cbbs", min_value=0.0, format="%.2f")
    cbbp = c2.number_input("買入金", key="cbbp", min_value=0.0, format="%.2f")
    cbss = c3.number_input("賣出價", key="cbss", min_value=0.0, format="%.2f")
    cbsp = c4.number_input("賣出金", key="cbsp", min_value=0.0, format="%.2f")

    st.markdown("**Bear Put Spread**")
    c1, c2, c3, c4 = st.columns(4)
    cpbs = c1.number_input("買入價", key="cpbs", min_value=0.0, format="%.2f")
    cpbp = c2.number_input("買入金", key="cpbp", min_value=0.0, format="%.2f")
    cpss = c3.number_input("賣出價", key="cpss", min_value=0.0, format="%.2f")
    cpsp = c4.number_input("賣出金", key="cpsp", min_value=0.0, format="%.2f")

    st.markdown("**單買 Call**")
    c1, c2 = st.columns(2)
    ccks = c1.number_input("行權價", key="ccks", min_value=0.0, format="%.2f")
    ccpp = c2.number_input("權利金", key="ccpp", min_value=0.0, format="%.2f")

    if st.button("比較三種策略", type="primary"):
        results = {}
        if cbbs and cbbp and cbss and cbsp:
            nc = cbbp - cbsp; sp = cbss - cbbs; ml = nc * 100
            mp = (sp - nc) * 100
            pat = spread_pnl("bull", cmp_target, cbbs, cbss, nc, ml)
            results["Bull Call"] = {"最大獲利": f"+${mp:.0f}", "最大虧損": f"-${ml:.0f}", "損益平衡": f"${cbbs+nc:.2f}", "目標價損益": f"{'+' if pat>=0 else ''}${pat:.0f}", "報酬率": f"{mp/ml*100:.1f}%", "成本/張": f"${ml:.0f}", "_ror": mp/ml*100}
        if cpbs and cpbp and cpss and cpsp:
            nc = cpbp - cpsp; sp = cpbs - cpss; ml = nc * 100
            mp = (sp - nc) * 100
            pat = spread_pnl("bear", cmp_target, cpbs, cpss, nc, ml)
            results["Bear Put"] = {"最大獲利": f"+${mp:.0f}", "最大虧損": f"-${ml:.0f}", "損益平衡": f"${cpbs-nc:.2f}", "目標價損益": f"{'+' if pat>=0 else ''}${pat:.0f}", "報酬率": f"{mp/ml*100:.1f}%", "成本/張": f"${ml:.0f}", "_ror": mp/ml*100}
        if ccks and ccpp:
            ml = ccpp * 100
            pat = call_pnl(cmp_target, ccks, ccpp)
            mp = max(pat, 0)
            results["單Call"] = {"最大獲利": f"+${mp:.0f}", "最大虧損": f"-${ml:.0f}", "損益平衡": f"${ccks+ccpp:.2f}", "目標價損益": f"{'+' if pat>=0 else ''}${pat:.0f}", "報酬率": f"{pat/ml*100:.1f}%", "成本/張": f"${ml:.0f}", "_ror": pat/ml*100}

        if results:
            best = max(results, key=lambda k: results[k]["_ror"])
            rows_labels = ["最大獲利", "最大虧損", "損益平衡", "目標價損益", "報酬率", "成本/張"]
            cols = ["項目"] + list(results.keys())
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |"
            rows_md = [header, sep]
            for lbl in rows_labels:
                row = [lbl]
                for k in results:
                    val = results[k][lbl]
                    if lbl == "報酬率" and k == best:
                        val = f"**✅ {val}**"
                    row.append(val)
                rows_md.append("| " + " | ".join(row) + " |")
            st.markdown("\n".join(rows_md))
            st.success(f"🏆 最佳報酬率策略：{best}（{results[best]['報酬率']}）")

# ════════════════════════════════════════════════════════
# TAB 3: AI SCAN
# ════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 🤖 AI 掃描期權鏈截圖")
    scan_ticker = st.text_input("股票代號（選填）", placeholder="DKNG、ORCL", key="scan_ticker").upper()
    uploaded = st.file_uploader("上傳期權鏈截圖", type=["png", "jpg", "jpeg", "webp"])

    if uploaded:
        img = Image.open(uploaded)
        # Compress
        max_w = 1200
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode()
        kb = len(img_b64) * 3 // 4 // 1024
        st.image(uploaded, use_container_width=True)
        st.caption(f"✓ 已壓縮：約 {kb} KB")

        if st.button("🤖 AI 分析 Top 3 組合", type="primary"):
            if not api_key:
                st.error("請先在左側 Sidebar 填入 API Key")
            else:
                with st.spinner("AI 分析中，請稍候..."):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        prompt = f"""你是期權策略分析師。分析這張期權鏈截圖（股票：{scan_ticker or '未知'}）。

從截圖讀取所有可見行權價和Call/Put權利金，找出最佳Top 3期權組合策略。
評分標準：報酬率（最大獲利/最大成本）最高、盈虧比合理。

只回純JSON陣列，不含任何說明文字：
[
  {{
    "rank": 1,
    "type": "bull",
    "buyStrike": 185,
    "buyPremium": 33.0,
    "sellStrike": 210,
    "sellPremium": 23.0,
    "reason": "30字內中文說明",
    "maxProfit": 1700,
    "maxLoss": 1000,
    "breakeven": 195.0,
    "ror": 170
  }}
]
type只能是bull/bear/call。call時sellStrike和sellPremium為null。"""

                        msg = client.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=1500,
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                                    {"type": "text", "text": prompt}
                                ]
                            }]
                        )
                        text = msg.content[0].text.strip()
                        import re
                        match = re.search(r'\[[\s\S]*\]', text)
                        if not match:
                            st.error("AI回傳格式錯誤：" + text[:300])
                        else:
                            results = json.loads(match.group())
                            rank_icons = ["🥇", "🥈", "🥉"]
                            for i, r in enumerate(results[:3]):
                                type_label = "Bull Call Spread" if r["type"] == "bull" else "Bear Put Spread" if r["type"] == "bear" else "單買 Call"
                                with st.expander(f"{rank_icons[i]} {type_label} — 報酬率 {r['ror']}%　最大獲利 +${r['maxProfit']}", expanded=(i==0)):
                                    st.markdown(f"**組合：** ${r['buyStrike']}{f' / ${r[\"sellStrike\"]}' if r.get('sellStrike') else ''}")
                                    col1, col2, col3, col4 = st.columns(4)
                                    col1.metric("最大獲利", f"+${r['maxProfit']}")
                                    col2.metric("最大虧損", f"-${r['maxLoss']}")
                                    col3.metric("損益平衡", f"${r['breakeven']}")
                                    col4.metric("報酬率", f"{r['ror']}%")
                                    st.info(f"💡 {r['reason']}")

                                    # Show ladder
                                    nc = (r["buyPremium"] - r["sellPremium"]) if r.get("sellPremium") else r["buyPremium"]
                                    ml = nc * 100
                                    sp = abs(r["buyStrike"] - r["sellStrike"]) if r.get("sellStrike") else 0
                                    show_results(r["type"], r["maxProfit"], r["maxLoss"], r["breakeven"], nc,
                                                 buy_s=r["buyStrike"], sell_s=r.get("sellStrike"),
                                                 spread=sp, strike=r["buyStrike"], premium=r["buyPremium"],
                                                 ticker=scan_ticker)
                    except Exception as e:
                        st.error(f"分析失敗：{e}")

# ════════════════════════════════════════════════════════
# TAB 4: HELP
# ════════════════════════════════════════════════════════
with tab4:
    st.markdown("""
### 使用說明

**🧮 計算**
填入行權價和權利金，自動算出最大獲利/虧損、損益平衡、報酬率、對照表。

**⚖️ 比較**
同一股票同時比較 Bull Call、Bear Put、單Call 三種策略，自動標出最佳報酬率。

**🤖 AI掃描**
上傳期權鏈截圖，AI 自動找出 Top 3 最佳組合並計算損益。

---
**步距規則**
- 行權價差 < $20：每 $1
- 行權價差 $20–$50：每 $5
- 行權價差 > $50：每 $10

**報酬率 = 最大獲利 ÷ 最大成本**
""")
