"""
Pakistan Air Quality Intelligence Dashboard  -  MAIN FILE
---------------------------------------------------------
Run:   python app.py        (it launches Streamlit by itself)
Needs: pip install streamlit pandas numpy plotly statsmodels

Folder layout (all .py and .csv files in the same folder):
    app.py          <- this file: styling, sidebar, filters, page routing
    theme.py        <- AQI-driven colour theme (edit PALETTE to change colours)
    common.py       <- shared constants, helpers, chart/KPI functions
    page_daily.py   <- pakistan_air_quality_daily.csv  -> Overview, Daily Air Quality, Forecasting
    page_hourly.py  <- pakistan_aqi_hourly_profile.csv -> Hourly Profile
    page_cities.py  <- pakistan_cities.csv             -> Cities
"""
import calendar
import sys
from pathlib import Path
from urllib.parse import quote

import numpy as np
import streamlit as st


# ----------------------------------------------------------------------------
# Direct-run bootstrap: `python app.py` (or double-click) starts the dashboard.
# Inside Streamlit this block is skipped, so `streamlit run app.py` still works.
# ----------------------------------------------------------------------------
def _inside_streamlit():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__" and not _inside_streamlit():
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", str(Path(__file__).resolve()), "--server.headless=false"]
    sys.exit(stcli.main())

# Must be the first Streamlit command
st.set_page_config(page_title="Pakistan Air Quality Intelligence", layout="wide")

# Make sure sibling modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (AQI_BINS, AQI_COLORS, AQI_LABELS, ATM, DEFAULT_FILES, F, BASE, aqi_cat, find_file, load,
                    prep_daily)
from page_cities import page_cities
from page_daily import page_daily, page_forecast, page_overview
from page_hourly import page_hourly
from theme import set_plotly_colors, status_card, theme_css

# ----------------------------------------------------------------------------
# Base styling
# ----------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container{padding-top:1.5rem;padding-bottom:2rem;max-width:1450px}
.kpi{background:linear-gradient(135deg,#1f2a44,#2b3a67);border-radius:14px;padding:14px 16px;
     color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.18);margin-bottom:10px;min-height:104px}
.kpi .l{font-size:.74rem;opacity:.8;text-transform:uppercase;letter-spacing:.05em}
.kpi .v{font-size:1.55rem;font-weight:700;line-height:1.25;word-break:break-word}
.kpi .s{font-size:.74rem;opacity:.75}
.insights{background:rgba(46,134,222,.10);border-left:4px solid #2e86de;border-radius:8px;
          padding:10px 16px;margin:8px 0 18px 0}
@media (max-width:640px){.kpi .v{font-size:1.15rem}.block-container{padding-left:.8rem;padding-right:.8rem}}
</style>
""",
    unsafe_allow_html=True,
)

st.sidebar.markdown('<div class="brand"><div class="mark"></div><div><div class="b1">GALLUP PAKISTAN</div>'
                    '<div class="b2">Air Quality Analytics</div></div></div>', unsafe_allow_html=True)
side_status = st.sidebar.empty()   # coloured air-status card (filled by paint())

# ----------------------------------------------------------------------------
# Load the 3 data files
# ----------------------------------------------------------------------------
daily_raw = load("daily")
hourly = load("hourly")
cities = load("cities")
daily = prep_daily(daily_raw) if daily_raw is not None else None

DATA_SOURCE = "Add your data source and collection period here (e.g. satellite/model provider, date range)."

st.markdown(
    """
