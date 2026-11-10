"""
advisor.py - "Smog Excuse & Health Advisor": an AI chat (its own tab) that answers with
LIVE air-quality data (Open-Meteo, free, no key) plus the dashboard's daily data.

Setup (once):
    pip install requests google-genai anthropic
    .streamlit/secrets.toml:
        GEMINI_API_KEY = "..."            # preferred if present
        GEMINI_MODEL   = "gemini-2.5-flash"   # optional, change here if Google retires it
        ANTHROPIC_API_KEY = "sk-ant-..."  # optional fallback provider
        ANTHROPIC_MODEL   = "claude-haiku-5-5"  # optional
    (or environment variables with the same names; Streamlit Cloud: App settings -> Secrets)

Fallback chain: live data -> dashboard daily data -> rule-based advice.
AI provider: Gemini -> Anthropic -> offline rule-based answer. If an AI call fails, the offline answer is used.

Used by the "AI Advisor" tab in app.py:   render_advisor(daily, aqi_cat)   # daily = prepped daily dataframe
All colours / shapes of the chat live in theme.py (look for stChatMessage there).
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
import streamlit as st

from smog import CIG_UG, find_pm25_col, aqi_to_pm25

MODEL = "claude-haiku-5-5"          # Anthropic default; override with ANTHROPIC_MODEL
GEMINI_DEFAULT = "gemini-2.5-flash"  # override with GEMINI_MODEL
MAX_TOKENS = 450                    # Anthropic reply cap
GEMINI_MAX_TOKENS = 900             # Gemini 2.5 may spend some tokens on thinking
MAX_USER_MSGS = 25                  # per browser session (protects your API bill on a public app)
MAX_CHARS = 500
HISTORY_TURNS = 8                   # earlier messages sent along with each question

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
LIVE_TTL = 600                      # seconds; live data refreshes at most every 10 minutes for ALL users

SUGGESTIONS = [
    "Is it safe for my 6-year-old to play cricket outside today?",
    "Which mask should I buy for an AQI of 400?",
    "Give me a smog excuse to work from home",
]

SYSTEM = """You are "Smog Advisor", a friendly assistant inside the Gallup Pakistan Air Quality dashboard.

