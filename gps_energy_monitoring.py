import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import re
from io import StringIO

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
    st.session_state.last_refreshed = datetime.now()

# ----------------------------
# Auto-refresh trigger
# ----------------------------
count = st_autorefresh(interval=interval_ms, limit=None, key="data_refresh")
# note: st_autorefresh triggers reruns. We treat refresh time as now on each run.
if count > 0:
    st.session_state.last_refreshed = datetime.now()

# ----------------------------
# Manual refresh button (immediate)
# ----------------------------
if st.button("🔄 Refresh Now"):
    st.session_state.last_refreshed = datetime.now()
    # force immediate rerun so UI updates now
    st.experimental_rerun()

# ----------------------------
# Fetch NOAA Kp Index (current, 1-minute data)
# ----------------------------
url_current = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
try:
    df_current = pd.read_json(url_current)
    latest = df_current.tail(1).iloc[0]
    kp_index = latest["kp_index"]
    time_tag = latest["time_tag"]
except Exception as e:
    st.error("Error fetching current Kp index. Showing fallback value 0.")
    kp_index = 0
    time_tag = "Unavailable"

# ----------------------------
# Fetch NOAA Kp Forecast (3-day text file)
# ----------------------------
url_forecast = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"
forecast_text = ""
try:
    forecast_text = requests.get(url_forecast, timeout=10).text
except Exception:
    forecast_text = ""

# Collect ALL kp values across lines (robust)
kp_values = []
if forecast_text:
    for line in forecast_text.splitlines():
        # lines look like: "Kp indices (3-hourly): 1 1 1 1 2 2 2 2 2 ..."
        if "Kp indices" in line or re.search(r"\bKp\b", line, flags=re.IGNORECASE):
            numbers = re.findall(r"\b\d+\b", line)
            kp_values.extend(list(map(int, numbers)))

# Sidebar settings
st.sidebar.header("⚙️ Settings")
horizon_options = list(range(1, 9))  # 1..8 (3h steps -> up to 24h)
selected_horizon = st.sidebar.selectbox("Forecast horizon (3h per step):", horizon_options, index=0)

# ----------------------------
# Robust loader for world cities (tries multiple remote sources, falls back local)
# ----------------------------
@st.cache_data(show_spinner=False)
def load_world_cities():
    candidate_urls = [
        # reliable small-ish lists (include the joelacus repo which contains lat/lng)
        "https://raw.githubusercontent.com/joelacus/world-cities/main/world_cities_5000.csv",
        "https://raw.githubusercontent.com/joelacus/world-cities/main/world_cities_15000.csv",
        # fallback dataset with only names/countries (no lat/lon) - kept as last resort
        "https://raw.githubusercontent.com/datasets/world-cities/master/data/world-cities.csv",
    ]

    def pick_col(cols_map, want):
        for alias in want:
            if alias in cols_map:
                return cols_map[alias]
        return None

    for url in candidate_urls:
        try:
            txt = requests.get(url, timeout=15).text
            df = pd.read_csv(StringIO(txt))
            # create lower->orig mapping
            cols_map = {c.lower(): c for c in df.columns}
            # pick columns
            city_col = pick_col(cols_map, ["city", "name"])
            country_col = pick_col(cols_map, ["country", "country_name"])
            lat_col = pick_col(cols_map, ["latitude", "lat"])
            lon_col = pick_col(cols_map, ["longitude", "lon", "lng", "long"])

            if city_col and country_col and lat_col and lon_col:
                # normalize names to: city, country, latitude, longitude
                df = df.rename(columns={
                    city_col: "city",
                    country_col: "country",
                    lat_col: "latitude",
                    lon_col: "longitude"
                })
                # ensure numeric coords
                df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
                df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
                df = df.dropna(subset=["latitude", "longitude", "city", "country"])
                # return a trimmed DataFrame
                return df[["city", "country", "latitude", "longitude"]].reset_index(drop=True)
            else:
                # try next url if missing lat/lon etc.
                continue
        except Exception:
            continue

    # --- final fallback: tiny built-in list so the app still works ---
    fallback = pd.DataFrame([
        {"city": "Nairobi", "country": "Kenya", "latitude": -1.286389, "longitude": 36.817223},
        {"city": "London", "country": "United Kingdom", "latitude": 51.507222, "longitude": -0.1275},
        {"city": "New York", "country": "United States", "latitude": 40.7128, "longitude": -74.0060},
        {"city": "Sydney", "country": "Australia", "latitude": -33.8688, "longitude": 151.2093},
        {"city": "Tokyo", "country": "Japan", "latitude": 35.6895, "longitude": 139.6917},
    ])
    return fallback

# load (cached)
world_cities = load_world_cities()

# Debug helper in sidebar (collapsed)
with st.sidebar.expander("🔍 Forecast / Data debug", expanded=False):
    st.write("Parsed kp_values (first 20):", kp_values[:20])
    st.write("World cities sample (rows):", len(world_cities))
    st.dataframe(world_cities.head(10))

# ----------------------------
# Region selection UI
# ----------------------------
st.sidebar.subheader("🌍 Region Selection")
region_mode = st.sidebar.radio("View:", ["Global", "By Country & City"])

