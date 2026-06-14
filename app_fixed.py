import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
    HAS_YF = True
except Exception:
    HAS_YF = False

st.set_page_config(page_title="Options Strategy Pro", page_icon="📈", layout="centered")

st.markdown(
    """
    <style>
    .metric-card{background:#111827;border:1px solid #243044;border-radius:16px;padding:14px 12px;text-align:center;margin-bottom:8px}
    .metric-title{color:#9CA3AF;font-size:13px;margin-bottom:4px}
    .metric-value{color:#F9FAFB;font-size:22px;font-weight:800}
    .hint{background:#0B1220;border-left:4px solid #3B82F6;padding:10px 12px;border-radius:10px;color:#CBD5E1}
    .leg-chip{border:1px solid #334155;border-radius:12px;padding:10px;background:#0F172A;margin-bottom:6px}
    .leg-title{font-size:12px;color:#94A3B8}.leg-value{font-size:16px;font-weight:700;color:#F8FAFC}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Options Strategy Pro")
st.caption("選擇權損益計算器：Bull Call Spread / Bear Put Spread / Long Call / Long Put")


def fmt_money(v: Optional[float], digits: int = 0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    sign = "+" if v > 0 else "" if v == 0 else "-"
    return f"{sign}${abs(v):,.{digits}f}"


def fmt_price(v: Optional[float]) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"${v:,.2f}"


def fmt_pct(v: Optional[float]) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


@st.cache_data(ttl=120)
def get_stock_price(symbol: str) -> Optional[float]:
    if not HAS_YF or not symbol:
        return None
    try:
        t = yf.Ticker(symbol)
        fi = getattr(t, "fast_info", {})
        price = fi.get("lastPrice") or fi.get("last_price")
        if price:
            return round(float(price), 2)
        hist = t.history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        return None
    return None


@st.cache_data(ttl=300)
def get_expiries(symbol: str) -> List[str]:
    if not HAS_YF or not symbol:
        return []
    try:
        return list(yf.Ticker(symbol).options)
    except Exception:
        return []


@st.cache_data(ttl=120)
def get_chain(symbol: str, expiry: str) -> Tuple[Optional[float], pd.DataFrame]:
    if not HAS_YF or not symbol or not expiry:
        return None, pd.DataFrame()
    try:
        t = yf.Ticker(symbol)
        opt = t.option_chain(expiry)
        price = get_stock_price(symbol)
        calls = opt.calls[["strike", "bid", "ask", "lastPrice", "impliedVolatility"]].rename(
            columns={"bid": "callBid", "ask": "callAsk", "lastPrice": "callLast", "impliedVolatility": "callIV"}
        )
        puts = opt.puts[["strike", "bid", "ask", "lastPrice", "impliedVolatility"]].rename(
            columns={"bid": "putBid", "ask": "putAsk", "lastPrice": "putLast", "impliedVolatility": "putIV"}
        )
        df = calls.merge(puts, on="strike", how="outer").sort_values("strike").reset_index(drop=True)
        return price, df
    except Exception:
        return None, pd.DataFrame()


def pnl_at_price(legs: Dict[str, Dict[str, float]], stock_price: float, contracts: int = 1) -> float:
    multiplier = 100 * contracts
    pnl = 0.0
    if "buyCall" in legs:
        leg = legs["buyCall"]
        pnl += (max(stock_price - leg["strike"], 0) - leg["premium"]) * multiplier
    if "sellCall" in legs:
        leg = legs["sellCall"]
        pnl += (leg["premium"] - max(stock_price - leg["strike"], 0)) * multiplier
    if "buyPut" in legs:
        leg = legs["buyPut"]
        pnl += (max(leg["strike"] - stock_price, 0) - leg["premium"]) * multiplier
    if "sellPut" in legs:
        leg = legs["sellPut"]
        pnl += (leg["premium"] - max(leg["strike"] - stock_price, 0)) * multiplier
    return round(pnl, 2)


def analyze_strategy(strategy: str, legs: Dict[str, Dict[str, float]], contracts: int = 1) -> Dict[str, Optional[float]]:
    m = 100 * contracts
    if strategy == "bull":
        buy = legs["buyCall"]
        sell = legs["sellCall"]
        width = sell["strike"] - buy["strike"]
        net_debit = buy["premium"] - sell["premium"]
        return {
            "net_cost": net_debit * m,
            "max_profit": max((width - net_debit) * m, 0),
            "max_loss": max(net_debit * m, 0),
            "breakeven": buy["strike"] + net_debit,
            "unlimited": False,
        }
    if strategy == "bear":
        buy = legs["buyPut"]
        sell = legs["sellPut"]
        width = buy["strike"] - sell["strike"]
        net_debit = buy["premium"] - sell["premium"]
        return {
            "net_cost": net_debit * m,
            "max_profit": max((width - net_debit) * m, 0),
            "max_loss": max(net_debit * m, 0),
            "breakeven": buy["strike"] - net_debit,
            "unlimited": False,
        }
    if strategy == "call":
        leg = legs["buyCall"]
        return {
            "net_cost": leg["premium"] * m,
            "max_profit": None,
            "max_loss": leg["premium"] * m,
            "breakeven": leg["strike"] + leg["premium"],
            "unlimited": True,
        }
    if strategy == "put":
        leg = legs["buyPut"]
        return {
            "net_cost": leg["premium"] * m,
            "max_profit": max((leg["strike"] - leg["premium"]) * m, 0),
            "max_loss": leg["premium"] * m,
            "breakeven": leg["strike"] - leg["premium"],
            "unlimited": False,
        }
    return {}


def build_pnl_table(
    legs: Dict[str, Dict[str, float]],
    start_price: float,
    end_price: float,
    step: float,
    max_loss: float,
    contracts: int = 1,
) -> pd.DataFrame:
    if step <= 0:
        step = 1
    prices = []
    p = start_price
    while p <= end_price + 1e-9:
        prices.append(round(p, 2))
        p += step
    rows = []
    base = abs(max_loss) if max_loss else None
    for price in prices:
        pnl = pnl_at_price(legs, price, contracts)
        rows.append(
            {
                "股價": price,
                "損益金額": pnl,
                "損益%": (pnl / base * 100) if base else None,
            }
        )
    return pd.DataFrame(rows)


def make_svg_chart(strategy: str, legs: Dict[str, Dict[str, float]], current_price: Optional[float], analysis: Dict[str, Optional[float]], contracts: int = 1) -> str:
    strikes = [v["strike"] for v in legs.values()]
    be = analysis.get("breakeven")
    center_points = strikes + ([current_price] if current_price else []) + ([be] if be else [])
    center = current_price or sum(strikes) / len(strikes)
    low_base = min(center_points) if center_points else center * 0.8
    high_base = max(center_points) if center_points else center * 1.2
    span = max(high_base - low_base, center * 0.25, 5)
    lo = max(0.01, low_base - span * 0.55)
    hi = high_base + span * 0.55

    pts = [lo + (hi - lo) * i / 220 for i in range(221)]
    pnls = [pnl_at_price(legs, p, contracts) for p in pts]
    min_v = min(min(pnls), 0)
    max_v = max(max(pnls), 0)
    pad = max((max_v - min_v) * 0.18, 50)
    v_top = max_v + pad
    v_bot = min_v - pad

    W, H = 720, 390
    left, right, top, bottom = 52, 18, 28, 52
    plot_w, plot_h = W - left - right, H - top - bottom

    def x(price: float) -> float:
        return left + (price - lo) / (hi - lo) * plot_w

    def y(val: float) -> float:
        return top + (v_top - val) / (v_top - v_bot) * plot_h

    zero_y = y(0)
    path = " ".join(f"{'M' if i == 0 else 'L'}{x(pts[i]):.1f},{y(pnls[i]):.1f}" for i in range(len(pts)))
    fill = f"{path} L{x(hi):.1f},{zero_y:.1f} L{x(lo):.1f},{zero_y:.1f} Z"

    svg = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    svg.append('<rect width="100%" height="100%" rx="16" fill="#0B1220"/>')
    svg.append(f'<line x1="{left}" x2="{W-right}" y1="{zero_y:.1f}" y2="{zero_y:.1f}" stroke="#64748B" stroke-dasharray="6 5" opacity="0.75"/>')
    svg.append(f'<path d="{fill}" fill="#22C55E" opacity="0.12"/>')
    svg.append(f'<path d="{path}" fill="none" stroke="#38BDF8" stroke-width="3"/>')

    for i in range(6):
        px = lo + (hi - lo) * i / 5
        xx = x(px)
        svg.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{top}" y2="{H-bottom}" stroke="#1E293B"/>')
        svg.append(f'<text x="{xx:.1f}" y="{H-22}" fill="#CBD5E1" font-size="13" text-anchor="middle">${px:.0f}</text>')

    for sk in sorted(set(strikes)):
        if lo <= sk <= hi:
            xx = x(sk)
            svg.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{top}" y2="{H-bottom}" stroke="#F59E0B" stroke-width="1.8" stroke-dasharray="7 5"/>')
            svg.append(f'<text x="{xx:.1f}" y="{top+18}" fill="#FBBF24" font-size="13" text-anchor="middle">Strike ${sk:g}</text>')

    if be and lo <= be <= hi:
        xx = x(be)
        svg.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{top}" y2="{H-bottom}" stroke="#A78BFA" stroke-width="2.2" stroke-dasharray="4 5"/>')
        svg.append(f'<text x="{xx:.1f}" y="{top+38}" fill="#C4B5FD" font-size="13" text-anchor="middle">損平 ${be:.2f}</text>')

    if current_price and lo <= current_price <= hi:
        xx = x(current_price)
        svg.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{top}" y2="{H-bottom}" stroke="#F43F5E" stroke-width="2.2" stroke-dasharray="8 5"/>')
        svg.append(f'<text x="{xx:.1f}" y="{H-38}" fill="#FDA4AF" font-size="13" text-anchor="middle">現價 ${current_price:.2f}</text>')

    svg.append(f'<text x="{left}" y="22" fill="#CBD5E1" font-size="14">到期損益圖</text>')
    svg.append(f'<text x="{W-right}" y="22" fill="#CBD5E1" font-size="14" text-anchor="end">虛線：現價 / Strike / 損益平衡</text>')
    svg.append(f'<text x="{left}" y="{zero_y-7:.1f}" fill="#94A3B8" font-size="12">$0</text>')
    svg.append('</svg>')
    return "".join(svg)


def show_metrics(analysis: Dict[str, Optional[float]]) -> None:
    cols = st.columns(4)
    vals = [
        ("最大獲利", "無限 ∞" if analysis.get("unlimited") else fmt_money(analysis.get("max_profit"))),
        ("最大虧損", fmt_money(-abs(analysis.get("max_loss") or 0))),
        ("損益平衡", fmt_price(analysis.get("breakeven"))),
        ("成本 / Debit", fmt_money(analysis.get("net_cost"))),
    ]
    for col, (title, value) in zip(cols, vals):
        col.markdown(f'<div class="metric-card"><div class="metric-title">{title}</div><div class="metric-value">{value}</div></div>', unsafe_allow_html=True)


STRATEGIES = {
    "看漲價差 Bull Call Spread": ("bull", ["buyCall", "sellCall"]),
    "看跌價差 Bear Put Spread": ("bear", ["buyPut", "sellPut"]),
    "單買 Call": ("call", ["buyCall"]),
    "單買 Put": ("put", ["buyPut"]),
}

LEG_LABEL = {
    "buyCall": "買入 Call（用 Ask）",
    "sellCall": "賣出 Call（用 Bid）",
    "buyPut": "買入 Put（用 Ask）",
    "sellPut": "賣出 Put（用 Bid）",
}

PRICE_COL = {
    "buyCall": "callAsk",
    "sellCall": "callBid",
    "buyPut": "putAsk",
    "sellPut": "putBid",
}


def reset_legs():
    st.session_state["legs"] = {}


if "legs" not in st.session_state:
    st.session_state["legs"] = {}

symbol_col, exp_col = st.columns([1.2, 1.8])
symbol = symbol_col.text_input("股票代號", value=st.session_state.get("last_symbol", "")).upper().strip()
if symbol:
    st.session_state["last_symbol"] = symbol

expiries = get_expiries(symbol) if symbol else []
expiry = exp_col.selectbox("到期日", expiries if expiries else ["—"], disabled=not bool(expiries))

if not HAS_YF:
    st.error("缺少 yfinance，請確認 requirements.txt 有 yfinance。")

if symbol and expiry != "—":
    current_price, chain = get_chain(symbol, expiry)
    if chain.empty:
        st.warning("抓不到期權鏈，可能是代號錯誤、YFinance 暫時限制，或該到期日沒有資料。")
    else:
        st.markdown(f"<div class='hint'>目前股價：<b>{fmt_price(current_price)}</b>　到期日：<b>{expiry}</b></div>", unsafe_allow_html=True)

        strategy_name = st.selectbox("策略", list(STRATEGIES.keys()), on_change=reset_legs)
        strategy, needed_legs = STRATEGIES[strategy_name]
        contracts = st.number_input("合約張數", min_value=1, max_value=100, value=1, step=1)

        st.subheader("已選擇")
        chip_cols = st.columns(len(needed_legs))
        for col, leg_key in zip(chip_cols, needed_legs):
            leg = st.session_state["legs"].get(leg_key)
            value = f"${leg['strike']:g} @ ${leg['premium']:.2f}" if leg else "尚未選擇"
            col.markdown(f'<div class="leg-chip"><div class="leg-title">{LEG_LABEL[leg_key]}</div><div class="leg-value">{value}</div></div>', unsafe_allow_html=True)

        all_done = all(k in st.session_state["legs"] for k in needed_legs)
        next_leg = next((k for k in needed_legs if k not in st.session_state["legs"]), None)

        with st.expander("選擇權鏈 / 點選價格", expanded=not all_done):
            if next_leg:
                st.info(f"請選：{LEG_LABEL[next_leg]}")
                price_col = PRICE_COL[next_leg]
                pick_df = chain[["strike", "callBid", "callAsk", "putBid", "putAsk"]].copy()
                pick_df = pick_df[pick_df[price_col].fillna(0) > 0]
                if current_price:
                    pick_df["距現價%"] = ((pick_df["strike"] - current_price) / current_price * 100).round(1)
                    pick_df = pick_df.sort_values(by="距現價%", key=lambda s: s.abs()).head(40).sort_values("strike")
                pick_df = pick_df.reset_index(drop=True)
                if pick_df.empty:
                    st.warning("這一腿沒有可用 Bid/Ask。")
                else:
                    choice = st.selectbox(
                        "行權價 / 權利金",
                        range(len(pick_df)),
                        format_func=lambda i: f"Strike ${pick_df.loc[i, 'strike']:g} · {LEG_LABEL[next_leg]} ${pick_df.loc[i, price_col]:.2f}",
                    )
                    st.dataframe(
                        pick_df.rename(columns={
                            "strike": "行權價", "callBid": "Call Bid", "callAsk": "Call Ask", "putBid": "Put Bid", "putAsk": "Put Ask"
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )
                    if st.button(f"確認加入：{LEG_LABEL[next_leg]}", type="primary"):
                        row = pick_df.loc[choice]
                        st.session_state["legs"][next_leg] = {"strike": float(row["strike"]), "premium": float(row[price_col])}
                        st.rerun()
            else:
                st.success("價格表已收起。下面顯示損益表；需要重選可按下方按鈕。")

        if st.button("重新選擇", use_container_width=True):
            reset_legs()
            st.rerun()

        if all_done:
            legs = {k: st.session_state["legs"][k] for k in needed_legs}
            analysis = analyze_strategy(strategy, legs, contracts)
            st.divider()
            st.subheader("結果")
            show_metrics(analysis)

            if strategy == "bull" and analysis.get("max_profit") is not None:
                st.success("Bull Call Spread 已固定獲利上限：股價高於賣出 Call 行權價後，損益線會變成水平。")

            st.markdown(make_svg_chart(strategy, legs, current_price, analysis, contracts), unsafe_allow_html=True)

            st.subheader("損益表")
            default_low = math.floor(min([v["strike"] for v in legs.values()] + ([current_price] if current_price else [])) * 0.85)
            default_high = math.ceil(max([v["strike"] for v in legs.values()] + ([current_price] if current_price else [])) * 1.25)
            p1, p2, p3 = st.columns(3)
            start_price = p1.number_input("起始股價", value=float(max(default_low, 0)), step=1.0)
            end_price = p2.number_input("結束股價", value=float(default_high), step=1.0)
            step = p3.number_input("間距", value=1.0, min_value=0.5, step=0.5)
            pnl_df = build_pnl_table(legs, start_price, end_price, step, analysis.get("max_loss") or 0, contracts)
            display_df = pnl_df.copy()
            display_df["股價"] = display_df["股價"].map(lambda x: f"${x:g}")
            display_df["損益金額"] = display_df["損益金額"].map(lambda x: fmt_money(x))
            display_df["損益%"] = display_df["損益%"].map(lambda x: fmt_pct(x))
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            csv = pnl_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("下載損益表 CSV", csv, file_name=f"{symbol}_{strategy}_pnl.csv", mime="text/csv")

else:
    st.info("輸入股票代號後，選擇到期日即可開始。")

st.divider()
st.caption("提醒：本工具只做數學損益試算，不是投資建議。Bid/Ask 可能延遲或不成交，實際成交請以券商為準。")
