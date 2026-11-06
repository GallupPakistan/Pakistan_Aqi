"""
theme.py - the whole dashboard changes mood with the air quality.

    Good air          -> fresh green, clear bright sky
    Moderate (to 100) -> still green, with a light haze building
    Unhealthy (sens.) -> turns warm light grey, visible smog (from ~115)
    Unhealthy         -> mid grey, thick drifting smog
    Very unhealthy    -> dark charcoal, heavy smog
    Hazardous         -> near-black, smoke everywhere

Edit PALETTE to change any level. Colours blend smoothly between the anchor AQI values.
Keys: accent / mid / dark / tint = UI colours;  sky_top / sky_bot = page background;
      smog = colour of the drifting smoke;  haze = smoke strength behind the page;
      veil = smoke strength drifting OVER the page;  sun = sun glow;  card = page-card opacity
"""
from urllib.parse import quote

import numpy as np
import plotly.io as pio

PALETTE = [
    dict(aqi=0,   accent=(34, 166, 92),   mid=(22, 120, 76),   dark=(8, 56, 40),   tint=(232, 247, 238),
         sky_top=(118, 200, 150), sky_bot=(226, 245, 232), smog=(255, 255, 255), haze=0.30, veil=0.00, sun=0.95, card=0.95),
    dict(aqi=50,  accent=(46, 160, 96),   mid=(30, 116, 78),   dark=(12, 56, 42),  tint=(232, 246, 236),
         sky_top=(132, 200, 158), sky_bot=(228, 244, 234), smog=(240, 246, 240), haze=0.32, veil=0.01, sun=0.85, card=0.95),
    dict(aqi=100, accent=(84, 150, 108),  mid=(58, 108, 84),   dark=(26, 56, 46),  tint=(234, 243, 237),
         sky_top=(152, 190, 168), sky_bot=(226, 238, 230), smog=(214, 224, 216), haze=0.40, veil=0.03, sun=0.60, card=0.94),
    dict(aqi=115, accent=(150, 146, 138), mid=(104, 100, 95),  dark=(48, 46, 44),  tint=(241, 240, 237),
         sky_top=(172, 170, 164), sky_bot=(226, 224, 219), smog=(196, 193, 186), haze=0.50, veil=0.10, sun=0.35, card=0.92),
    dict(aqi=150, accent=(122, 122, 128), mid=(82, 82, 88),    dark=(36, 36, 42),  tint=(236, 236, 239),
         sky_top=(176, 176, 182), sky_bot=(226, 226, 230), smog=(190, 190, 194), haze=0.50, veil=0.10, sun=0.12, card=0.93),
    dict(aqi=200, accent=(98, 98, 108),   mid=(62, 62, 71),    dark=(26, 26, 33),  tint=(230, 230, 235),
         sky_top=(166, 166, 174), sky_bot=(218, 218, 224), smog=(176, 176, 182), haze=0.55, veil=0.12, sun=0.00, card=0.93),
    dict(aqi=300, accent=(72, 68, 72),    mid=(44, 42, 46),    dark=(18, 17, 19),  tint=(224, 222, 224),
         sky_top=(156, 154, 160), sky_bot=(210, 208, 214), smog=(160, 158, 164), haze=0.60, veil=0.14, sun=0.00, card=0.93),
]
_AN = [p["aqi"] for p in PALETTE]


def _ip(key, aqi):
    v = float(np.clip(aqi, 0, 300))
    cols = [p[key] for p in PALETTE]
    if isinstance(cols[0], tuple):
        return tuple(float(np.interp(v, _AN, [c[k] for c in cols])) for k in range(3))
    return float(np.interp(v, _AN, cols))


def _mix(c, w, t=(255, 255, 255)):
    return tuple(a * (1 - w) + b * w for a, b in zip(c, t))


def _rgb(c):
    return ",".join(str(int(round(x))) for x in c)


def colors(aqi):
    accent = _ip("accent", aqi)
    mid = _ip("mid", aqi)
    return dict(
        accent=accent, mid=mid, dark=_ip("dark", aqi), tint=_ip("tint", aqi),
        strong=_mix(accent, 0.22, (0, 0, 0)),   # active pills / buttons (white text stays readable)
        soft=_mix(accent, 0.58),                # light text & lines on the dark sidebar
        side2=_mix(mid, 0.35, (0, 0, 0)),       # sidebar gradient end
        sky_top=_ip("sky_top", aqi), sky_bot=_ip("sky_bot", aqi), smog=_ip("smog", aqi),
    )


