"""
common.py - shared constants, state and helper functions used by every page module.
Change things here when they affect ALL pages (colours, AQI bands, chart style, KPI cards...).
"""
import html
import io
import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
DEFAULT_FILES = {
    "daily": "pakistan_air_quality_daily.csv",
    "hourly": "pakistan_aqi_hourly_profile.csv",
    "cities": "pakistan_cities.csv",
}

AQI_BINS = [-1, 50, 100, 150, 200, 300, 10000]
AQI_LABELS = ["Good", "Moderate", "Unhealthy for Sensitive Groups", "Unhealthy", "Very Unhealthy", "Hazardous"]
AQI_COLORS = {"Good": "#00e400", "Moderate": "#e6c800", "Unhealthy for Sensitive Groups": "#ff7e00",
              "Unhealthy": "#ff0000", "Very Unhealthy": "#8f3f97", "Hazardous": "#7e0023"}
WHO_PM25_24H = 15     # WHO 2021 24-hour guideline (ug/m3): compare single DAYS with this
WHO_PM25_ANNUAL = 5   # WHO 2021 annual guideline (ug/m3): compare long-term AVERAGES with this
AQI_SCALE_MAX = 500   # the US AQI scale officially ends at 500; higher values are "beyond the index"

# Seasons in calendar order (used for charts and filters instead of alphabetical order)
SEASON_ORDER = ["Spring (Feb-Apr)", "Summer (May-Jun)", "Monsoon (Jul-Sep)", "Pre-Smog (Oct)",
                "Smog Season (Nov-Jan)"]


def season_sort(values):
    """Sort season names in calendar order; unknown names go last, alphabetically."""
    vals = list(dict.fromkeys(values))
    return sorted(vals, key=lambda v: (SEASON_ORDER.index(v) if v in SEASON_ORDER else 99, str(v)))

# Shared mutable state (always mutate in place, never reassign, so every module sees changes)
# F   : current sidebar filter selections (filled by app.py)
# ATM : AQI value that drives the background / banner (a page may overwrite it, e.g. forecast)
F = dict(years=None, provs=[], seasons=[], n_seasons=0, months=list(range(1, 13)), cats=list(AQI_LABELS),
         trend_cities=[], top_n=10)
ATM = {"aqi": None, "src": "filters"}


def reset_atm():
    """Called at the start of every run so a forecast value never leaks onto other pages."""
    ATM["aqi"], ATM["src"] = None, "filters"

# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent


@st.cache_data(show_spinner=False)
def read_csv_bytes(b: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(b))


def find_file(name):
    for folder in [BASE, BASE / "data", Path.cwd(), Path.cwd() / "data"]:
        if folder.exists():
            for p in folder.glob("*.csv"):
                if p.name.lower() == name.lower():
                    return p
    return None


@st.cache_data(show_spinner="Loading data...")
def read_csv_path(path, mtime):
    return pd.read_csv(path)


def load(key):
    p = find_file(DEFAULT_FILES[key])
    return read_csv_path(str(p), p.stat().st_mtime) if p else None


def prep_daily(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values(["city", "date"])
    return df


# ----------------------------------------------------------------------------
# Chart / UI helpers
# ----------------------------------------------------------------------------
PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def _legend_count(fig):
    n = 0
    for t in fig.data:
        if t.type == "pie":
            n += len(t.labels) if t.labels is not None else 0
        elif getattr(t, "showlegend", None) is not False and getattr(t, "name", None):
            n += 1
    return n


def show(fig, h=380, legend="auto"):
    """Render a chart without overlaps.
    legend = auto | top | topright | right | bottom | off
    """
    n = _legend_count(fig)
    if legend == "auto":
        legend = "off" if n == 0 else ("top" if n <= 4 else "right")
    top, bottom = 60, 10
    if legend == "off" or n == 0:
        fig.update_layout(showlegend=False)
    elif legend in ("top", "topright"):
        right = legend == "topright"
        fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.0,
                                                       xanchor="right" if right else "left",
                                                       x=1 if right else 0, title_text=""))
        top = 92 if n <= 2 else (112 if n <= 4 else 135)
    elif legend == "bottom":
        fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.02,
                                                       xanchor="center", x=0.5, title_text="",
                                                       font=dict(size=11)))
        bottom = 90
    else:
        fig.update_layout(showlegend=True, legend=dict(orientation="v", yanchor="middle", y=0.5,
                                                       xanchor="left", x=1.0, font=dict(size=11)))
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=top, b=bottom),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    title = fig.layout.title.text
    if title:
        fig.update_layout(title=dict(text=title, x=0, xanchor="left", y=1 - 36 / h, yanchor="top",
                                     font=dict(size=15)))
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    try:
        st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)