if region_mode == "Global":
    selected_region = "Global"
    lat_center, lon_center = 20, 0
else:
    # protect against countries missing due to fallback
    countries = sorted(world_cities["country"].unique())
    selected_country = st.sidebar.selectbox("Select Country:", countries)
    filtered_cities = world_cities[world_cities["country"] == selected_country]
    # ensure list not empty
    if filtered_cities.empty:
        st.sidebar.warning("No cities available for this country (fallback dataset).")
        selected_city = None
        lat_center, lon_center = 20, 0
    else:
        selected_city = st.sidebar.selectbox("Select City:", sorted(filtered_cities["city"].unique()))
        city_row = filtered_cities[filtered_cities["city"] == selected_city].iloc[0]
        selected_region = f"{selected_city}, {selected_country}"
        lat_center, lon_center = float(city_row["latitude"]), float(city_row["longitude"])

# ----------------------------
# Forecast selection (from parsed kp_values)
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
# Build DataFrames (for current + forecast)
# ----------------------------
def build_df_from_cities(cities_df, kp_value):
    data = []
    for _, row in cities_df.iterrows():
        risk = gps_risk(kp_value, row["latitude"])
        data.append({
            "City": row["city"],
            "Country": row["country"],
            "Latitude": row["latitude"],
            "Longitude": row["longitude"],
            "Risk": risk
        })
    df = pd.DataFrame(data)
    color_map = {"Safe": [0, 200, 0], "Caution": [255, 165, 0], "High Risk": [200, 0, 0]}
    df["Color"] = df["Risk"].map(color_map)
    return df

# If user selected a specific country/city, filter to that region to keep map fast
if region_mode == "Global":
    city_pool = world_cities.copy()
else:
    if selected_city:
        city_pool = world_cities[(world_cities["country"] == selected_country) & (world_cities["city"] == selected_city)]
    else:
        city_pool = world_cities[world_cities["country"] == selected_country]

# Build frames
risk_df_current = build_df_from_cities(city_pool, kp_index)
risk_df_forecast = build_df_from_cities(city_pool, kp_forecast)

# ----------------------------
# Layout
# ----------------------------
st.title("🛰️ SolarShield - GPS Risk Monitor")

col_main1, col_main2 = st.columns(2)

# Map view state (center + zoom)
if region_mode == "Global":
    view_state = pdk.ViewState(latitude=lat_center, longitude=lon_center, zoom=1.5, pitch=0)
else:
    view_state = pdk.ViewState(latitude=lat_center, longitude=lon_center, zoom=6, pitch=30)

# -- Current risks panel
with col_main1:
    st.subheader(f"📊 Current Risks (Kp={kp_index}, Time={time_tag})")

    def highlight_risk(val):
        if val == "High Risk":
            return "background-color: red; color: white"
        elif val == "Caution":
            return "background-color: orange; color: black"
        else:
            return "background-color: green; color: white"

    st.dataframe(risk_df_current.drop(columns=["Color"]).style.applymap(highlight_risk, subset=["Risk"]))

    st.subheader("🌍 Current Risk Map")
    layer_current = pdk.Layer(
        "ScatterplotLayer",
        data=risk_df_current,
        get_position=["Longitude", "Latitude"],
        get_color="Color",
        get_radius=50000 if region_mode!="Global" else 200000,
        pickable=True
    )
    st.pydeck_chart(pdk.Deck(layers=[layer_current], initial_view_state=view_state, tooltip={"text": "{City}, {Country}: {Risk}"}))

# -- Forecast risks panel
with col_main2:
    st.subheader(f"📈 Forecast Risks (Kp={kp_forecast}, Horizon={forecast_time})")
    st.dataframe(risk_df_forecast.drop(columns=["Color"]).style.applymap(highlight_risk, subset=["Risk"]))

    st.subheader("🌍 Forecast Risk Map")
    layer_forecast = pdk.Layer(
        "ScatterplotLayer",
        data=risk_df_forecast,
        get_position=["Longitude", "Latitude"],
        get_color="Color",
        get_radius=50000 if region_mode!="Global" else 200000,
        pickable=True
    )
    st.pydeck_chart(pdk.Deck(layers=[layer_forecast], initial_view_state=view_state, tooltip={"text": "{City}, {Country}: {Risk}"}))

# ----------------------------
# Refresh info (bottom)
# ----------------------------
last_time = st.session_state.last_refreshed.strftime("%Y-%m-%d %H:%M:%S")
next_refresh_time = st.session_state.last_refreshed + timedelta(milliseconds=interval_ms)
seconds_remaining = max(0, int((next_refresh_time - datetime.now()).total_seconds()))
mins, secs = divmod(seconds_remaining, 60)

with st.expander("🔄 Refresh Information", expanded=False):
    st.markdown(f"**⏱️ Last refreshed:** {last_time}")
    st.markdown(f"**⌛ Next auto-refresh in:** {mins}m {secs:02d}s")
    # show a progress bar (approx)
    try:
        progress_value = max(0.0, min(1.0, 1 - (seconds_remaining * 1.0) / (interval_ms / 1000)))
        st.progress(progress_value)
    except Exception:
        pass
