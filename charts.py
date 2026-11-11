"""
charts.py - simple, labelled charts used by every page (so all pages look and read the same way).

Rules followed everywhere:
    * one message per chart, title written as a plain question or statement
    * every bar shows its number; colours mean the US AQI category (green = good ... maroon = hazardous)
    * no heatmaps, scatter clouds, box plots or polar charts
"""
import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import AQI_COLORS, AQI_LABELS, aqi_cat, show

NEUTRAL = "#5b6b82"
SOFT = "#a9b4c4"
GOOD_GREEN = "#1e9e5a"
BAD_RED = "#d64545"

# PM2.5 (µg/m³) -> US AQI category, US EPA 2024 breakpoints on 24-hour averages
_PM25_TOPS = [9.0, 35.4, 55.4, 125.4, 225.4]
PM25_SAFE, PM25_UNHEALTHY = 35.4, 55.4   # PM2.5 at AQI 100 and AQI 150

BLOCKS = ["12-3 AM", "3-6 AM", "6-9 AM", "9 AM-12 PM", "12-3 PM", "3-6 PM", "6-9 PM", "9 PM-12 AM"]


def pm25_cat(v):
    if v is None or pd.isna(v):
        return "n/a"
    return AQI_LABELS[int(np.searchsorted(_PM25_TOPS, float(v), side="left"))]


def colour_for(values, scale):
    """scale: 'aqi' (values are AQI), 'pm25' (values are PM2.5), a single colour, or a list of colours."""
    vals = list(values)
    if scale == "aqi":
        return [AQI_COLORS.get(aqi_cat(v), SOFT) for v in vals]
    if scale == "pm25":
        return [AQI_COLORS.get(pm25_cat(v), SOFT) for v in vals]
    if isinstance(scale, (list, tuple, np.ndarray, pd.Series)):
        return list(scale)
    return [scale or NEUTRAL] * len(vals)


def legend_note(scale):
    """One-line colour key shown under charts coloured by category."""
    if scale not in ("aqi", "pm25"):
        return
    chips = "".join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px">'
                    f'<span style="width:11px;height:11px;border-radius:3px;background:{AQI_COLORS[c]}"></span>'
                    f'{html.escape(c)}</span>' for c in AQI_LABELS)
    st.markdown(f'<div style="font-size:.78rem;opacity:.8;margin:-6px 0 14px 0;line-height:1.9">Colour = air '
                f'quality category: {chips}</div>', unsafe_allow_html=True)


def bar(labels, values, title, *, horizontal=True, scale=None, fmt="{:.0f}", suffix="", h=None, ref=None,
        highlight=None, hover=None, x_title="", y_title="", key_note=True, value_range=None, text=None):
    """Single-series bar chart with a number on every bar.
    ref = [(value, label, colour), ...] dashed reference lines (e.g. WHO limit)."""
    labels = [str(x) for x in labels]
    values = [float(v) if v is not None and not pd.isna(v) else np.nan for v in values]
    cols = colour_for(values, scale)
    if highlight is not None:   # grey out everything except the highlighted labels
        hl = set([highlight] if isinstance(highlight, str) else highlight)
        cols = [c if l in hl else "#c9cfd8" for c, l in zip(cols, labels)]
    if text is None:
        text = ["" if pd.isna(v) else fmt.format(v) + suffix for v in values]
    hov = hover if hover is not None else [f"{l}: {t}" for l, t in zip(labels, text)]
    lo_v, hi_v = min(0.0, float(np.nanmin(values + [0]))), float(np.nanmax(values + [1]))
    pad_lo = min(lo_v * 1.3, -0.28 * max(hi_v, 1e-9)) if lo_v < 0 else 0   # room for labels on negative bars
    auto_rng = [pad_lo, hi_v * (1.18 if horizontal else 1.2) if hi_v > 0 else 1]
    if horizontal:
        fig = go.Figure(go.Bar(y=labels, x=values, orientation="h", marker_color=cols, text=text,
                               textposition="outside", cliponaxis=False, hovertext=hov, hoverinfo="text"))
        fig.update_yaxes(autorange="reversed", dtick=1, title_text=y_title)   # first label on top
        fig.update_xaxes(title_text=x_title, showgrid=False, showticklabels=False,
                         range=value_range or auto_rng)
        h = h or max(260, 26 * len(labels) + 90)
    else:
        fig = go.Figure(go.Bar(x=labels, y=values, marker_color=cols, text=text, textposition="outside",
                               cliponaxis=False, hovertext=hov, hoverinfo="text"))
        fig.update_xaxes(type="category", title_text=x_title)
        fig.update_yaxes(title_text=y_title, showgrid=True,
                         range=value_range or auto_rng)
        h = h or 340
    for v, lab, colr in (ref or []):
        if horizontal:   # no text on the line (it would sit on a bar label); each note explains the line
            fig.add_vline(x=v, line_dash="dash", line_color=colr, line_width=2)
        else:
            fig.add_hline(y=v, line_dash="dash", line_color=colr, line_width=2,
                          annotation_text=lab, annotation_position="top left", annotation_font_color=colr,
                          annotation_font_size=11)
    fig.update_traces(textfont_size=12)
    fig.update_layout(title=title, bargap=0.28)
    show(fig, h=h, legend="off")
    if key_note:
        legend_note(scale)


