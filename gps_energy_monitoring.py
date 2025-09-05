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
# Initialize session state
# ----------------------------
if "last_refreshed" not in st.session_state:
    st.session_state.last_refreshed = datetime.now()
if "manual_refresh" not in st.session_state:
    st.session_state.manual_refresh = False

# ----------------------------
# Auto-refresh trigger
# ----------------------------
count = st_autorefresh(interval=interval_ms, limit=None, key="data_refresh")
if count > 0:
    st.session_state.last_refreshed = datetime.now()

# ----------------------------
# Manual refresh button
# ----------------------------
if st.button("🔄 Refresh Now"):
    st.session_state.manual_refresh = True

if st.session_state.manual_refresh:
    st.session_state.manual_refresh = False
    st.session_state.last_refreshed = datetime.now()

# ----------------------------
# Fetch NOAA Kp Index (current, 1-minute data)
# ----------------------------
url_current = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
df_current = pd.read_json(url_current)
latest = df_current.tail(1).iloc[0]
kp_index = latest["kp_index"]
time_tag = latest["time_tag"]

# ----------------------------
# Fetch NOAA Kp Forecast (3-day text file)
# ----------------------------
url_forecast = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"
forecast_text = requests.get(url_forecast).text

# Extract kp lines
kp_lines = [line for line in forecast_text.splitlines() if "Kp indices" in line]

# Sidebar settings
st.sidebar.header("⚙️ Settings")
horizon_options = list(range(1, 9))  # up to 24h ahead (8 steps × 3h)
selected_horizon = st.sidebar.selectbox("Forecast horizon (3h per step):", horizon_options, index=0)

# ----------------------------
# Regions
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

selected_region = st.sidebar.selectbox("🌍 Focus on region:", ["Global"] + list(regions.keys()))

# ----------------------------
# Forecast parsing
# ----------------------------
if kp_lines:
    kp_values = re.findall(r"\d+", kp_lines[0])
    kp_values = list(map(int, kp_values))

    if selected_horizon <= len(kp_values):
        kp_forecast = kp_values[selected_horizon - 1]
    else:
        kp_forecast = kp_values[-1]

    forecast_time = f"{selected_horizon * 3} hours ahead"
else:
    kp_forecast = kp_index
    forecast_time = "Unavailable"

# ----------------------------
# Risk function
# ----------------------------
def gps_risk(kp, latitude):
    lat = abs(latitude)
    if lat >= 60:
        if kp >= 4: return "High Risk"
        elif kp >= 2: return "Caution"
        else: return "Safe"
    elif 30 <= lat < 60:
        if kp >= 6: return "High Risk"
        elif kp >= 4: return "Caution"
        else: return "Safe"
    else:
        if kp >= 8: return "High Risk"
        elif kp >= 6: return "Caution"
        else: return "Safe"

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

# ----------------------------
# Layout
# ----------------------------
st.title("🛰️ SolarShield - GPS Risk Monitor")

col_main1, col_main2 = st.columns(2)

# Map zoom logic
if selected_region == "Global":
    view_state = pdk.ViewState(latitude=20, longitude=0, zoom=1.5)
else:
    lat, lon = regions[selected_region]
    view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=4)

# ---- Current risks ----
with col_main1:
    st.subheader(f"📊 Current Risks (Kp={kp_index}, Time={time_tag})")

    def highlight_risk(val):
        if val == "High Risk":
            return "background-color: red; color: white"
        elif val == "Caution":
            return "background-color: orange; color: black"
        else:
            return "background-color: green; color: white"

    st.dataframe(
        risk_df_current.drop(columns=["Color"]).style.applymap(highlight_risk, subset=["Risk"])
    )

    st.subheader("🌍 Current Risk Map")
    st.pydeck_chart(
        pdk.Deck(
            layers=[pdk.Layer(
                "ScatterplotLayer",
                data=risk_df_current,
                get_position=["Longitude", "Latitude"],
                get_color="Color",
                get_radius=200000,
                pickable=True,
            )],
            initial_view_state=view_state,
            tooltip={"text": "{City}: {Risk}"}
        )
    )

# ---- Forecast risks ----
with col_main2:
    st.subheader(f"📈 Forecast Risks (Kp={kp_forecast}, Horizon={forecast_time})")

    st.dataframe(
        risk_df_forecast.drop(columns=["Color"]).style.applymap(highlight_risk, subset=["Risk"])
    )

    st.subheader("🌍 Forecast Risk Map")
    st.pydeck_chart(
        pdk.Deck(
            layers=[pdk.Layer(
                "ScatterplotLayer",
                data=risk_df_forecast,
                get_position=["Longitude", "Latitude"],
                get_color="Color",
                get_radius=200000,
                pickable=True,
            )],
            initial_view_state=view_state,
            tooltip={"text": "{City}: {Risk}"}
        )
    )

# ----------------------------
# Refresh info
# ----------------------------
st.caption(f"⏱️ Last refreshed at: {st.session_state.last_refreshed.strftime('%Y-%m-%d %H:%M:%S')}")
next_refresh_time = st.session_state.last_refreshed + timedelta(milliseconds=interval_ms)
seconds_remaining = int((next_refresh_time - datetime.now()).total_seconds())
if seconds_remaining < 0: seconds_remaining = 0
mins, secs = divmod(seconds_remaining, 60)
st.markdown(f"⌛ Next auto-refresh in: **{mins}m {secs:02d}s**")