<style>
.hero{background:#0f2a4a;border-radius:14px;padding:22px 26px;margin-bottom:14px;color:#fff}
.hero .tag{font-size:.78rem;letter-spacing:.14em;opacity:.8}
.hero h1{margin:.1rem 0 .2rem 0;font-size:2rem;color:#fff;padding:0}
.hero p{margin:0;opacity:.85}
.card{background:var(--secondary-background-color);border-radius:12px;padding:14px 16px;height:100%}
.card h4{margin:0 0 6px 0}
.disc{font-size:.82rem;opacity:.85;border-top:1px solid rgba(128,128,128,.35);padding-top:10px;margin-top:26px}
.foot{font-size:.78rem;opacity:.7;text-align:center;margin-top:14px;line-height:1.6}
@media (max-width:640px){.hero h1{font-size:1.4rem}}
</style>
""",
    unsafe_allow_html=True,
)

HEALTH = {
    "Good": ("Healthy air", "Air quality is healthy. Outdoor activity is fine for everyone."),
    "Moderate": ("Acceptable air", "Air quality is acceptable. Unusually sensitive people may want to limit long outdoor exertion."),
    "Unhealthy for Sensitive": ("Unhealthy for sensitive groups", "Children, older adults and people with heart or lung conditions should limit time outdoors."),
    "Unhealthy": ("Unhealthy air", "Everyone may begin to feel effects. Limit outdoor exertion and consider a mask outdoors."),
    "Very Unhealthy": ("Very unhealthy air", "Avoid outdoor activity, keep windows closed and use an air purifier if you have one."),
    "Hazardous": ("Hazardous air", "Emergency conditions. Stay indoors and avoid all outdoor exertion."),
}


# Each tab gets its own banner: (eyebrow, title, tagline)
PAGE_HERO = {
    "Overview": ("OVERVIEW", "Pakistan Air Quality Analytics", "Gallup Pakistan Digital Analytics"),
    "Daily Air Quality": ("DAILY AIR QUALITY", "Day by Day: Pollution & Weather",
                          "Track AQI, PM2.5 and weather for every city, every day"),
    "Hourly Profile": ("HOURLY PROFILE", "Pollution Around the Clock",
                       "See which hours of the day the air is cleanest and dirtiest"),
    "Cities": ("CITIES & GEOGRAPHY", "Pakistan, City by City",
               "Where the monitored cities are and how their air compares"),
    "Forecasting": ("FORECASTING", "What the Air Will Look Like Next",
                    "Statistical projections for the coming days and weeks"),
}


def render_banner(slot, aqi, source, page_name="Overview"):
    cat = aqi_cat(aqi)
    color = "#1f9d55" if cat in ("Good", "Moderate") else AQI_COLORS.get(cat, "#999")
    head, advice = HEALTH.get(cat, ("Air quality", ""))
    scope = "forecast average" if source == "forecast" else "average for the current filters"
    tag, title, sub = PAGE_HERO.get(page_name, PAGE_HERO["Overview"])
    icon = ("<svg viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1' stroke-linecap='round' "
            "stroke-linejoin='round'>" + NAV_ICONS[PAGES.index(page_name)] + "</svg>") if page_name in PAGES else ""
    slot.markdown(f'<div class="hero"><div class="wm">{icon}</div><div class="tag">{tag}</div><h1>{title}</h1>'
                  f'<p>{sub}</p>'
                  f'<div class="status"><span class="sdot" style="background:{color}"></span><b>{head}</b>'
                  f'<span>· AQI {aqi:.0f}</span><span class="ssrc">({scope})</span></div>'
                  f'<div class="advice">{advice}</div></div>', unsafe_allow_html=True)


def render_disclaimer():
    st.markdown(
        f'<div class="disc"><b>Disclaimer.</b> The data in this dashboard is drawn from the source described below. '
        f'Values are daily and hourly aggregates of air-quality and weather readings and may include modelled '
        f'estimates, so they are not official government statistics. City-level figures describe the monitored '
        f'point, not the whole city. AQI categories follow the US AQI scale. Forecasts are statistical projections '
        f'from past patterns and do not account for sudden events. Classification and aggregation were done by '
        f'GDAP for public understanding and educational insight, and may contain errors.<br>'
        f'<b>Data source:</b> {DATA_SOURCE}</div>', unsafe_allow_html=True)


def render_footer():
    st.markdown(
        '<div class="foot">Built by <b>Asad Shahid </b>, Giki Graduate<br>'
        '© 2026 Gallup Pakistan. All rights reserved.</div>',
        unsafe_allow_html=True)


def run_page(fn, data, name, *extra):
    if data is None:
        st.warning(f"Please upload **{name}** in the sidebar (or place it next to app.py).")
    else:
        fn(data, *extra)


# ----------------------------------------------------------------------------
# Sidebar navigation + theme CSS
# ----------------------------------------------------------------------------
PAGES = ["Overview", "Daily Air Quality", "Hourly Profile", "Cities", "Forecasting"]
page = st.radio("Dashboard", PAGES, horizontal=True, label_visibility="collapsed", key="nav")  # top tab bar


def _icon(inner, stroke="#9db8ff"):
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='" + stroke +
           "' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>" + inner + "</svg>")
    return 'url("data:image/svg+xml,' + quote(svg) + '")'


NAV_ICONS = [
    "<rect x='3' y='3' width='7' height='7' rx='2'/><rect x='14' y='3' width='7' height='7' rx='2'/>"
    "<rect x='3' y='14' width='7' height='7' rx='2'/><rect x='14' y='14' width='7' height='7' rx='2'/>",
    "<rect x='3' y='5' width='18' height='16' rx='3'/><path d='M8 3v4M16 3v4M3 10h18M8 15h3M13 15h3'/>",
    "<circle cx='12' cy='12' r='9'/><path d='M12 7v5l3 2'/>",
    "<path d='M3 21h18M5 21V10l5-3v14M10 21V4l6 3v14M16 21v-8l3 1.5V21'/>",
    "<polyline points='3,17 8,11 12,14 17,7'/><polyline points='17,7 21,3' stroke-dasharray='2 2'/>"
    "<polyline points='16,3 21,3 21,8'/>",
]
BRAND_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40' fill='none'>"
             "<circle cx='20' cy='20' r='18' stroke='%236fa8ff' stroke-width='2'/>"
             "<path d='M9 15c4-3 7 3 11 0s7-3 11 0M9 21c4-3 7 3 11 0s7-3 11 0M9 27c4-3 7 3 11 0s7-3 11 0' "
             "stroke='%23dbe7ff' stroke-width='2' stroke-linecap='round'/></svg>")
nav_css = "".join(
    '.block-container div[role="radiogroup"] > label:nth-child(%d) [data-testid="stMarkdownContainer"] p::before'
    '{background-image:%s}'
    '.block-container div[role="radiogroup"] > label:nth-child(%d):has(input:checked) '
    '[data-testid="stMarkdownContainer"] p::before{background-image:%s}'
    % (i + 1, _icon(ic, "#3d4a5c"), i + 1, _icon(ic, "#ffffff"))
    for i, ic in enumerate(NAV_ICONS))

STATIC_CSS = """
<style>
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0b0a26 0%,#16143d 100%)}
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] li{color:#f1f1f7}
section[data-testid="stSidebar"] div[data-baseweb="select"] input{color:#111 !important}
.brand{display:flex;align-items:center;gap:12px;margin:0 0 12px 0}
.brand .mark{width:40px;height:40px;flex:none;background-size:contain;background-repeat:no-repeat;
  background-image:url("data:image/svg+xml,__BRAND__")}
.brand .b1{font-size:.95rem;font-weight:700;letter-spacing:.16em;color:#fff}
.brand .b2{font-size:.78rem;color:#9db8ff;letter-spacing:.04em;margin-top:2px}
.side-h{font-size:.74rem;letter-spacing:.2em;color:#9db8ff;margin:12px 0 6px 0;padding-bottom:6px;
  border-bottom:1px solid rgba(157,184,255,.25)}
section[data-testid="stSidebar"] [data-baseweb="tag"]{background:#3b82f6 !important;border-radius:999px !important;
  height:26px;margin:2px 3px 2px 0}
section[data-testid="stSidebar"] [data-baseweb="tag"] span{color:#fff !important;font-size:.8rem !important}
section[data-testid="stSidebar"] [data-baseweb="tag"] svg{fill:#fff}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:first-child{max-height:132px;overflow-y:auto}
.pf-h{font-size:.72rem;font-weight:700;letter-spacing:.14em;color:#b8c7ee;margin:16px 0 2px 0}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button,
section[data-testid="stSidebar"] button[data-testid*="pills"]{background:#fff !important;border:1px solid #fff !important;
  border-radius:999px !important;padding:2px 14px !important;min-height:34px;box-shadow:none;color:#14213d !important}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button *,
section[data-testid="stSidebar"] button[data-testid*="pills"] *{color:#14213d !important;
  -webkit-text-fill-color:#14213d !important;font-weight:500;margin:0;opacity:1 !important}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button:hover,
section[data-testid="stSidebar"] button[data-testid*="pills"]:hover{filter:brightness(.93)}
section[data-testid="stSidebar"] button[data-testid*="pillsActive"],
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[kind="pillsActive"]{background:#3b82f6 !important;border-color:#3b82f6 !important;color:#fff !important}
section[data-testid="stSidebar"] button[data-testid*="pillsActive"] *,
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[kind="pillsActive"] *{color:#fff !important;
  -webkit-text-fill-color:#fff !important}
section[data-testid="stSidebar"] div[role="radiogroup"]{gap:5px}
section[data-testid="stSidebar"] div[role="radiogroup"] > label{background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:7px 12px;margin:0;width:100%;
  transition:all .2s ease}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover{background:rgba(111,168,255,.14)}
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child{position:absolute;opacity:0;
  width:0;height:0;overflow:hidden}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){
  background:linear-gradient(90deg,rgba(76,141,255,.38),rgba(76,141,255,.06));
  border-color:rgba(120,170,255,.6);box-shadow:inset 3px 0 0 #6fa8ff}
section[data-testid="stSidebar"] div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] p{
  font-size:.98rem;letter-spacing:.01em;margin:0}
section[data-testid="stSidebar"] div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] p::before{
  content:"";display:inline-block;width:19px;height:19px;margin-right:11px;vertical-align:-4px;
  background-size:contain;background-repeat:no-repeat;opacity:.9}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p::before{
  filter:brightness(1.7);opacity:1}
.pill{display:inline-flex;align-items:center;gap:8px;margin-top:12px;background:rgba(255,255,255,.14);
  border:1px solid rgba(255,255,255,.28);border-radius:999px;padding:4px 14px;font-size:.84rem}
.pill .dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.verdict{background:rgba(128,128,128,.10);border-radius:10px;padding:14px 18px;margin:6px 0 16px 0;
  line-height:1.6}
.kgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:8px 0 20px 0}
.kc{background:linear-gradient(135deg,#1f2a44,#2b3a67);color:#fff;border-radius:14px;padding:14px 16px;
  height:120px;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;
  box-shadow:0 2px 8px rgba(0,0,0,.16)}
.kl{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;opacity:.8;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.kv{font-size:1.6rem;font-weight:700;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ks{font-size:.76rem;opacity:.8;line-height:1.3;min-height:2.6em;display:-webkit-box;
  -webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.igrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin:8px 0 24px 0}
.ic{background:#f5f8fd;border:1px solid #e1e8f4;border-top:4px solid #2e5fbf;border-radius:12px;
  padding:18px 20px;display:flex;flex-direction:column;gap:8px}
.it{font-size:1.1rem;font-weight:700;color:#0f2a4a}
.ib{font-size:.95rem;line-height:1.65;color:#2b3345}
.hero .tag{font-size:.78rem;letter-spacing:.16em;opacity:.85}
.hero h1{margin:.15rem 0 .2rem 0;font-size:2rem;padding:0}
.hero p{margin:0;opacity:.9}
.hero .status{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:16px;font-size:1.12rem}
.hero .sdot{width:14px;height:14px;border-radius:50%;box-shadow:0 0 0 3px rgba(255,255,255,.6);flex:none}
.hero .ssrc{opacity:.8;font-size:.82rem}
.hero .advice{margin-top:4px;font-size:.93rem;opacity:.95}
.sstat{background:rgba(255,255,255,.06);border-radius:10px;border-left:4px solid #888;padding:10px 12px;
  margin:16px 0 4px 0}
.sstat .sl{font-size:.66rem;letter-spacing:.22em;color:#9db8ff}
.sstat .sh{font-size:1rem;font-weight:700;color:#fff;margin-top:2px}
.sstat .sv{font-size:.8rem;color:#c9d6f5}
.hero > .wm{position:absolute !important;right:48px;top:50%;transform:translateY(-50%);width:170px;height:170px;opacity:.16;z-index:0 !important;pointer-events:none}
@media (max-width:760px){.hero > .wm{display:none}}
/* ---- top tab bar (colours come from theme.py) ---- */
.block-container div[data-testid="stRadio"] div[role="radiogroup"]{display:flex;flex-direction:row;flex-wrap:wrap;
  gap:6px;padding:6px;border-radius:14px;width:fit-content;max-width:100%}
.block-container div[role="radiogroup"] > label{border-radius:10px;padding:8px 18px;margin:0;cursor:pointer;
  transition:all .2s ease}
.block-container div[role="radiogroup"] > label > div:first-child{position:absolute;opacity:0;width:0;height:0;
  overflow:hidden}
.block-container div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] p{font-size:.98rem;
  font-weight:600;margin:0;white-space:nowrap}
.block-container div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] p::before{content:"";
  display:inline-block;width:18px;height:18px;margin-right:9px;vertical-align:-4px;background-size:contain;
  background-repeat:no-repeat}
@media (max-width:640px){.block-container div[role="radiogroup"] > label{padding:7px 12px}}
section[data-testid="stSidebar"]{height:100vh !important;height:100dvh !important}
section[data-testid="stSidebar"] > div:first-child,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{height:100vh !important;height:100dvh !important;
  max-height:100dvh;overflow-y:auto !important;overflow-x:hidden !important;box-sizing:border-box;
  overscroll-behavior:contain;scroll-behavior:smooth;scrollbar-width:thin;
  scrollbar-color:#6fa8ff rgba(255,255,255,.06);padding-bottom:90px}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.7rem}
section[data-testid="stSidebar"] *::-webkit-scrollbar{width:8px}
section[data-testid="stSidebar"] *::-webkit-scrollbar-track{background:rgba(255,255,255,.06);border-radius:8px}
section[data-testid="stSidebar"] *::-webkit-scrollbar-thumb{background:#6fa8ff;border-radius:8px}
</style>
""".replace("__BRAND__", quote(BRAND_SVG, safe="%"))
st.markdown(STATIC_CSS + "<style>" + nav_css + "</style>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar filters (write into the shared dict F from common.py)
# ---------------------------------------------------------------------------
MONTHS_ABBR = list(calendar.month_abbr)[1:]


def _pill_cb(key, all_label):
    """'All ...' pill is exclusive: picking it clears the rest, picking anything else switches it off."""
    cur = list(st.session_state.get(key) or [])
    prev = st.session_state.get(key + "_prev", [all_label])
    if not cur or (all_label in cur and all_label not in prev):
        cur = [all_label]
    elif all_label in cur and len(cur) > 1:
        cur = [c for c in cur if c != all_label]
    st.session_state[key] = cur
    st.session_state[key + "_prev"] = cur


def pill_filter(title, options, all_label, key):
    """Click-to-select pill filter. Returns the chosen options, or every option while 'All' is on."""
    st.sidebar.markdown(f'<div class="pf-h">{title}</div>', unsafe_allow_html=True)
    options = list(options)
    if key not in st.session_state:
        st.session_state[key] = [all_label]
        st.session_state[key + "_prev"] = [all_label]
    kw = dict(key=key, on_change=_pill_cb, args=(key, all_label), label_visibility="collapsed")
    if hasattr(st.sidebar, "pills"):
        sel = st.sidebar.pills(title, [all_label] + options, selection_mode="multi", format_func=str, **kw)
    else:  # older Streamlit: same behaviour with a multiselect
        sel = st.sidebar.multiselect(title, [all_label] + options, **kw)
    sel = [x for x in (sel or []) if x != all_label]
    return sel or options


def sidebar_filters(d):
    st.sidebar.markdown('<div class="side-h">FILTERS</div>', unsafe_allow_html=True)
    if d is None:
        st.sidebar.info("Daily data file not found yet.")
        return
    F["years"] = pill_filter("YEAR", sorted(int(y) for y in d.date.dt.year.unique()), "All Years", "f_years")
    provs_all = sorted(d.province.dropna().unique())
    F["provs"] = pill_filter("PROVINCE", provs_all, "All Provinces", "f_provs")
    stats = d[d.province.isin(F["provs"])].groupby("city").us_aqi_avg.mean().sort_values(ascending=False)
    opts = list(stats.index)
    st.sidebar.markdown('<div class="pf-h">CITIES (TREND CHART)</div>', unsafe_allow_html=True)
    F["trend_cities"] = st.sidebar.multiselect("Cities (for trend chart)", opts, default=opts[:5],
                                               label_visibility="collapsed",
                                               help="Cities drawn on the trend line charts. Default: 5 most polluted.")
    n = max(2, len(opts))
    F["top_n"] = st.sidebar.slider("Top N Cities (bar/heatmap charts)", 1, n, min(10, n))
    seasons_all = sorted(d.season.dropna().unique())
    F["n_seasons"] = len(seasons_all)
    F["seasons"] = pill_filter("SEASON", seasons_all, "All Seasons", "f_seasons")
    ms = pill_filter("MONTH", MONTHS_ABBR, "All Months", "f_months")
    F["months"] = [MONTHS_ABBR.index(m) + 1 for m in ms]
    F["cats"] = pill_filter("AQI CATEGORY", AQI_LABELS, "All Categories", "f_cats")


def apply_daily(d):
    import pandas as pd
    if d is None or F["years"] is None:
        return d
    m = (d.date.dt.year.isin(F["years"]) & d.province.isin(F["provs"])
         & d.date.dt.month.isin(F["months"]) & d.season.isin(F["seasons"]))
    out = d[m]
    if 0 < len(F["cats"]) < len(AQI_LABELS):
        out = out[pd.cut(out.us_aqi_avg, AQI_BINS, labels=AQI_LABELS).isin(F["cats"])]
    return out


def apply_hourly(h):
    if h is None or F["years"] is None:
        return h
    m = h.province.isin(F["provs"]) & h.month.isin(F["months"])
    if len(F["seasons"]) < F["n_seasons"]:
        m &= h.season.isin(F["seasons"])
    return h[m]


sidebar_filters(daily)
with st.sidebar.expander("Data files"):
    for _k, _v in DEFAULT_FILES.items():
        st.write((":green[found] " if find_file(_v) else ":red[missing] ") + _v)
    st.caption(f"Looking in: {BASE}")

st.sidebar.markdown(
    '<div style="font-size:.78rem;color:#9db8ff;margin-top:14px;text-align:center">'
    'Built by Asad Shahid Giki, Graduate</div>',
    unsafe_allow_html=True)

dflt = apply_daily(daily)
hflt = apply_hourly(hourly)

banner_slot = st.empty()
atm_slot = st.empty()


def filter_aqi():
    if dflt is not None and len(dflt):
        return float(np.nan_to_num(dflt.us_aqi_avg.mean(), nan=40.0))
    return 40.0


def paint(aqi, source):
    """Re-colour the entire dashboard for this AQI (theme.py holds the palette)."""
    cat = aqi_cat(aqi)
    dot = "#1f9d55" if cat in ("Good", "Moderate") else AQI_COLORS.get(cat, "#999")
    set_plotly_colors(aqi)
    atm_slot.markdown(theme_css(aqi), unsafe_allow_html=True)
    render_banner(banner_slot, aqi, source, page)
    side_status.markdown(status_card(aqi, HEALTH.get(cat, ("Air quality", ""))[0], source, dot),
                         unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------
# paint the background and the healthy / unhealthy message BEFORE the page loads, so it appears instantly
if page == "Forecasting" and "forecast_aqi" in st.session_state:
    early = (st.session_state["forecast_aqi"], "forecast")
else:
    early = (filter_aqi(), "filters")
paint(*early)

with st.spinner(f"Loading {page}..."):   # loading sign shown while a tab is being built
    if dflt is not None and dflt.empty:
        st.warning("No records match the current filters. Widen the filters in the sidebar.")
    elif page == "Overview":
        page_overview(dflt, hflt, cities)
    elif page == "Daily Air Quality":
        run_page(page_daily, dflt, DEFAULT_FILES["daily"])
    elif page == "Hourly Profile":
        run_page(page_hourly, hflt, DEFAULT_FILES["hourly"])
    elif page == "Cities":
        run_page(page_cities, cities, DEFAULT_FILES["cities"], dflt)
    else:
        st.caption("Forecasting uses the full history of the selected city, regardless of the sidebar filters.")
        run_page(page_forecast, daily, DEFAULT_FILES["daily"])

final = (ATM["aqi"], ATM["src"]) if ATM["aqi"] is not None else (filter_aqi(), "filters")
if round(final[0]) != round(early[0]) or final[1] != early[1]:
    paint(*final)
render_disclaimer()
render_footer()

# ---------------------------------------------------------------------------
# Sidebar scroll-up / scroll-down buttons
# ---------------------------------------------------------------------------
SCROLL_JS = """
<script>
(function () {
  var doc = window.parent.document;
  var win = window.parent;
  var UP = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6,15 12,9 18,15"/></svg>';
  var DOWN = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6,9 12,15 18,9"/></svg>';

  function scroller(sb) {
    var els = sb.querySelectorAll('*');
    for (var i = 0; i < els.length; i++) {
      var cs = win.getComputedStyle(els[i]);
      if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && els[i].scrollHeight > els[i].clientHeight + 4) {
        return els[i];
      }
    }
    return sb;
  }
  function make(label, svg, dir, sb) {
    var b = doc.createElement('button');
    b.type = 'button';
    b.title = label;
    b.setAttribute('aria-label', label);
    b.innerHTML = svg;
    b.style.cssText = 'width:38px;height:38px;border-radius:50%;border:1px solid rgba(157,184,255,.55);' +
      'background:rgba(20,18,58,.94);color:#cfe0ff;cursor:pointer;display:flex;align-items:center;' +
      'justify-content:center;padding:0;box-shadow:0 2px 8px rgba(0,0,0,.45)';
    b.onclick = function () { scroller(sb).scrollBy({ top: dir * 300, behavior: 'smooth' }); };
    return b;
  }
  function ensure() {
    var sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (!sb || doc.getElementById('gp-scroll-btns')) return;
    if (win.getComputedStyle(sb).position === 'static') { sb.style.position = 'relative'; }
    var box = doc.createElement('div');
    box.id = 'gp-scroll-btns';
    box.style.cssText = 'position:absolute;right:14px;bottom:18px;z-index:60;display:flex;flex-direction:column;gap:8px';
    box.appendChild(make('Scroll up', UP, -1, sb));
    box.appendChild(make('Scroll down', DOWN, 1, sb));
    sb.appendChild(box);
  }
  function fix() {
    var sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (!sb) return;
    var c = sb.querySelector('[data-testid="stSidebarContent"]') || sb.firstElementChild;
    if (c) { c.style.overflowY = 'auto'; c.style.overflowX = 'hidden'; c.style.height = '100vh'; }
  }
  function tick() { fix(); ensure(); }
  tick();
  setInterval(tick, 1000);
})();
</script>
"""
try:
    import streamlit.components.v1 as components
    components.html(SCROLL_JS, height=0)
except Exception:
    pass