def grouped(categories, series, title, *, colors=None, fmt="{:.0f}", suffix="", h=None, horizontal=False,
            y_title="", order=None, texts=None):
    """series = {name: values}; a few bars side by side per category, numbers on bars."""
    fig = go.Figure()
    palette = colors or ["#a9b4c4", "#5b6b82", "#1b2a41", "#eb6834"]
    for i, (name, vals) in enumerate(series.items()):
        txt = (texts or {}).get(name) or ["" if pd.isna(v) else fmt.format(v) + suffix for v in vals]
        kw = dict(y=categories, x=vals, orientation="h") if horizontal else dict(x=categories, y=vals)
        fig.add_trace(go.Bar(name=name, marker_color=palette[i % len(palette)], text=txt, textposition="outside",
                             cliponaxis=False, **kw))
    fig.update_traces(textfont_size=11)
    fig.update_layout(title=title, barmode="group", bargap=0.25, bargroupgap=0.06,
                      uniformtext=dict(minsize=10, mode="show"))
    if horizontal:
        mx = max([float(np.nanmax(list(v) + [0])) for v in series.values()] + [1])
        fig.update_yaxes(autorange="reversed", dtick=1)
        fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, mx * (1.55 if texts else 1.2)])
    else:
        fig.update_xaxes(type="category", categoryorder="array", categoryarray=order or list(categories))
        fig.update_yaxes(title_text=y_title)
    show(fig, h=h or (max(300, 34 * len(categories) + 120) if horizontal else 360), legend="top")


def stacked(categories, parts, title, *, colors, h=None, suffix="%"):
    """100% stacked horizontal bars; parts = {segment: values (shares that add to 100)}."""
    fig = go.Figure()
    for name, vals in parts.items():
        vals = [0 if pd.isna(v) else v for v in vals]
        txt = [f"{v:.0f}{suffix}" if v >= 9 else "" for v in vals]
        fig.add_trace(go.Bar(name=name, y=categories, x=vals, orientation="h", marker_color=colors.get(name, SOFT),
                             text=txt, textposition="inside", insidetextanchor="middle", textangle=0,
                             hovertemplate=f"{name}: " + "%{x:.0f}" + suffix + "<extra>%{y}</extra>"))
    fig.update_layout(title=title, barmode="stack", bargap=0.25, legend=dict(traceorder="normal"))
    fig.update_yaxes(autorange="reversed", dtick=1)
    fig.update_xaxes(range=[0, 100], ticksuffix="%", showgrid=False)
    show(fig, h=h or max(280, 28 * len(categories) + 130), legend="top")


def donut(labels, values, title, *, colors, center="", h=380, pct=True):
    """Donut with the percentage inside each big slice and a legend that names every slice with its share."""
    vals = [0 if pd.isna(v) else float(v) for v in values]
    tot = sum(vals) or 1
    keep = [(l, v, c) for l, v, c in zip(labels, vals, colors) if v > 0]
    names = [f"{k[0]} ({k[1] / tot * 100:.0f}%)" if pct else f"{k[0]} ({k[1]:,.0f})" for k in keep]
    inside = [f"{k[1] / tot * 100:.0f}%" if k[1] / tot >= 0.06 else "" for k in keep]
    fig = go.Figure(go.Pie(labels=names, values=[k[1] for k in keep], hole=0.56, sort=False, direction="clockwise",
                           marker=dict(colors=[k[2] for k in keep], line=dict(color="white", width=2)),
                           text=inside, textinfo="text", textposition="inside", insidetextorientation="horizontal",
                           hovertemplate="%{label}<extra></extra>"))
    if center:
        fig.add_annotation(text=center, showarrow=False, font=dict(size=14), x=0.5, y=0.5)
    fig.update_traces(textfont=dict(size=13, color="white"))
    fig.update_layout(title=title)
    show(fig, h=h, legend="right")