RULES
- Take every air-quality number ONLY from the DATA and LIVE NOW blocks below. Never invent readings. If a city is not in them, say so.
- If a LIVE NOW line exists for a city, use it and just say "right now" (do not mention timestamps, "modelled", or data sources). Otherwise use the dashboard's daily reading and say "latest daily average" with its date. Never call a daily reading "live".
- If the user asks about a hypothetical AQI (e.g. "for an AQI of 400"), answer for that number, and briefly mention the current real value too.
- Answer the exact question asked (office, kids, masks, excuse...) with a clear yes/no/it-depends first, then 2-4 short tips. Never repeat the same generic paragraph.
- Use US AQI bands: 0-50 Good, 51-100 Moderate, 101-150 Unhealthy for sensitive groups, 151-200 Unhealthy, 201-300 Very unhealthy, 301+ Hazardous.
- Give practical advice for Pakistan: school sports and outdoor play, walking, commuting, motorbike riders, outdoor workers, keeping windows closed at peak pollution hours, indoor air purifiers or a simple DIY fan-and-filter box.
- Masks: N95 / KN95 / FFP2 respirators filter fine particles (PM2.5) when they fit snugly; cloth and plain surgical masks give little protection from PM2.5. They are usually sold at pharmacies, medical-supply stores and online marketplaces. Do not quote prices or recommend brands. Advise checking genuine certification (NIOSH N95, EN 149 FFP2) because counterfeits exist, and note that kids need small-size respirators that fit.
- Be more cautious for children, older adults, pregnancy, asthma, heart or lung disease. Say to see a doctor for such conditions, and to seek urgent care for breathlessness, chest pain or fainting. You are not a doctor.
- If asked for a "smog excuse" (to skip sports, work from home, cancel plans), give one short, witty but honest excuse that cites the real numbers.
- Reply in the user's language (English or Urdu/Roman Urdu), warm and concise: at most about 140 words, short bullets allowed.
- If the question is not about air quality, health or the dashboard, politely steer back.
"""


# ----------------------------------------------------------------------------
# Live data (Open-Meteo): geocode any city, one batched + cached request
# ----------------------------------------------------------------------------
_GEO = {}      # process-wide cache city -> (lat, lon); shared by all users, survives reruns


def _geocode(city):
    if city in _GEO:
        return _GEO[city]
    r = requests.get(GEO_URL, params={"name": city, "count": 1, "country_code": "PK"}, timeout=5)
    r.raise_for_status()
    res = r.json().get("results")
    p = (res[0]["latitude"], res[0]["longitude"]) if res else None
    if p:
        _GEO[city] = p
    return p


def _safe_geo(city):
    try:
        return city, _geocode(city)
    except Exception:
        return city, None


@st.cache_data(ttl=LIVE_TTL, show_spinner=False)
def _fetch_live(cities):
    with ThreadPoolExecutor(max_workers=8) as ex:          # geocode all cities in parallel
        pts = {c: p for c, p in ex.map(_safe_geo, cities) if p}
    if not pts:
        raise RuntimeError("no coordinates")      # raised so an empty result is not cached
    names = list(pts)
    r = requests.get(AQ_URL, params={
        "latitude": ",".join(str(pts[n][0]) for n in names),
        "longitude": ",".join(str(pts[n][1]) for n in names),
        "current": "us_aqi,pm2_5", "timezone": "auto"}, timeout=8)
    r.raise_for_status()
    data = r.json()
    data = [data] if isinstance(data, dict) else data
    out = {}
    for n, d in zip(names, data):
        c = d.get("current", {})
        if c.get("us_aqi") is not None:
            out[n] = {"aqi": float(c["us_aqi"]), "pm25": c.get("pm2_5"), "time": c.get("time")}
    if not out:
        raise RuntimeError("no live values")
    return out


def get_live(cities):
    """Live readings {city: {aqi, pm25, time}}; {} if the feed is down (chat never breaks)."""
    try:
        return _fetch_live(tuple(sorted(cities)))
    except Exception:
        return {}


def live_block(live, aqi_cat):
    if not live:
        return "LIVE DATA: unavailable right now. Use the daily readings above and state their date.\n"
    lines = []
    for c, v in sorted(live.items(), key=lambda x: -x[1]["aqi"]):
        pm = f"{v['pm25']:.0f}" if isinstance(v.get("pm25"), (int, float)) else "n/a"
        lines.append(f"{c}: AQI {v['aqi']:.0f} [{aqi_cat(v['aqi'])}], PM2.5 {pm} ug/m3, as of {v['time']}")
    return "LIVE NOW (modelled estimate, updated every ~10 min):\n" + "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------
# Context built from the dashboard data
# ----------------------------------------------------------------------------
def _prep(d):
    col = find_pm25_col(d)
    if col:
        pm = pd.to_numeric(d[col], errors="coerce")
    else:
        pm = pd.Series(aqi_to_pm25(pd.to_numeric(d["us_aqi_avg"], errors="coerce").to_numpy()), index=d.index)
    return d.assign(_pm=pm, _aqi=pd.to_numeric(d["us_aqi_avg"], errors="coerce"))


def build_context(d, city, aqi_cat):
    d = _prep(d)
    latest = d.sort_values("date").groupby("city").tail(1).sort_values("_aqi", ascending=False)
    lines = []
    for _, r in latest.iterrows():
        pm = f"{r['_pm']:.0f}" if np.isfinite(r["_pm"]) else "n/a"
        aq = f"{r['_aqi']:.0f}" if np.isfinite(r["_aqi"]) else "n/a"
        lines.append(f"{r['city']} ({r.get('province', '')}): AQI {aq} [{aqi_cat(r['_aqi'])}], PM2.5 {pm} ug/m3, "
                     f"daily average of {r['date']:%d %b %Y}")
    week = d[d["city"] == city].sort_values("date").tail(7)
    wk = "; ".join(f"{r['date']:%d %b}: AQI {r['_aqi']:.0f}" for _, r in week.iterrows() if np.isfinite(r["_aqi"]))
    extra = ""
    if len(week):
        last = week.iloc[-1]
        keep = [c for c in d.columns if any(k in str(c).lower() for k in ("temp", "humid", "wind"))
                and any(k in str(c).lower() for k in ("avg", "mean")) and pd.api.types.is_numeric_dtype(d[c])]
        extra = ", ".join(f"{c}={last[c]:.1f}" for c in keep[:4] if np.isfinite(last[c]))
    return (f"DATA (dataset latest date: {d['date'].max():%d %b %Y})\n"
            f"Cities, latest daily reading each (worst first):\n" + "\n".join(lines) +
            f"\n\nUSER-SELECTED CITY: {city}\nLast 7 days AQI: {wk or 'n/a'}\nWeather (latest daily): {extra or 'n/a'}\n"
            f"Rule of thumb: 22 ug/m3 PM2.5 per day = about 1 cigarette.")


# ----------------------------------------------------------------------------
# Backends: Gemini / Anthropic (AI) and an offline fallback
# ----------------------------------------------------------------------------
def _secret(name):
    try:
        v = st.secrets.get(name)
    except Exception:
        v = None
    return v or os.environ.get(name)


def _note(e):
    """Remember the last AI error (shown only when ADVISOR_DEBUG is set) and print it to the server log."""
    msg = f"{type(e).__name__}: {e}"
    print("advisor AI error:", msg)
    st.session_state["adv_err"] = msg


def _client():
    """Returns (provider, client) or None. Gemini first, then Anthropic."""
    if _secret("GEMINI_API_KEY"):
        try:
            from google import genai
            from google.genai import types
            return ("gemini", genai.Client(api_key=_secret("GEMINI_API_KEY"),
                                           http_options=types.HttpOptions(timeout=20000)))
        except Exception as e:
            _note(e)
    if _secret("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            return ("anthropic", anthropic.Anthropic(api_key=_secret("ANTHROPIC_API_KEY"),
                                                     timeout=20.0, max_retries=1))
        except Exception as e:
            _note(e)
    if not (_secret("GEMINI_API_KEY") or _secret("ANTHROPIC_API_KEY")):
        print("advisor: no GEMINI_API_KEY / ANTHROPIC_API_KEY found "
              "(put it in .streamlit/secrets.toml in the folder you run the app from, or set the env var)")
    return None


def _stream_reply(client, system, msgs):
    kind, c = client
    if kind == "gemini":
        from google.genai import types
        contents = [types.Content(role="user" if m["role"] == "user" else "model",
                                  parts=[types.Part(text=m["content"])]) for m in msgs]
        model = _secret("GEMINI_MODEL") or GEMINI_DEFAULT
        kw = {}
        if "flash" in model:                      # skip "thinking" on flash models: much faster
            kw["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        cfg = types.GenerateContentConfig(system_instruction=system, max_output_tokens=GEMINI_MAX_TOKENS, **kw)
        for ch in c.models.generate_content_stream(model=model, contents=contents, config=cfg):
            if ch.text:
                yield ch.text
    else:
        with c.messages.stream(model=_secret("ANTHROPIC_MODEL") or MODEL,
                               max_tokens=MAX_TOKENS, system=system, messages=msgs) as s:
            yield from s.text_stream


def _has(q, words):
    return re.search(r"\b(" + "|".join(words) + r")\b", q) is not None


def _intent(q):
    q = q.lower()
    if _has(q, ["excuse", "skip", "bahana", "cancel", "wfh"]) or "work from home" in q:
        return "excuse"
    if _has(q, ["mask", "masks", "n95", "kn95", "ffp2", "respirator"]):
        return "mask"
    if _has(q, ["kid", "kids", "child", "children", "son", "daughter", "school", "play", "cricket", "football",
                "sport", "sports", "baby", "bacha", "bachay"]):
        return "kids"
    if _has(q, ["office", "work", "job", "commute", "bike", "motorbike", "drive", "driving", "walk", "walking",
                "jog", "run", "running", "exercise", "outside", "outdoor", "outdoors", "go"]):
        return "outdoor"
    return "general"


def _band(aqi):
    return 0 if aqi <= 50 else 1 if aqi <= 100 else 2 if aqi <= 150 else 3 if aqi <= 200 else 4 if aqi <= 300 else 5


def offline_reply(city, aqi, question, aqi_cat, when="right now"):
    """Rule-based answer used when no AI is available; it still follows the question (kids / mask / office / excuse)."""
    if aqi is None or not np.isfinite(aqi):
        return "I don't have a reading for that city yet."
    q = question or ""
    hyp = re.search(r"aqi\D{0,12}(\d{2,3})", q, re.I)
    use = float(hyp.group(1)) if hyp else float(aqi)
    b, cat = _band(use), aqi_cat(use)
    head = (f"At an AQI of **{use:.0f}** ({cat})" if hyp else f"{city} is at AQI **{aqi:.0f}** ({cat}) {when}")
    intent = _intent(q)

    if intent == "kids":
        body = ["Yes, kids can play outside normally.",
                "Yes, but keep an eye on children with asthma or allergies.",
                "Keep it short and light: no hard running or long matches, and skip it for any child with asthma.",
                "Better not. Move cricket or football indoors today and let kids play outside only briefly, if at all.",
                "No outdoor play today. Keep children indoors with windows closed.",
                "Absolutely not. Keep children indoors, seal windows and use an air purifier if you have one."][b]
    elif intent == "mask":
        fit = ("Look for an N95 / KN95 / FFP2 respirator: cloth and plain surgical masks do little against PM2.5. "
               "It must seal snugly around nose and cheeks, so shave or tuck stray hair, and use a small size for kids. "
               "Check genuine certification (NIOSH N95 or EN 149 FFP2) because counterfeits are common, and buy from a "
               "pharmacy or medical-supply store.")
        body = ("A mask isn't really needed at this level, but " if b <= 1 else "") + fit
    elif intent == "excuse":
        body = ["Honestly the air is fine, so this one needs a different excuse.",
                "The air is acceptable, so a smog excuse won't be convincing today.",
                f"\"The air is at AQI {use:.0f}, unhealthy for sensitive groups, and I'm one of them.\"",
                f"\"AQI {use:.0f} is officially unhealthy. Every breath outside is a free cigarette, so I'm working from home.\"",
                f"\"AQI {use:.0f} is very unhealthy: I'm protecting my lungs and keeping my productivity indoors.\"",
                f"\"AQI {use:.0f} is hazardous. Going out is a health risk, so I'm working remotely.\""][b]
    elif intent == "outdoor":
        body = ["Go ahead, the air is fine.",
                "Go ahead; unusually sensitive people may want shorter time outside.",
                "You can go, but people with asthma or heart/lung conditions should limit time outdoors and avoid hard exercise.",
                "Work from home if you can. If you must go, wear a well-fitted N95/KN95/FFP2, especially on a motorbike, "
                "and skip outdoor exercise and walking breaks.",
                "Work from home if at all possible. If you must go, wear a well-fitted N95/KN95/FFP2 and keep outdoor time minimal.",
                "Stay home if you can. If you must travel, use a well-fitted N95/KN95/FFP2 and avoid walking or riding in the open."][b]
    else:
        body = ["Air is healthy. Outdoor play and exercise are fine.",
                "Acceptable air. Unusually sensitive people may want shorter outdoor exertion.",
                "Children, older adults and people with asthma or heart/lung conditions should limit time outdoors and avoid hard exercise.",
                "Everyone should cut back on outdoor exertion. Move sports indoors, keep windows closed and consider an N95/KN95/FFP2 mask outdoors.",
                "Avoid outdoor activity. Keep children indoors, close windows and wear a well-fitted N95/KN95/FFP2 respirator if you must go out.",
                "Hazardous. Stay indoors, seal windows, use an air purifier and wear an N95/KN95/FFP2 for any outdoor trip. "
                "See a doctor for breathlessness or chest pain."][b]
    tail = (f"\n\n_For reference, {city} is at AQI {aqi:.0f} {when}._" if hyp else "")
    return f"{head}. {body}{tail}" if intent != "excuse" else f"{head}. {body}{tail}"


def _offline_for(daily, city, live, aqi_cat, question=""):
    for c in sorted(daily["city"].dropna().unique(), key=len, reverse=True):   # a city named in the question wins
        if c.lower() in (question or "").lower():
            city = c
            break
    lv = live.get(city)
    if lv:
        return offline_reply(city, lv["aqi"], question, aqi_cat)
    rows = _prep(daily)
    rows = rows[rows["city"] == city].sort_values("date")
    if not len(rows):
        return "I don't have a reading for that city yet."
    r = rows.iloc[-1]
    return offline_reply(city, float(r["_aqi"]), question, aqi_cat, when=f"in the latest daily average ({r['date']:%d %b %Y})")


def _history(msgs):
    """Last N messages, guaranteed to start with a user message (required by both providers)."""
    h = [{"role": m["role"], "content": m["content"]} for m in msgs[-(HISTORY_TURNS * 2):]]
    while h and h[0]["role"] != "user":
        h.pop(0)
    return h


# ----------------------------------------------------------------------------
# Tab UI (rendered in the main page by the "AI Advisor" tab)
# ----------------------------------------------------------------------------
def _queue(q):
    st.session_state["adv_pending"] = q


def render_advisor(daily, aqi_cat):
    if daily is None or len(daily) == 0:
        return
    cities = sorted(daily["city"].dropna().unique())
    if st.session_state.get("adv_city") not in cities:
        st.session_state.pop("adv_city", None)
    msgs = st.session_state.setdefault("adv_msgs", [])

    c1, c2 = st.columns([3, 1])
    city = c1.selectbox("City for advice", cities, index=cities.index("Lahore") if "Lahore" in cities else 0,
                        key="adv_city", help="The advisor also knows every other city, so you can name one in your question.")
    c2.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
    if msgs and c2.button("Clear chat", key="adv_clear"):
        st.session_state["adv_msgs"] = []
        st.rerun()

    if not msgs:
        cols = st.columns(len(SUGGESTIONS))
        for i, (col, q) in enumerate(zip(cols, SUGGESTIONS)):
            try:
                col.button(q, key=f"adv_sug{i}", on_click=_queue, args=(q,), width="stretch")
            except TypeError:      # older Streamlit
                col.button(q, key=f"adv_sug{i}", on_click=_queue, args=(q,), use_container_width=True)

    box = st.container()                       # all messages render here, above the input
    with box:
        for m in msgs:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

    with st.container():                       # inside a container the input stays inline instead of docking at the screen bottom
        prompt = st.chat_input("Ask about air, kids, masks, or get a smog excuse...", key="adv_input", max_chars=MAX_CHARS)
    prompt = prompt or st.session_state.pop("adv_pending", None)
    n_user = sum(1 for m in msgs if m["role"] == "user")
    if prompt:
        if n_user >= MAX_USER_MSGS:
            st.warning("Chat limit reached for this session. Refresh the page to start again.")
        else:
            prompt = prompt[:MAX_CHARS]
            msgs.append({"role": "user", "content": prompt})
            with box, st.chat_message("user"):
                st.markdown(prompt)
            with box, st.chat_message("assistant"):
                live = get_live(cities)            # cached 10 min, shared by all users
                client = _client()
                reply = None
                if client is not None:
                    system = (SYSTEM + "\n" + build_context(daily, city, aqi_cat)
                              + "\n\n" + live_block(live, aqi_cat))
                    try:
                        reply = st.write_stream(_stream_reply(client, system, _history(msgs)))
                    except Exception as e:
                        _note(e)
                        reply = None               # fall through to the offline answer
                if not reply:
                    reply = _offline_for(daily, city, live, aqi_cat, prompt)
                    st.markdown(reply)
                if _secret("ADVISOR_DEBUG") and st.session_state.get("adv_err"):
                    st.caption("AI error: " + st.session_state.pop("adv_err"))
            msgs.append({"role": "assistant", "content": reply if isinstance(reply, str) else str(reply)})

    st.caption("General information only, not medical advice. Live values are modelled estimates (Open-Meteo, "
               "refreshed about every 10 minutes); charts use the dashboard's daily data.")