def table(df, hide_index=False):
    """st.dataframe that works on both new (width=) and old (use_container_width=) Streamlit."""
    try:
        st.dataframe(df, width="stretch", hide_index=hide_index)
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=hide_index)


def download_csv(df, filename, label):
    """Download button for a table (keeps working on older Streamlit versions)."""
    st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=filename, mime="text/csv")


def fmt_aqi(v):
    """AQI as text; values above the 500 scale top are flagged instead of shown as if on-scale."""
    return f"{v:.0f}" if v <= AQI_SCALE_MAX else f"{v:.0f}*"


def kpis(items):
    e = lambda x: html.escape(str(x))   # data values may contain < or > (e.g. "Stagnant (<5 km/h)")
    cells = "".join(f'<div class="kc"><div class="kl">{e(l)}</div><div class="kv">{e(v)}</div><div class="ks">{e(sub)}</div></div>'
                    for l, v, sub in items)
    st.markdown(f'<div class="kgrid">{cells}</div>', unsafe_allow_html=True)


def insights(lines):
    lines = [l for l in lines if l]
    if lines:
        items = ""
        for l in lines:
            html_line = re.sub(r"[*][*](.+?)[*][*]", lambda m: "<b>" + m.group(1) + "</b>", html.escape(l, quote=False))
            items += "<li>" + html_line + "</li>"
        st.markdown('<div class="insights"><div style="font-weight:600;font-size:1.02rem">Key insights</div>'
                    '<ul style="margin:8px 0 2px 0;padding-left:20px;line-height:1.75">' + items + "</ul></div>",
                    unsafe_allow_html=True)


def explain(text):
    """Plain-language note placed directly under a chart."""
    html_line = re.sub(r"[*][*](.+?)[*][*]", lambda m: "<b>" + m.group(1) + "</b>", html.escape(text, quote=False))
    st.markdown('<div class="insights" style="margin:0 0 18px 0;font-size:.9rem;line-height:1.55">'
                '<span style="font-weight:600">How to read this chart: </span>' + html_line + "</div>",
                unsafe_allow_html=True)


def need(df, cols, name):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"`{name}` is missing required columns: {missing}")
        st.stop()


def aqi_cat(v):
    if pd.isna(v):
        return "n/a"
    return AQI_LABELS[int(np.digitize(v, AQI_BINS[1:-1], right=True))]


def hr12(h):
    h = int(h) % 24
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


def same_window(df):
    """Rows from 1 Jan to the last date's day-of-year in every year, so partial years compare fairly.
    Returns (rows, label) e.g. label '1 Jan to 20 Oct'."""
    last = df.date.max()
    m = (df.date.dt.month < last.month) | ((df.date.dt.month == last.month) & (df.date.dt.day <= last.day))
    return df[m], f"1 Jan to {last.day} {last:%b}"


WHO_24H = {"pm2_5_avg": ("PM2.5", 15), "pm10_avg": ("PM10", 45), "no2_avg": ("NO₂", 25), "so2_avg": ("SO₂", 40),
           "co_avg": ("CO", 4000), "ozone_avg": ("Ozone", 100)}   # WHO 2021 short-term guidelines, µg/m³


def haversine(lat1, lon1, lat2, lon2):
    r = 6371
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))