def gauge(value, title, *, max_value=300, suffix="", h=300):
    """Speedometer dial with the US AQI bands."""
    v = float(value)
    bands = [(0, 50), (50, 100), (100, 150), (150, 200), (200, 300), (300, max(max_value, 301))]
    steps = [dict(range=[a, min(b, max_value)], color=AQI_COLORS[l]) for (a, b), l in zip(bands, AQI_LABELS)
             if a < max_value]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=v, number=dict(suffix=suffix, font=dict(size=46), valueformat=".0f"),
        gauge=dict(axis=dict(range=[0, max_value], tickvals=[0, 50, 100, 150, 200, 300]),
                   bar=dict(color="#1b1f2a", thickness=0.22), steps=steps,
                   threshold=dict(line=dict(color="#1b1f2a", width=4), thickness=0.9, value=v))))
    fig.update_layout(title=title)
    show(fig, h=h, legend="off")
    st.markdown(f'<div style="text-align:center;margin:-18px 0 14px 0;font-weight:600;color:'
                f'{AQI_COLORS.get(aqi_cat(v), "#555")}">{html.escape(aqi_cat(v))}</div>', unsafe_allow_html=True)


def lines(x, series, title, *, colors=None, y_title="", h=360, markers=False, ref=None, widths=None,
          dashes=None, x_title=""):
    """series = {name: values}; plain lines, optional dashed reference lines [(value, label, colour)]."""
    fig = go.Figure()
    palette = colors or ["#d64545", "#2a78d6", "#7a8496", "#eb6834", "#0f766e", "#7c3aed", "#a16207", "#475569"]
    for i, (name, vals) in enumerate(series.items()):
        fig.add_trace(go.Scatter(x=x, y=vals, name=name, mode="lines+markers" if markers else "lines",
                                 line=dict(color=palette[i % len(palette)],
                                           width=(widths or {}).get(name, 2.6),
                                           dash=(dashes or {}).get(name, "solid"))))
    for v, lab, colr in (ref or []):
        fig.add_hline(y=v, line_dash="dash", line_color=colr, annotation_text=lab,
                      annotation_position="top left", annotation_font_color=colr, annotation_font_size=11)
    fig.update_layout(title=title, hovermode="x unified")
    fig.update_yaxes(title_text=y_title, rangemode="tozero")
    fig.update_xaxes(title_text=x_title)
    if len(x) and isinstance(list(x)[0], str) and len(x) > 12:   # e.g. 24 hour labels: show every 3rd, flat
        fig.update_xaxes(type="category", tickangle=0, tickmode="array", tickvals=list(x)[::3])
    show(fig, h=h, legend="top" if len(series) > 1 else "off")


def tiles(items, title):
    """Row of coloured tiles: items = [(top_text, big_value, bottom_text, colour)]."""
    cells = "".join(
        f'<div style="flex:1 1 110px;min-width:105px;border-radius:12px;padding:12px 10px;text-align:center;'
        f'background:{c};color:{"#1b1f2a" if c in (AQI_COLORS["Good"], AQI_COLORS["Moderate"]) else "#fff"};'
        f'box-shadow:0 2px 8px rgba(0,0,0,.12)"><div style="font-size:.8rem;font-weight:600">{html.escape(a)}</div>'
        f'<div style="font-size:1.7rem;font-weight:800;line-height:1.2">{html.escape(b)}</div>'
        f'<div style="font-size:.74rem;opacity:.95">{html.escape(s)}</div></div>'
        for a, b, s, c in items)
    st.markdown(f'<div style="font-weight:600;font-size:15px;margin:6px 0 10px 0">{html.escape(title)}</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px">{cells}</div>',
                unsafe_allow_html=True)


def note(text):
    """Plain-language line under a chart (bold with **...**)."""
    from common import explain
    explain(text)
