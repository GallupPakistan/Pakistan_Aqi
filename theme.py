"""
theme.py - ALL styling for the dashboard lives here (app.py has no CSS or JS any more).

It makes the dashboard change mood with the air quality.

    Good air          -> fresh green, clear bright sky
    Moderate (to 100) -> still green, with a light haze building
    Unhealthy (sens.) -> turns warm light grey, visible smog (from ~115)
    Unhealthy         -> mid grey, thick drifting smog
    Very unhealthy    -> dark charcoal, heavy smog
    Hazardous         -> near-black, smoke everywhere

Where to change what:
    PALETTE        colours / smog / sun for each AQI level (dynamic theme)
    TAB_ICON_*     colour of the icons in the top tab bar
    NAV_ICONS      the tab-bar icons themselves
    STATIC_CSS     layout, fonts, sizes, cards, KPI boxes, hero banner, sidebar shape, tab bar shape
    theme_css()    every colour that follows the AQI (sidebar, pills, tabs, cards, text)
    stChatMessage  the AI Advisor tab chat look (advisor.py builds the content)
    .smog / .cig   the Smog Equivalency Calculator card and cigarette icons (smog.py builds the content)
    MAP_STYLE      base map tiles (English labels)
    SIDEBAR_SCROLL_JS  the scroll-up / scroll-down buttons in the sidebar

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
         sky_top=(134, 134, 138), sky_bot=(202, 202, 206), smog=(150, 150, 154), haze=0.62, veil=0.17, sun=0.12, card=0.89),
    dict(aqi=200, accent=(98, 98, 108),   mid=(62, 62, 71),    dark=(26, 26, 33),  tint=(230, 230, 235),
         sky_top=(96, 96, 104),   sky_bot=(166, 166, 172), smog=(112, 112, 118), haze=0.74, veil=0.24, sun=0.00, card=0.85),
    dict(aqi=300, accent=(72, 68, 72),    mid=(44, 42, 46),    dark=(18, 17, 19),  tint=(224, 222, 224),
         sky_top=(58, 56, 60),    sky_bot=(108, 106, 110), smog=(72, 70, 74),   haze=0.86, veil=0.30, sun=0.00, card=0.80),
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
    pio.templates["plotly"].layout.font.color = hexc(c["dark"])   # chart text is always dark (the page card is light)


# ----------------------------------------------------------------------------
# Simple knobs
# ----------------------------------------------------------------------------
TAB_ICON_IDLE = "#3d4a5c"     # top-tab icon colour (not selected)
TAB_ICON_ACTIVE = "#ffffff"   # top-tab icon colour (selected)

NAV_ICONS = [
    "<rect x='3' y='3' width='7' height='7' rx='2'/><rect x='14' y='3' width='7' height='7' rx='2'/>"
    "<rect x='3' y='14' width='7' height='7' rx='2'/><rect x='14' y='14' width='7' height='7' rx='2'/>",
    "<rect x='3' y='5' width='18' height='16' rx='3'/><path d='M8 3v4M16 3v4M3 10h18M8 15h3M13 15h3'/>",
    "<circle cx='12' cy='12' r='9'/><path d='M12 7v5l3 2'/>",
    "<path d='M3 21h18M5 21V10l5-3v14M10 21V4l6 3v14M16 21v-8l3 1.5V21'/>",
    "<polyline points='3,17 8,11 12,14 17,7'/><polyline points='17,7 21,3' stroke-dasharray='2 2'/>"
    "<polyline points='16,3 21,3 21,8'/>",
    "<path d='M4 5h16v11H9l-5 4z'/><path d='M8 9h8M8 12h5'/>",
]


def _icon(inner, stroke):
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='" + stroke +
           "' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>" + inner + "</svg>")
    return 'url("data:image/svg+xml,' + quote(svg) + '")'


_TAB = '.block-container div[role="radiogroup"]'


def _tab_sel(i, extra=""):
    """Icon selector that works whether the tab labels are direct children of the radiogroup or wrapped."""
    tail = '[data-testid="stMarkdownContainer"] p::before'
    return (f'{_TAB} > label:nth-child({i}){extra} {tail}, '
            f'{_TAB} > *:nth-child({i}) label{extra} {tail}')


def _nav_css():
    return "".join(
        _tab_sel(i + 1) + "{background-image:%s}" % _icon(ic, TAB_ICON_IDLE)
        + _tab_sel(i + 1, ":has(input:checked)") + "{background-image:%s}" % _icon(ic, TAB_ICON_ACTIVE)
        for i, ic in enumerate(NAV_ICONS))


# ----------------------------------------------------------------------------
# Static CSS: shapes, sizes, layout (colours that follow the AQI are in theme_css below)
# ----------------------------------------------------------------------------
STATIC_CSS = r"""
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
<style>
/* always render with light-mode form controls/scrollbars, even when Chrome is in dark mode */
:root, .stApp{color-scheme:light !important}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0b0a26 0%,#16143d 100%)}
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] li{color:#f1f1f7}
section[data-testid="stSidebar"] div[data-baseweb="select"] input{color:#111 !important}
.brand{display:flex;align-items:center;gap:12px;margin:0 0 12px 0}
.brand .mark{width:40px;height:40px;flex:none;background-size:contain;background-repeat:no-repeat;}
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
section[data-testid="stSidebar"] button[data-testid*="pills"]{border-radius:999px !important;
  padding:2px 14px !important;min-height:34px;box-shadow:none}
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
.smog{border-radius:16px;padding:20px 24px;margin:6px 0 14px 0;color:#fff !important;
  box-shadow:0 6px 20px rgba(0,0,0,.28)}
.smog .sk{font-size:.74rem;letter-spacing:.2em;opacity:.85}
.smog .sbig{font-size:1.3rem;line-height:1.5;margin:.4rem 0 .3rem 0;color:#fff !important}
.smog .sbig b{font-size:1.7rem}
.smog .sn{font-size:.8rem;opacity:.82;margin-top:10px;line-height:1.5}
.cigs{display:flex;flex-wrap:wrap;align-items:center;margin:12px 0 4px 0}
.cig{display:inline-block;width:78px;height:11px;border-radius:3px;overflow:hidden;margin:3px 7px 3px 0;
  background:rgba(255,255,255,.16)}
.cig i{display:block;height:100%;
  background:linear-gradient(90deg,#d99a4e 0 24%,#f7f3ea 24% 90%,#e2553a 90% 100%)}
.cigmore{font-size:.9rem;font-weight:700;margin-left:4px}
/* ---- AI advisor chat (main area) ---- */
.block-container [data-testid="stChatMessage"]{border-radius:14px;padding:10px 14px;margin-bottom:8px}
[class*="st-key-adv_sug"] button{border-radius:12px;text-align:left;font-size:.88rem;line-height:1.35;
  min-height:68px;height:100%}
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
.block-container div[data-testid="stRadio"] div[role="radiogroup"]{display:flex;flex-direction:row;flex-wrap:nowrap;
  gap:4px;padding:6px;border-radius:14px;width:fit-content;max-width:100%;overflow-x:auto;scrollbar-width:thin}
.block-container div[role="radiogroup"] label{border-radius:10px;padding:8px clamp(9px,1.1vw,18px);margin:0;cursor:pointer;flex:0 0 auto;
  transition:all .2s ease}
.block-container div[role="radiogroup"] label > div:first-child{position:absolute;opacity:0;width:0;height:0;
  overflow:hidden}
.block-container div[role="radiogroup"] label [data-testid="stMarkdownContainer"] p{font-size:clamp(.82rem,.95vw,.98rem);
  font-weight:600;margin:0;white-space:nowrap}
.block-container div[role="radiogroup"] label [data-testid="stMarkdownContainer"] p::before{content:"";
  display:inline-block;width:18px;height:18px;margin-right:7px;vertical-align:-4px;background-size:contain;
  background-repeat:no-repeat}
.block-container div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child{position:absolute;opacity:0;
  width:0;height:0;overflow:hidden}
@media (max-width:640px){.block-container div[role="radiogroup"] label{padding:7px 12px}}
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
"""


def static_css():
    """Inject once, at the top of app.py:  st.markdown(static_css(), unsafe_allow_html=True)"""
    return STATIC_CSS + "<style>" + _nav_css() + "</style>"


# ----------------------------------------------------------------------------
# Sidebar scroll-up / scroll-down buttons (JavaScript, rendered through components.html)
# ----------------------------------------------------------------------------
SIDEBAR_SCROLL_JS = r"""
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



# ----------------------------------------------------------------------------
# Maps: carto-positron has English (Latin-script) labels and needs no token.
# Other no-token options: "carto-darkmatter", "open-street-map" (local-language labels), "white-bg".
# ----------------------------------------------------------------------------
MAP_STYLE = "carto-positron"


def style_map(fig):
    """Apply the dashboard's map style to a Plotly map figure (scatter_map or scatter_mapbox)."""
    new_api = any(getattr(tr, "type", "") == "scattermap" for tr in fig.data)
    fig.update_layout(**({"map_style": MAP_STYLE} if new_api else {"mapbox_style": MAP_STYLE}),
                      legend=dict(font=dict(color="#1c2b2a"), title_font=dict(color="#1c2b2a")))
    return fig



def status_card(aqi, head, source, dot="#999"):
    """Coloured air-status card at the top of the sidebar (dot = official AQI colour)."""
    c = colors(aqi)
    scope = "forecast" if source == "forecast" else "current filters"
    return (f'<div class="sstat" style="border-left-color:{dot};'
            f'background:linear-gradient(90deg,rgba({_rgb(c["accent"])},.40),rgba({_rgb(c["accent"])},.06))">'
            f'<div class="sl">AIR RIGHT NOW</div>'
            f'<div class="sh"><span style="display:inline-block;width:11px;height:11px;border-radius:50%;'
            f'background:{dot};margin-right:8px;box-shadow:0 0 0 2px rgba(255,255,255,.55)"></span>{head}</div>'
            f'<div class="sv">AQI {aqi:.0f} · {scope}</div></div>')


# ----------------------------------------------------------------------------
# Roaming smog clouds (pure CSS, no JavaScript). Clouds drift across the whole screen; they get denser and
# darker as the AQI rises. Four layers: three drift OVER the page (they never block clicks) and one drifts
# BEHIND the content card so it shows in the margins. Turned off by the sidebar toggle in app.py.
# ----------------------------------------------------------------------------
_FOG_TILE = "80vw"          # one cloud cluster repeats every 80vw, so the loop is seamless
_PUFFS = {                  # (centre x %, centre y %, radius x %, radius y %, alpha)
    "A": [(26, 52, 22, 42, .80), (40, 40, 18, 34, .70), (52, 58, 24, 44, .85), (66, 44, 18, 36, .70),
          (76, 56, 15, 30, .60), (36, 62, 16, 28, .55)],
    "B": [(24, 45, 17, 36, .75), (38, 58, 24, 46, .85), (55, 42, 20, 38, .75), (70, 60, 19, 34, .70),
          (46, 50, 14, 28, .60), (78, 46, 12, 26, .55)],
    "C": [(28, 56, 20, 40, .78), (44, 44, 22, 42, .82), (60, 58, 18, 34, .72), (74, 48, 16, 32, .65),
          (34, 38, 12, 24, .55)],
    "D": [(30, 50, 18, 38, .85), (50, 55, 24, 46, .90), (68, 45, 16, 32, .75), (40, 40, 13, 26, .60),
          (76, 58, 13, 26, .55)],
}


def _puffs(rgb, key):
    return ",".join(
        f"radial-gradient(ellipse {rx}% {ry}% at {cx}% {cy}%, rgba({rgb},{a}) 0%, rgba({rgb},{a * .6:.2f}) 35%, "
        f"rgba({rgb},0) 70%)" for cx, cy, rx, ry, a in _PUFFS[key])


def fog_css(aqi):
    v = float(np.clip(aqi, 0, 300)) / 300.0
    base = _ip("smog", aqi)
    rgb = _rgb(_mix(base, 0.30 * v, (128, 116, 98)))       # warm grey-brown tint as the air gets worse
    a = 0.18 + 0.26 * v                                    # overall cloud strength: 0.18 (clean) .. 0.44 (hazardous)
    P = _FOG_TILE
    common = ("content:\"\";position:fixed;left:-100vw;width:300vw;pointer-events:none;background-repeat:repeat-x;"
              f"background-size:{P} 100%;will-change:transform")
    return f"""
<style>
/* ---------- roaming smog clouds ---------- */
body::before,body::after,html::after,[data-testid="stAppViewContainer"]::before{{{common}}}
body::before{{top:3vh;height:34vh;z-index:4;background-image:{_puffs(rgb, "A")};opacity:{a * .80:.2f};
  animation:fogR 150s linear -40s infinite,fogBob 23s ease-in-out -6s infinite alternate}}
body::after{{top:36vh;height:40vh;z-index:5;background-image:{_puffs(rgb, "B")};opacity:{a * .90:.2f};
  animation:fogL 105s linear -70s infinite,fogBob 31s ease-in-out -12s infinite alternate-reverse}}
html::after{{top:64vh;height:36vh;z-index:6;background-image:{_puffs(rgb, "C")};opacity:{a * .75:.2f};
  animation:fogR 130s linear -90s infinite,fogBob 27s ease-in-out -3s infinite alternate}}
[data-testid="stAppViewContainer"]::before{{top:18vh;height:56vh;z-index:-1;background-image:{_puffs(rgb, "D")};
  opacity:{min(a * 1.5, .70):.2f};animation:fogL 85s linear -30s infinite,fogBob 35s ease-in-out -9s infinite alternate}}
@keyframes fogR{{from{{transform:translate3d(0,0,0)}}to{{transform:translate3d({P},0,0)}}}}
@keyframes fogL{{from{{transform:translate3d(0,0,0)}}to{{transform:translate3d(-{P},0,0)}}}}
@keyframes fogBob{{from{{translate:0 -2.5vh}}to{{translate:0 3vh}}}}
@media (prefers-reduced-motion: reduce){{body::before,body::after,html::after,
  [data-testid="stAppViewContainer"]::before{{animation:none}}}}
</style>
"""


def theme_css(aqi, fog=True):
    c = colors(aqi)
    sun, haze, veil, card = _ip("sun", aqi), _ip("haze", aqi), _ip("veil", aqi), _ip("card", aqi)
    brand = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40' fill='none'>"
             "<circle cx='20' cy='20' r='18' stroke='rgb(%s)' stroke-width='2'/>"
             "<path d='M9 15c4-3 7 3 11 0s7-3 11 0M9 21c4-3 7 3 11 0s7-3 11 0M9 27c4-3 7 3 11 0s7-3 11 0' "
             "stroke='white' stroke-width='2' stroke-linecap='round'/></svg>") % _rgb(c["soft"])
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
[data-testid="stMain"]{color:rgb(__DARK__) !important}
[data-testid="stHeader"], [data-testid="stHeader"] *{color:rgb(__DARK__) !important}
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
.brand .b2, .side-h, .pf-h{color:rgb(__SOFT__) !important}
.side-h{border-bottom:1px solid rgba(__SOFT__,.35) !important}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{background:rgba(__SOFT__,.18) !important}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
  background:linear-gradient(90deg,rgba(__SOFT__,.38),rgba(__SOFT__,.06)) !important;
  border-color:rgba(__SOFT__,.75) !important;box-shadow:inset 3px 0 0 rgb(__SOFT__) !important}
section[data-testid="stSidebar"] button[data-testid*="pillsActive"]{
  background:rgb(__STRONG__) !important;border-color:rgb(__STRONG__) !important}

/* sidebar filter pills, built to stay readable in Streamlit's light AND dark themes (and in any browser light/dark mode):
   inactive = light chip + dark text, active = solid accent + white text. Extra selectors + higher specificity so
   Streamlit's own theme styles can't win, and text colours are set together with the background. */
html body section[data-testid="stSidebar"] :is(button[data-testid="stBaseButton-pills"], button[kind="pills"]){
  background:rgba(255,255,255,.92) !important;background-image:none !important;
  border:1px solid rgba(__SOFT__,.75) !important;box-shadow:none !important}
html body section[data-testid="stSidebar"] :is(button[data-testid="stBaseButton-pills"], button[kind="pills"]),
html body section[data-testid="stSidebar"] :is(button[data-testid="stBaseButton-pills"], button[kind="pills"]) *{
  color:rgb(__DARK__) !important;-webkit-text-fill-color:rgb(__DARK__) !important;opacity:1 !important}
html body section[data-testid="stSidebar"] :is(button[data-testid="stBaseButton-pills"], button[kind="pills"]):hover{
  background:rgb(__SOFT__) !important;border-color:rgb(__SOFT__) !important}
html body section[data-testid="stSidebar"] :is(button[data-testid*="pillsActive"], button[kind="pillsActive"]){
  background:rgb(__STRONG__) !important;background-image:none !important;
  border:1px solid rgb(__STRONG__) !important;box-shadow:none !important}
html body section[data-testid="stSidebar"] :is(button[data-testid*="pillsActive"], button[kind="pillsActive"]),
html body section[data-testid="stSidebar"] :is(button[data-testid*="pillsActive"], button[kind="pillsActive"]) *{
  color:#fff !important;-webkit-text-fill-color:#fff !important;opacity:1 !important}

section[data-testid="stSidebar"] [data-baseweb="tag"]{background:rgb(__STRONG__) !important}
section[data-testid="stSidebar"] div[data-baseweb="slider"] div[role="slider"]{background-color:rgb(__SOFT__) !important}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{scrollbar-color:rgb(__SOFT__) rgba(255,255,255,.06) !important}
section[data-testid="stSidebar"] *::-webkit-scrollbar-thumb{background:rgb(__SOFT__) !important}
.block-container [data-testid="stChatMessage"]{background:rgba(__TINT__,.85) !important;
  border:1px solid rgba(__ACC__,.30)}
.block-container [data-testid="stChatMessage"] *{color:rgb(__DARK__) !important}
[class*="st-key-adv_sug"] button{background:rgb(__TINT__) !important;border:1px solid rgba(__ACC__,.45) !important}
[class*="st-key-adv_sug"] button, [class*="st-key-adv_sug"] button p{color:rgb(__DARK__) !important}
[class*="st-key-adv_sug"] button:hover{background:rgba(__ACC__,.22) !important;border-color:rgb(__STRONG__) !important}
.sstat .sl{color:rgb(__SOFT__) !important;opacity:1 !important;font-weight:700}
section[data-testid="stSidebar"] label p{color:rgb(__SOFT__) !important;opacity:1 !important}

/* ---------- cards, KPIs, insights ---------- */
.smog{background:linear-gradient(135deg, rgb(__DARK__), rgb(__MID__)) !important;
  border-bottom:3px solid rgb(__SOFT__)}
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
.block-container div[role="radiogroup"] label p{color:rgb(__DARK__) !important}
.block-container div[role="radiogroup"] label:hover{background:rgba(__ACC__,.20) !important}
.block-container div[role="radiogroup"] label:has(input:checked){
  background:linear-gradient(135deg, rgb(__STRONG__), rgb(__MID__)) !important;
  box-shadow:0 3px 10px rgba(__DARK__,.35)}
.block-container div[role="radiogroup"] label:has(input:checked) p{color:#fff !important}

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

/* ---------- charts: light card, dark text, transparent backgrounds (Streamlit light AND dark themes) ----------
   In Streamlit's dark theme Plotly paints a dark chart background with near-white text. The content card is always
   light, so: make chart backgrounds transparent and every axis / legend / title / colourbar / selector text dark.
   Plotly writes colours inline, hence !important. Text drawn INSIDE coloured marks (heatmap cells, labels inside
   bars) is left alone so it keeps its own white/dark contrast. */
.block-container .js-plotly-plot .main-svg{background:transparent !important}
.block-container .js-plotly-plot .main-svg .bg{fill:transparent !important;fill-opacity:0 !important}
.block-container .js-plotly-plot :is(.xtick,.ytick,.x2tick,.y2tick,.x3tick,.y3tick,.angularaxistick,.radialaxistick) text,
.block-container .js-plotly-plot :is(.g-xtitle,.g-ytitle,.g-x2title,.g-y2title) text,
.block-container .js-plotly-plot :is(.cbaxis,.cbtitle,.legend,.rangeselector,.rangeslider-container) text,
.block-container .js-plotly-plot :is(.gtitle,.legendtext,.legendtitletext,.annotation-text,.bartext-outside,.textpoint text){
  fill:rgb(__DARK__) !important;fill-opacity:1 !important;opacity:1 !important}
.block-container .js-plotly-plot .rangeselector .selector-rect{fill:rgb(__TINT__) !important}
.block-container .js-plotly-plot .gridlayer path{stroke:rgba(__DARK__,.16) !important}
.block-container .js-plotly-plot .zerolinelayer path{stroke:rgba(__DARK__,.35) !important}

/* disclaimer + footer: always dark text on the light card (they were near-white in Streamlit's dark theme) */
.block-container .disc, .block-container .disc *, .block-container .foot, .block-container .foot *{
  color:rgb(__DARK__) !important}

/* chat input + main-area form controls: light, never the black Streamlit-dark look */
[data-testid="stBottom"], [data-testid="stBottom"] > div{background:transparent !important}
.block-container{padding-bottom:2rem !important}
.block-container [data-testid="stChatInput"]{background:rgb(__TINT__) !important;border:1px solid rgba(__ACC__,.45) !important;
  border-radius:14px !important;box-shadow:none !important}
.block-container [data-testid="stChatInput"]:focus-within{border-color:rgb(__STRONG__) !important}
.block-container [data-testid="stChatInput"] *{background:transparent !important;border-color:transparent !important;
  box-shadow:none !important;color:rgb(__DARK__) !important;-webkit-text-fill-color:rgb(__DARK__) !important}
.block-container [data-testid="stChatInput"] textarea::placeholder{color:rgba(__DARK__,.6) !important;
  -webkit-text-fill-color:rgba(__DARK__,.6) !important}
.block-container [data-testid="stChatInput"] button svg{fill:rgb(__STRONG__) !important}
.block-container :is([data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"]){
  background:rgb(__TINT__) !important;border-color:rgba(__ACC__,.45) !important}
.block-container [data-baseweb="select"] :is(div,input,svg){color:rgb(__DARK__) !important;
  -webkit-text-fill-color:rgb(__DARK__) !important;fill:rgb(__DARK__) !important}
.block-container :is([data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="textarea"]) :is(input,textarea){
  color:rgb(__DARK__) !important;-webkit-text-fill-color:rgb(__DARK__) !important}

/* captions, widget labels and metrics in the main area (zero specificity, so cards that set their own colour still win) */
:where(.block-container) :where([data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *,
  [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] *, [data-testid="stMetricLabel"],
  [data-testid="stMetricLabel"] *, [data-testid="stMetricValue"], [data-testid="stMetricValue"] *){
  color:rgb(__DARK__) !important}
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
    return css + (fog_css(aqi) if fog else "")