def set_plotly_colors(aqi):
    """Plotly Express charts: first series follows the theme, the rest stay clearly distinguishable."""
    c = colors(aqi)
    hexc = lambda t: "#%02x%02x%02x" % tuple(int(round(x)) for x in t)
    pio.templates["plotly"].layout.colorway = [
        hexc(c["strong"]), "#2a78d6", "#eb6834", "#0f766e", "#7c3aed", "#be185d", "#4d7c0f", "#a16207",
        "#475569", "#0ea5e9",
    ]


def status_card(aqi, head, source, dot="#999"):
    """Coloured air-status card at the top of the sidebar (dot = official AQI colour)."""
    c = colors(aqi)
    scope = "forecast" if source == "forecast" else "current filters"
    return (f'<div class="sstat" style="border-left-color:{dot};'
            f'background:linear-gradient(90deg,rgba({_rgb(c["accent"])},.40),rgba({_rgb(c["accent"])},.06))">'
            f'<div class="sl">AIR RIGHT NOW</div>'
            f'<div class="sh"><span style="display:inline-block;width:11px;height:11px;border-radius:50%;'
            f'background:{dot};margin-right:8px;box-shadow:0 0 0 2px rgba(0,0,0,.15)"></span>{head}</div>'
            f'<div class="sv">AQI {aqi:.0f} · {scope}</div></div>')


