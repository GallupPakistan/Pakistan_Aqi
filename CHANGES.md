# What was fixed (11 Nov 2026)

The three CSV files are unchanged. They were checked: 34 cities x 1,389 days (1 Jan 2023 to 20 Oct 2026),
no gaps, no duplicates, hourly file matches the daily file exactly, and known events (e.g. the Lahore smog
peak of 13-15 Nov 2024) appear where they should.

## Wrong or misleading numbers
- **Year-on-year insight** compared 2026 (Jan to 20 Oct only) with the whole of 2025, including smog-season
  Nov-Dec. It showed -1.8%; on the same dates it is +9.6%. It now always compares the same calendar window.
- **Forecast method ranking** used one 30-day test window. A calm Sep-Oct window made a flat model "best",
  which then predicted a flat AQI straight into smog season. Methods are now scored on three windows
  (recent days plus the same dates one and two years earlier) and averaged.
- **Banner leak:** after opening Forecasting, every other page kept showing "AQI ... (forecast average)".
  The background AQI is now reset on every run.
- **WHO guideline:** a multi-day average was compared with the WHO 24-hour limit. KPI now shows the share of
  days above 15 µg/m³; the ranking chart shows both the annual (5) and 24-hour (15) guidelines.
- **Cities page** invented an AQI (the overall mean) for cities with no data under the filters, and ignored
  the Province filter. Both fixed.
- **Rain insight** said "X% lower" even when rainy days were higher.
- **Forecast "Tomorrow" / "Today"** referred to the day after the last data (21 Oct), not today. Relabelled
  "First forecast day" and "Last data", with a note saying where the data ends.
- AQI above 500 (off the US AQI scale, dust-driven) is now marked with * and explained.
- Category name corrected to the official "Unhealthy for Sensitive Groups".

## Text and labels
- Data-source placeholder replaced (Open-Meteo / Copernicus CAMS); the period is read from the data.
- Overview scope text describes the whole file; highlights say they follow the filters.
- Note on the Hourly page that Year and AQI-category filters don't apply to the hourly file.
- Seasons shown in calendar order, readable correlation labels, credits punctuation fixed.

## UI
- Sidebar filter pills: unselected options were white text on white (unreadable) on current Streamlit.
- Top tab bar: radio dots showed and icons were missing on current Streamlit. CSS now works on old and new.
- "Stagnant (<5 km/h)" broke the HTML of the insights box; text is now escaped.
- Forecast calendar showed "null" in empty boxes; band labels overlapped; "Last data" label hit the legend.
- All city names visible on the city AQI chart; distance chart sorted nearest-first.
- Truncated KPI values (worst season, peak-day category) shortened.
- Neutral accent colour for sliders/tags/tabs instead of Streamlit's default red (`.streamlit/config.toml`).

## To check on your side
- Confirm the data source line in `app.py` (`DATA_SOURCE`) matches how the CSVs were downloaded.
- The city map needs internet for the OpenStreetMap tiles.

## Update (11 Nov, 11:05)
- Full-screen smog layers no longer move (`ANIMATE_PAGE_SMOG = False` in theme.py). On some Windows/Chrome
  graphics drivers the moving layers left the sidebar and top of the page blank. Set it to True to bring the
  movement back.
- Tab bar: on some Streamlit versions the tab names were hidden along with the radio dot. Fixed.

## New analysis pages (11 Nov, v4) - new file `page_analysis.py`
- **City Report:** one city, full history: national rank, PM2.5 vs WHO, unhealthy days, trend, main
  pollutant, episodes, a written summary, monthly comparison with province and country, a calendar of every
  day, category mix by year, time-of-day profile, comparison with other cities in the province, CSV download.
- **Sources & Trends:**
  - *What drives the pollution:* for every day, which pollutant set the AQI (PM2.5 = smoke, PM10 = dust,
    or ozone), city by city and month by month, plus combustion gases (NO2, CO, SO2).
  - *Is it getting better or worse:* trend per city with the seasons removed (Theil-Sen slope, Mann-Kendall
    test corrected for month-to-month persistence), national trend, and smog season by smog season.
- **Smog Episodes:** every run of consecutive days above an AQI level (150/200/300, length adjustable),
  labelled smog, dust or ozone; timeline, cities affected per day, month of onset, full table, CSV download.
- No new packages needed (the statistics are written with numpy).

### Findings worth knowing
- Islamabad and Rawalpindi have identical pollution values (same model grid cell); only weather differs.
- Skardu's very high AQI days are driven by modelled ozone, not particles; treat as a model signal.
- Nawabshah's top AQI rank comes from modelled dust (PM10), not smoke.
- 20 of 34 cities show a statistically clear rise in PM2.5 after removing the seasons; the record is under
  four years and comes from a model, so trends are indicative.

## v5 (11 Nov) - simpler visuals, sidebar navigation, 10 visuals per page
- **Navigation moved to the sidebar** (stays visible while scrolling).
- **Every page now has exactly 10 numbered visuals**, each answering one plain question, no two on the same
  page saying the same thing. New shared file `charts.py` (labelled bars, donuts, gauge, simple lines).
- Removed hard-to-read charts: correlation heatmap, box plot, scatter, polar clock, month x hour heatmap.
- Every bar shows its number; colours follow the official AQI categories; a "How to read this chart" note
  under every visual.
- New file `page_overview.py` (Overview page).
- **Data fix:** the hourly file's AQI is a rolling 24-hour value, so it cannot show which hour is worst.
  Hour-of-day charts and "safe / unhealthy hours" now use hourly PM2.5 (with the same EPA category limits).
- Fixed an insight that said "cold days are dirtiest" when the data shows cool (10-20°C) days are.

## v6 (11 Nov)
- AQI values are rounded to whole numbers before they are put in categories (EPA rule), so 50.3 counts as
  Good, not Moderate. Categories, the category filter and "AQI above 150" counts now always agree (affected
  380 of 47,226 days).
- Includes pakistan_aqi.py v3 (downloader): aqi_category from the daily average, aqi_category_peak from the
  worst hour, and a check for missing days.

## v7 (11 Nov) - filters
- City choices now follow the Province filter everywhere (sidebar trend cities, City Report, Hourly chart 5,
  Cities distance chart, Forecasting). Your own picks are kept while they are in the selected provinces;
  if none are left, the most polluted cities of the new provinces are used.
- Choices are remembered when you switch pages.
- "Top N cities" now controls the ranking charts on Overview, Daily and Sources & Trends.
- Every page shows which sidebar filters apply to it (blue) and which do not (grey, with the reason).
- An empty filter result no longer blocks pages that do not use those filters (City Report, Hourly,
  Episodes, Forecasting).
