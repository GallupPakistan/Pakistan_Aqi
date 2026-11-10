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
from advisor import render_advisor
from smog import run_overview_with_smog
from theme import NAV_ICONS, SIDEBAR_SCROLL_JS, set_plotly_colors, static_css, status_card, theme_css

# ----------------------------------------------------------------------------
# Base styling
# ----------------------------------------------------------------------------
st.markdown(static_css(), unsafe_allow_html=True)   # all CSS lives in theme.py

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
    "AI Advisor": ("HEALTH ADVISOR", "Ask the Smog Advisor",
                   "Instant, localized health advice built on the dashboard's own air data"),
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
PAGES = ["Overview", "Daily Air Quality", "Hourly Profile", "Cities", "Forecasting", "AI Advisor"]
page = st.radio("Dashboard", PAGES, horizontal=True, label_visibility="collapsed", key="nav")  # top tab bar


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
        run_overview_with_smog(page_overview, dflt, dflt, hflt, cities)   # smog calculator appears right under the KPI cards
    elif page == "Daily Air Quality":
        run_page(page_daily, dflt, DEFAULT_FILES["daily"])
    elif page == "Hourly Profile":
        run_page(page_hourly, hflt, DEFAULT_FILES["hourly"])
    elif page == "Cities":
        run_page(page_cities, cities, DEFAULT_FILES["cities"], dflt)
    elif page == "AI Advisor":
        run_page(render_advisor, daily, DEFAULT_FILES["daily"], aqi_cat)
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
try:
    import streamlit.components.v1 as components
    components.html(SIDEBAR_SCROLL_JS, height=0)
except Exception:
    pass