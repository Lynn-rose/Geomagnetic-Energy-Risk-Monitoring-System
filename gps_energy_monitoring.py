import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import re

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="SolarShield GPS Risk Monitor", layout="wide")

# ----------------------------
# Config
# ----------------------------
interval_ms = 60000  # 1 minute

# ----------------------------
# Session state init
# ----------------------------
if "last_refreshed" not in st.session_state:
    st.session_state.last_refreshed = None

# ----------------------------
# Auto-refresh trigger (causes the script to rerun every interval_ms)
# ----------------------------
count = st_autorefresh(interval=interval_ms, limit=None, key="data_refresh")

# ----------------------------
# Manual refresh button
# ----------------------------
if st.button("🔄 Refresh Now"):
    # rerun will happen automatically; we'll update last_refreshed after successful fetch below
    st.experimental_rerun()

# ----------------------------
# Fetch current Kp (1-minute JSON) - wrapped in try to avoid hard crash
# ----------------------------
url_current = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
kp_index = None
time_tag = None
fetch_ok = False

try:
    df_current = pd.read_json(url_current)
    latest = df_current.tail(1).iloc[0]
    kp_index = latest["kp_index"]
    time_tag = latest["time_tag"]
    fetch_ok = True
except Exception as e:
    st.warning("Warning: could not fetch current Kp index. Showing last-known / placeholder values.")
    # keep kp_index as None (build_df will handle None by treating as Safe); you can also set a default

# ----------------------------
# Fetch forecast Kp (3-day text) and parse Kp indices line
# ----------------------------
url_forecast_text = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"
kp_forecast = None
forecast_time = "Unavailable"
kp_values = []

try:
    forecast_text = requests.get(url_forecast_text, timeout=10).text
    # Find line(s) that reference "Kp indices" (format may vary — this is best-effort)
    kp_lines = [line for line in forecast_text.splitlines() if "Kp indices" in line or "Kp index" in line]
    if kp_lines:
        # extract all integers on the first matching line
        kp_values = list(map(int, re.findall(r"\d+", kp_lines[0])))
    else:
        kp_values = []
except Exception:
    kp_values = []

# Sidebar controls
st.sidebar.header("⚙️ Settings")
# Forecast horizon options: step = 3 hours, allow up to number of values parsed (or 8 steps default)
max_steps = max(1, len(kp_values))  # at least 1
horizon_options = list(range(1, max_steps + 1))
selected_horizon = st.sidebar.selectbox("Forecast step (3h per step):", horizon_options, index=0)

if kp_values:
    # choose the horizon index safely
    idx = min(selected_horizon - 1, len(kp_values) - 1)
    kp_forecast = kp_values[idx]
    forecast_time = f"{(idx + 1) * 3} hours ahead"
else:
    # fallback: if no parsed forecast, use current kp if available
    kp_forecast = kp_index
    forecast_time = "Unavailable"

# ----------------------------
# If we succeeded in fetching current/forecast, update last_refreshed timestamp
# ----------------------------
# We'll set last_refreshed on every successful fetch so manual and auto refresh show correctly
if fetch_ok or kp_values:
    st.session_state.last_refreshed = datetime.now()

# ----------------------------
# Risk function
# ----------------------------
def gps_risk(kp, latitude):
    # if kp is None, treat as Safe (you can change this)
    if kp is None:
        return "Safe"
    lat = abs(latitude)
    if lat >= 60:
        if kp >= 4:
            return "High Risk"
        elif kp >= 2:
            return "Caution"
        else:
            return "Safe"
    elif 30 <= lat < 60:
        if kp >= 6:
            return "High Risk"
        elif kp >= 4:
            return "Caution"
        else:
            return "Safe"
    else:
        if kp >= 8:
            return "High Risk"
        elif kp >= 6:
            return "Caution"
        else:
            return "Safe"

# ----------------------------
# Regions (your full list)
# ----------------------------
regions = {
    # ---- India ----
    "Hyderabad, India": (17.4, 78.5),
    "New Delhi, India": (28.6, 77.2),
    "Bangalore, India": (12.97, 77.59),
    "Chennai, India": (13.08, 80.27),
    "Nilgiris District, Tamil Nadu": (11.4, 77.0),
    "Mumbai, India": (19.1, 72.9),
    "Kolkata, India": (22.6, 88.4),

    # ---- Africa ----
    "Nairobi, Kenya": (-1.3, 36.8),
    "Dodoma, Tanzania": (-6.17, 35.74),
    "Cairo, Egypt": (30.0, 31.2),
    "Cape Town, South Africa": (-33.9, 18.4),
    "Lagos, Nigeria": (6.5, 3.4),
    "Mombasa, Kenya": (-4.0, 39.7),
    "Dar es Salaam, Tanzania": (-6.8, 39.3),
    "Dakar, Senegal": (14.7, -17.5),

    # ---- Europe ----
    "Oslo, Norway": (59.9, 10.8),
    "London, UK": (51.5, -0.1),
    "Paris, France": (48.9, 2.4),
    "Berlin, Germany": (52.5, 13.4),
    "Moscow, Russia": (55.8, 37.6),
    "Lisbon, Portugal": (38.7, -9.1),
    "Athens, Greece": (37.9, 23.7),
    "Istanbul, Turkey": (41.0, 28.9),

    # ---- North America ----
    "Anchorage, Alaska": (61.2, -149.9),
    "New York, USA": (40.7, -74.0),
    "Los Angeles, USA": (34.1, -118.2),
    "Miami, USA": (25.8, -80.2),
    "Toronto, Canada": (43.7, -79.4),
    "Vancouver, Canada": (49.3, -123.1),
    "Mexico City, Mexico": (19.4, -99.1),
    "Havana, Cuba": (23.1, -82.4),

    # ---- South America ----
    "São Paulo, Brazil": (-23.5, -46.6),
    "Buenos Aires, Argentina": (-34.6, -58.4),
    "Lima, Peru": (-12.0, -77.0),
    "Bogotá, Colombia": (4.7, -74.1),
    "Santiago, Chile": (-33.4, -70.6),
    "Rio de Janeiro, Brazil": (-22.9, -43.2),
    "Montevideo, Uruguay": (-34.9, -56.2),

    # ---- Asia-Pacific ----
    "Sydney, Australia": (-33.9, 151.2),
    "Tokyo, Japan": (35.7, 139.7),
    "Beijing, China": (39.9, 116.4),
    "Seoul, South Korea": (37.6, 127.0),
    "Jakarta, Indonesia": (-6.2, 106.8),
    "Manila, Philippines": (14.6, 121.0),
    "Bangkok, Thailand": (13.7, 100.5),
    "Auckland, New Zealand": (-36.8, 174.8),
}