def theme_css(aqi):
    c = colors(aqi)
    sun, haze, veil, card = _ip("sun", aqi), _ip("haze", aqi), _ip("veil", aqi), _ip("card", aqi)
    brand = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40' fill='none'>"
             "<circle cx='20' cy='20' r='18' stroke='rgb(%s)' stroke-width='2'/>"
             "<path d='M9 15c4-3 7 3 11 0s7-3 11 0M9 21c4-3 7 3 11 0s7-3 11 0M9 27c4-3 7 3 11 0s7-3 11 0' "
             "stroke='rgb(%s)' stroke-width='2' stroke-linecap='round'/></svg>") % (_rgb(c["strong"]), _rgb(c["mid"]))
    css = """
<style>
/* ---------- page: sky + smog behind the content ---------- */
.stApp{background:
  radial-gradient(circle at 86% 9%, rgba(255,250,215,__S__) 0, rgba(255,244,190,__S6__) 4%, rgba(255,240,170,__S3__) 12%, rgba(255,240,170,0) 28%),
  linear-gradient(180deg, rgb(__SKYT__) 0%, rgb(__SKYB__) 100%) fixed !important}
.stApp::before{content:"";position:fixed;inset:-15%;z-index:0;pointer-events:none;
  background:
   radial-gradient(38% 26% at 8% 20%, rgba(__SM__,__H__) 0%, rgba(__SM__,0) 70%),
   radial-gradient(46% 30% at 88% 34%, rgba(__SM__,__H8__) 0%, rgba(__SM__,0) 72%),
   radial-gradient(58% 32% at 38% 82%, rgba(__SM__,__H__) 0%, rgba(__SM__,0) 70%),
   radial-gradient(34% 22% at 96% 90%, rgba(__SM__,__H8__) 0%, rgba(__SM__,0) 70%),
   radial-gradient(50% 24% at 55% 8%, rgba(__SM__,__H6__) 0%, rgba(__SM__,0) 70%);
  animation:smogA 42s ease-in-out infinite alternate}
/* smoke drifting OVER the page (stronger as air gets worse) */
.stApp::after{content:"";position:fixed;inset:-15%;z-index:3;pointer-events:none;
  background:
   radial-gradient(42% 24% at 18% 30%, rgba(__SM__,__V__) 0%, rgba(__SM__,0) 70%),
   radial-gradient(50% 28% at 82% 62%, rgba(__SM__,__V__) 0%, rgba(__SM__,0) 72%),
   radial-gradient(60% 26% at 40% 92%, rgba(__SM__,__V__) 0%, rgba(__SM__,0) 70%),
   radial-gradient(36% 20% at 70% 12%, rgba(__SM__,__V__) 0%, rgba(__SM__,0) 70%);
  animation:smogB 55s ease-in-out infinite alternate}
@keyframes smogA{0%{transform:translate3d(-6%,0,0) scale(1.05)}100%{transform:translate3d(6%,3%,0) scale(1.22)}}
@keyframes smogB{0%{transform:translate3d(5%,-2%,0) scale(1.10)}100%{transform:translate3d(-7%,3%,0) scale(1.25)}}
@media (prefers-reduced-motion: reduce){.stApp::before,.stApp::after,.hero::before,.hero::after{animation:none}}
[data-testid="stAppViewContainer"]{position:relative;z-index:1;background:transparent !important}
[data-testid="stMain"], [data-testid="stHeader"]{background:transparent !important}
.block-container{background:rgba(255,255,255,__CARD__);border-radius:18px;
  box-shadow:0 8px 30px rgba(__DARK__,.25), 0 0 0 1px rgba(__ACC__,.30);
  margin-top:.6rem;padding-top:1.4rem !important;max-width:1280px}
.block-container h1,.block-container h2,.block-container h3,.block-container h4{color:rgb(__DARK__) !important}
.block-container h2,.block-container h3{border-bottom:2px solid rgba(__ACC__,.32);padding-bottom:.25rem}

/* ---------- hero banner with its own smoke ---------- */
.hero{position:relative;overflow:hidden;border-radius:16px;padding:22px 26px 20px 26px;margin-bottom:16px;
  color:#fff !important;
  background:
   radial-gradient(circle at 93% 14%, rgba(255,250,215,__S__) 0, rgba(255,244,190,__S3__) 9%, rgba(255,240,170,0) 22%),
   linear-gradient(135deg, rgb(__DARK__) 0%, rgb(__MID__) 100%) !important;
  box-shadow:0 6px 20px rgba(__DARK__,.35)}
.hero::before,.hero::after{content:"";position:absolute;inset:-30%;pointer-events:none}
.hero::before{background:
   radial-gradient(34% 44% at 18% 42%, rgba(__SM__,__HH__) 0%, rgba(__SM__,0) 70%),
   radial-gradient(40% 50% at 70% 68%, rgba(__SM__,__HH__) 0%, rgba(__SM__,0) 70%);
  animation:smogA 26s ease-in-out infinite alternate}
.hero::after{background:
   radial-gradient(30% 40% at 45% 25%, rgba(__SM__,__HH6__) 0%, rgba(__SM__,0) 70%),
   radial-gradient(36% 46% at 88% 55%, rgba(__SM__,__HH6__) 0%, rgba(__SM__,0) 70%);
  animation:smogB 34s ease-in-out infinite alternate}
.hero > *{position:relative;z-index:1}
.hero h1, .hero p, .hero .tag, .hero .status, .hero .advice{color:#fff !important}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{background:linear-gradient(180deg, rgb(__DARK__) 0%, rgb(__SIDE2__) 100%) !important}
.brand .mark{background-image:url("data:image/svg+xml,__BRAND__") !important}
.brand .b2, .side-h, .pf-h{color:rgb(__MID__) !important}
.side-h{border-bottom:1px solid rgba(__ACC__,.35) !important}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover{background:rgba(__ACC__,.15) !important}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){
  background:linear-gradient(90deg,rgba(__ACC__,.30),rgba(__ACC__,.05)) !important;
  border-color:rgba(__ACC__,.65) !important;box-shadow:inset 3px 0 0 rgb(__STRONG__) !important}
section[data-testid="stSidebar"] button[data-testid*="pillsActive"]{
  background:rgb(__STRONG__) !important;border-color:rgb(__STRONG__) !important}
section[data-testid="stSidebar"] [data-baseweb="tag"]{background:rgb(__STRONG__) !important}
section[data-testid="stSidebar"] div[data-baseweb="slider"] div[role="slider"]{background-color:rgb(__SOFT__) !important}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{scrollbar-color:rgb(__ACC__) rgba(0,0,0,.05) !important}
section[data-testid="stSidebar"] *::-webkit-scrollbar-thumb{background:rgb(__ACC__) !important}
.sstat .sl{color:rgb(__MID__) !important}

/* ---------- cards, KPIs, insights ---------- */
.kc{background:linear-gradient(135deg, rgb(__DARK__), rgb(__MID__)) !important;
  box-shadow:0 4px 14px rgba(__DARK__,.30) !important;border-bottom:3px solid rgb(__SOFT__)}
.insights{background:rgba(__ACC__,.12) !important;border-left:4px solid rgb(__STRONG__) !important}
.ic{background:rgb(__TINT__) !important;border:1px solid rgba(__ACC__,.32) !important;
  border-top:4px solid rgb(__STRONG__) !important}
.it{color:rgb(__DARK__) !important}
.verdict{background:rgba(__ACC__,.08) !important}
.disc{border-top:1px solid rgba(__ACC__,.45) !important}

/* ---------- top tab bar ---------- */
.block-container div[data-testid="stRadio"] div[role="radiogroup"]{background:rgba(__TINT__,.88);
  border:1px solid rgba(__ACC__,.38);box-shadow:0 2px 10px rgba(__DARK__,.14)}
.block-container div[role="radiogroup"] > label p{color:rgb(__DARK__) !important}
.block-container div[role="radiogroup"] > label:hover{background:rgba(__ACC__,.20) !important}
.block-container div[role="radiogroup"] > label:has(input:checked){
  background:linear-gradient(135deg, rgb(__STRONG__), rgb(__MID__)) !important;
  box-shadow:0 3px 10px rgba(__DARK__,.35)}
.block-container div[role="radiogroup"] > label:has(input:checked) p{color:#fff !important}

/* ---------- loading sign ---------- */
div[data-testid="stSpinner"]{background:rgba(__ACC__,.14);border:1px solid rgba(__ACC__,.40);
  border-radius:12px;padding:14px 18px;margin:10px 0;font-weight:600;font-size:1.05rem;
  box-shadow:0 2px 10px rgba(__DARK__,.12)}
div[data-testid="stSpinner"], div[data-testid="stSpinner"] *{color:rgb(__DARK__) !important}
div[data-testid="stSpinner"] i, div[data-testid="stSpinner"] > div > div:first-child{
  border-top-color:rgb(__STRONG__) !important;border-right-color:rgb(__STRONG__) !important}

/* ---------- streamlit widgets ---------- */
button[data-baseweb="tab"][aria-selected="true"]{color:rgb(__STRONG__) !important}
div[data-baseweb="tab-highlight"]{background-color:rgb(__STRONG__) !important}
.block-container div[data-baseweb="slider"] div[role="slider"]{background-color:rgb(__STRONG__) !important}
.stButton > button:hover, .stDownloadButton > button:hover{
  border-color:rgb(__STRONG__) !important;color:rgb(__STRONG__) !important}
.stButton > button:active, .stDownloadButton > button:active{background:rgba(__ACC__,.15) !important}
</style>
"""
    tokens = {
        "__S6__": f"{sun * 0.6:.2f}", "__S3__": f"{sun * 0.25:.2f}", "__S__": f"{sun:.2f}",
        "__H8__": f"{haze * 0.8:.2f}", "__H6__": f"{haze * 0.6:.2f}", "__H__": f"{haze:.2f}",
        "__HH6__": f"{min(haze * 0.7 + 0.05, 0.9):.2f}", "__HH__": f"{min(haze + 0.10, 0.92):.2f}",
        "__V__": f"{veil:.2f}", "__CARD__": f"{card:.2f}", "__SM__": _rgb(c["smog"]),
        "__SKYT__": _rgb(c["sky_top"]), "__SKYB__": _rgb(c["sky_bot"]),
        "__DARK__": _rgb(c["dark"]), "__MID__": _rgb(c["mid"]), "__ACC__": _rgb(c["accent"]),
        "__SOFT__": _rgb(c["soft"]), "__STRONG__": _rgb(c["strong"]), "__SIDE2__": _rgb(c["side2"]),
        "__TINT__": _rgb(c["tint"]), "__BRAND__": quote(brand, safe="%"),
    }
    for k, v in tokens.items():
        css = css.replace(k, v)
    return css
