import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

# ----------------------------
# Page config must be first
# ----------------------------
st.set_page_config(page_title="SolarShield GPS Risk Monitor", layout="wide")

# ----------------------------
# Config
# ----------------------------
interval_ms = 300000  # 5 minutes

# ----------------------------
# Initialize session state
# ----------------------------
if "last_refreshed" not in st.session_state:
    st.session_state.last_refreshed = datetime.now()

# ----------------------------
# Auto-refresh trigger
# ----------------------------
count = st_autorefresh(interval=interval_ms, key="data_refresh")

# ----------------------------
# Manual refresh button
# ----------------------------
if st.button("🔄 Refresh Now"):
    st.session_state.last_refreshed = datetime.now()
    st.rerun()

# ----------------------------
# Fetch NOAA Kp Index
# ----------------------------
url = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
df = pd.read_json(url)
latest = df.tail(1).iloc[0]
kp_index = latest["kp_index"]
time_tag = latest["time_tag"]

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
# Regions
# ----------------------------
regions = {
    "Hyderabad, India": (17.4, 78.5),
    "New Delhi, India": (28.6, 77.2),
    "Bangalore, India": (12.97, 77.59),
    "Oslo, Norway": (59.9, 10.8),
    "Anchorage, Alaska": (61.2, -149.9),
    "São Paulo, Brazil": (-23.5, -46.6),
    "Sydney, Australia": (-33.9, 151.2),
    "Nairobi, Kenya": (-1.3, 36.8),
    "Dodoma, Tanzania": (-6.17, 35.74),
    "Chennai, India": (13.08, 80.27),
}

# Build DataFrame
data = []
for city, (lat, lon) in regions.items():
    risk = gps_risk(kp_index, lat)
    data.append({"City": city, "Latitude": lat, "Longitude": lon, "Risk": risk})
risk_df = pd.DataFrame(data)

# Map colors
color_map = {"Safe": [0, 200, 0], "Caution": [255, 165, 0], "High Risk": [200, 0, 0]}
risk_df["Color"] = risk_df["Risk"].map(color_map)

# ----------------------------
# Streamlit Layout
# ----------------------------
st.title("🛰️ SolarShield - GPS Risk Monitor")
st.subheader(f"Latest Kp Index: {kp_index} (Time: {time_tag})")

# Last refresh
st.caption(f"⏱️ Last refreshed at: {st.session_state.last_refreshed.strftime('%Y-%m-%d %H:%M:%S')}")

# ----------------------------
# Countdown (calculated live)
# ----------------------------
next_refresh_time = st.session_state.last_refreshed + timedelta(milliseconds=interval_ms)
seconds_remaining = int((next_refresh_time - datetime.now()).total_seconds())
if seconds_remaining < 0:
    seconds_remaining = 0
mins, secs = divmod(seconds_remaining, 60)
st.markdown(f"⌛ Next auto-refresh in: **{mins}m {secs:02d}s**")

# ----------------------------
# Two columns: Table + Map
# ----------------------------
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📍 Location-specific Risks")
    st.dataframe(risk_df)

with col2:
    st.subheader("🌍 Global Risk Map")
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=risk_df,
        get_position=["Longitude", "Latitude"],
        get_color="Color",
        get_radius=200000,
        pickable=True,
    )
    view_state = pdk.ViewState(latitude=20, longitude=0, zoom=1.5, pitch=0)
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{City}: {Risk}"}
        )
    )


# # ----------------------------
# # Page config must be first
# # ----------------------------
# st.set_page_config(page_title="SolarShield GPS Risk Monitor", layout="wide")

# # ----------------------------
# # Refresh intervals
# # ----------------------------
# data_interval_ms = 300000   # 5 minutes for data
# ui_interval_ms   = 1000     # 1 second for countdown

# # Initialize session state
# if "last_refreshed" not in st.session_state:
#     st.session_state.last_refreshed = datetime.now()