# ----------------------------
# Region dropdown (sidebar)
# ----------------------------
region_names = ["All Regions"] + list(regions.keys())
selected_region = st.sidebar.selectbox("🌍 Select Region:", region_names, index=0)

# ----------------------------
# Build DataFrames
# ----------------------------
def build_df(kp_value):
    data = []
    for city, (lat, lon) in regions.items():
        risk = gps_risk(kp_value, lat)
        data.append({"City": city, "Latitude": lat, "Longitude": lon, "Risk": risk})
    df = pd.DataFrame(data)
    color_map = {"Safe": [0, 200, 0], "Caution": [255, 165, 0], "High Risk": [200, 0, 0]}
    df["Color"] = df["Risk"].map(color_map)
    return df

risk_df_current = build_df(kp_index)
risk_df_forecast = build_df(kp_forecast)

# Filter by selected region
if selected_region != "All Regions":
    # keep only the chosen city row (if it exists)
    risk_df_current = risk_df_current[risk_df_current["City"] == selected_region]
    risk_df_forecast = risk_df_forecast[risk_df_forecast["City"] == selected_region]

# ----------------------------
# Helpers: compute map view state from a df
# ----------------------------
def make_view_state(df, default_lat=20, default_lon=0):
    if df is None or df.empty:
        return pdk.ViewState(latitude=default_lat, longitude=default_lon, zoom=1.5, pitch=0)
    if len(df) == 1:
        lat = float(df.iloc[0]["Latitude"])
        lon = float(df.iloc[0]["Longitude"])
        return pdk.ViewState(latitude=lat, longitude=lon, zoom=6, pitch=0)
    # multiple cities: center on mean
    return pdk.ViewState(latitude=float(df["Latitude"].mean()), longitude=float(df["Longitude"].mean()), zoom=1.5, pitch=0)

# ----------------------------
# Layout
# ----------------------------
st.title("🛰️ SolarShield - GPS Risk Monitor")

# header showing kp values
col_header1, col_header2 = st.columns(2)
with col_header1:
    st.subheader(f"📡 Current Kp: {kp_index} (Time: {time_tag})")
with col_header2:
    st.subheader(f"🔮 Forecast Kp: {kp_forecast} (Horizon: {forecast_time})")

# two main columns: current and forecast
col1, col2 = st.columns(2)

# highlight function for table
def highlight_risk(val):
    if val == "High Risk":
        return "background-color: red; color: white"
    elif val == "Caution":
        return "background-color: orange; color: black"
    else:
        return "background-color: lightgreen; color: black"

# Current panel
with col1:
    st.subheader("📊 Current Risks")
    st.dataframe(risk_df_current.drop(columns=["Color"]).style.applymap(highlight_risk, subset=["Risk"]))
    st.subheader("🌍 Current Risk Map")
    view_current = make_view_state(risk_df_current)
    layer_current = pdk.Layer(
        "ScatterplotLayer",
        data=risk_df_current,
        get_position=["Longitude", "Latitude"],
        get_color="Color",
        get_radius=200000,
        pickable=True,
    )
    st.pydeck_chart(pdk.Deck(layers=[layer_current], initial_view_state=view_current, tooltip={"text": "{City}: {Risk}"}))

# Forecast panel
with col2:
    st.subheader("📈 Forecast Risks")
    st.dataframe(risk_df_forecast.drop(columns=["Color"]).style.applymap(highlight_risk, subset=["Risk"]))
    st.subheader("🌍 Forecast Risk Map")
    view_forecast = make_view_state(risk_df_forecast)
    layer_forecast = pdk.Layer(
        "ScatterplotLayer",
        data=risk_df_forecast,
        get_position=["Longitude", "Latitude"],
        get_color="Color",
        get_radius=200000,
        pickable=True,
    )
    st.pydeck_chart(pdk.Deck(layers=[layer_forecast], initial_view_state=view_forecast, tooltip={"text": "{City}: {Risk}"}))

# ----------------------------
# Refresh info (bottom)
# ----------------------------
st.markdown("---")
if st.session_state.last_refreshed:
    st.caption(f"⏱️ Last refreshed at: {st.session_state.last_refreshed.strftime('%Y-%m-%d %H:%M:%S')}")
else:
    st.caption("⏱️ Last refreshed at: N/A")

next_refresh_time = (st.session_state.last_refreshed or datetime.now()) + timedelta(milliseconds=interval_ms)
seconds_remaining = int((next_refresh_time - datetime.now()).total_seconds())
if seconds_remaining < 0:
    seconds_remaining = 0
mins, secs = divmod(seconds_remaining, 60)
st.markdown(f"⌛ Next auto-refresh in: **{mins}m {secs:02d}s**")
