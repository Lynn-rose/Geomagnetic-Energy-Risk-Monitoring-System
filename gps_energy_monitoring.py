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

# Collect ALL kp values across lines
kp_values = []
for line in forecast_text.splitlines():
    if "Kp indices" in line:
        numbers = re.findall(r"\d+", line)
        kp_values.extend(map(int, numbers))

# Sidebar settings
st.sidebar.header("⚙️ Settings")
horizon_options = list(range(1, 9))  # up to 24h ahead (8 steps × 3h)
selected_horizon = st.sidebar.selectbox("Forecast horizon (3h per step):", horizon_options, index=0)

# ----------------------------
# Load world cities dataset (safe GitHub source)
# ----------------------------
@st.cache_data
def load_world_cities():
    url = "https://raw.githubusercontent.com/datasets/world-cities/master/data/world-cities.csv"
    df = pd.read_csv(url)
    return df

world_cities = load_world_cities()

# Sidebar selection
st.sidebar.subheader("🌍 Region Selection")
region_mode = st.sidebar.radio("View:", ["Global", "By Country & City"])

if region_mode == "Global":
    selected_region = "Global"
    lat, lon = 20, 0  # Default global view
else:
    selected_country = st.sidebar.selectbox("Select Country:", sorted(world_cities["country"].unique()))
    filtered_cities = world_cities[world_cities["country"] == selected_country]
    selected_city = st.sidebar.selectbox("Select City:", sorted(filtered_cities["name"].unique()))
    city_row = filtered_cities[filtered_cities["name"] == selected_city].iloc[0]
    selected_region = f"{selected_city}, {selected_country}"
    lat, lon = city_row["latitude"], city_row["longitude"]

# ----------------------------
# Forecast selection
# ----------------------------
if kp_values:
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
    for _, row in world_cities.iterrows():
        risk = gps_risk(kp_value, row["latitude"])
        data.append({
            "City": row["name"],
            "Country": row["country"],
            "Latitude": row["latitude"],
            "Longitude": row["longitude"],
            "Risk": risk
        })
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
    view_state = pdk.ViewState(latitude=20, longitude=0, zoom=1.5, pitch=0)
else:
    view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=5, pitch=20)

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
            tooltip={"text": "{City}, {Country}: {Risk}"}
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
            tooltip={"text": "{City}, {Country}: {Risk}"}
        )
    )

# ----------------------------
# Refresh info
# ----------------------------
st.caption(f"⏱️ Last refreshed at: {st.session_state.last_refreshed.strftime('%Y-%m-%d %H:%M:%S')}")
next_refresh_time = st.session_state.last_refreshed + timedelta(milliseconds=interval_ms)
seconds_remaining = int((next_refresh_time - datetime.now()).total_seconds())
if seconds_remaining < 0:
    seconds_remaining = 0
mins, secs = divmod(seconds_remaining, 60)
st.markdown(f"⌛ Next auto-refresh in: **{mins}m {secs:02d}s**")