# # ----------------------------
# # Manual refresh button
# # ----------------------------
# if st.button("🔄 Refresh Now"):
#     st.session_state.last_refreshed = datetime.now()  # reset timer
#     st.rerun()

# # ----------------------------
# # Auto-refresh for DATA (5 mins)
# # ----------------------------
# st_autorefresh(interval=data_interval_ms, key="data_refresh")

# # ----------------------------
# # Auto-refresh for UI (1 sec countdown updates)
# # ----------------------------
# st_autorefresh(interval=ui_interval_ms, key="ui_refresh")

# # ----------------------------
# # Fetch NOAA Kp Index
# # ----------------------------
# url = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
# df = pd.read_json(url)
# latest = df.tail(1).iloc[0]
# kp_index = latest["kp_index"]
# time_tag = latest["time_tag"]

# # ----------------------------
# # Display refresh info
# # ----------------------------
# st.caption(f"⏱️ Last refreshed at: {st.session_state.last_refreshed.strftime('%Y-%m-%d %H:%M:%S')}")

# # ----------------------------
# # Countdown (live ticking every sec)
# # ----------------------------
# next_refresh_time = st.session_state.last_refreshed + timedelta(milliseconds=data_interval_ms)
# seconds_remaining = max(0, int((next_refresh_time - datetime.now()).total_seconds()))
# mins, secs = divmod(seconds_remaining, 60)
# st.markdown(f"⌛ Next auto-refresh in: **{mins}m {secs:02d}s**")

# # ----------------------------
# # Your existing dashboard layout...
# # ----------------------------
# st.title("🛰️ SolarShield - GPS Risk Monitor")
# st.subheader(f"Latest Kp Index: {kp_index} (Time: {time_tag})")

# # Risk function
# def gps_risk(kp, latitude):
#     lat = abs(latitude)
#     if lat >= 60:
#         if kp >= 4:
#             return "High Risk"
#         elif kp >= 2:
#             return "Caution"
#         else:
#             return "Safe"
#     elif 30 <= lat < 60:
#         if kp >= 6:
#             return "High Risk"
#         elif kp >= 4:
#             return "Caution"
#         else:
#             return "Safe"
#     else:
#         if kp >= 8:
#             return "High Risk"
#         elif kp >= 6:
#             return "Caution"
#         else:
#             return "Safe"

# regions = {
#     "Hyderabad, India": (17.4, 78.5),
#     "New Delhi, India": (28.6, 77.2),
#     "Bangalore, India": (12.97, 77.59),
#     "Oslo, Norway": (59.9, 10.8),
#     "Anchorage, Alaska": (61.2, -149.9),
#     "São Paulo, Brazil": (-23.5, -46.6),
#     "Sydney, Australia": (-33.9, 151.2),
#     "Nairobi, Kenya": (-1.3, 36.8),
#     "Dodoma, Tanzania": (-6.17, 35.74),
#     "Chennai, India": (13.08, 80.27),
# }

# data = []
# for city, (lat, lon) in regions.items():
#     risk = gps_risk(kp_index, lat)
#     data.append({"City": city, "Latitude": lat, "Longitude": lon, "Risk": risk})
# risk_df = pd.DataFrame(data)

# color_map = {"Safe": [0, 200, 0], "Caution": [255, 165, 0], "High Risk": [200, 0, 0]}
# risk_df["Color"] = risk_df["Risk"].map(color_map)

# col1, col2 = st.columns([1, 2])
# with col1:
#     st.subheader("📍 Location-specific Risks")
#     st.dataframe(risk_df)

# with col2:
#     st.subheader("🌍 Global Risk Map")
#     layer = pdk.Layer(
#         "ScatterplotLayer",
#         data=risk_df,
#         get_position=["Longitude", "Latitude"],
#         get_color="Color",
#         get_radius=200000,
#         pickable=True,
#     )
#     view_state = pdk.ViewState(latitude=20, longitude=0, zoom=1.5, pitch=0)
#     st.pydeck_chart(
#         pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{City}: {Risk}"})
#     )