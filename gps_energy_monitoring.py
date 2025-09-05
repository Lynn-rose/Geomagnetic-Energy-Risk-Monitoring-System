import pandas as pd
import numpy as np
import streamlit as st
import requests
import datetime as dt
import matplotlib.pyplot as plt

# -----------------------------
# Utility functions
# -----------------------------
@st.cache_data
def load_world_cities():
    url = "https://raw.githubusercontent.com/datasets/world-cities/master/data/world-cities.csv"
    df = pd.read_csv(url)
    df = df.rename(columns={"name": "city", "lat": "latitude", "lng": "longitude"})
    return df

def gps_risk(kp_index, latitude):
    """
    Simple risk function based on Kp index and latitude.
    Higher latitude + higher Kp = higher risk.
    """
    if latitude is None:
        return 0
    score = kp_index * (abs(latitude) / 90)
    if score < 2:
        return "Low"
    elif score < 4:
        return "Moderate"
    elif score < 6:
        return "High"
    else:
        return "Severe"

def build_df(kp_index):
    cities = load_world_cities().sample(20, random_state=42)  # sample for performance
    risks = []
    for _, row in cities.iterrows():
        risks.append(gps_risk(kp_index, row.get("latitude", None)))
    cities["risk"] = risks
    return cities

# -----------------------------
# NASA API call (or fallback)
# -----------------------------
@st.cache_data
def get_kp_forecast():
    try:
        url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        df = pd.DataFrame(data[1:], columns=data[0])  # first row is header
        df["time_tag"] = pd.to_datetime(df["time_tag"])
        df["kp_index"] = df["kp_index"].astype(float)
        return df
    except Exception as e:
        st.warning(f"Could not load Kp forecast, using fallback. Error: {e}")
        now = dt.datetime.utcnow()
        times = [now + dt.timedelta(hours=3 * i) for i in range(10)]
        return pd.DataFrame({
            "time_tag": times,
            "kp_index": np.random.randint(0, 9, size=len(times))
        })

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("🌍 Geomagnetic Energy Risk Monitoring")

# Load forecast
forecast_df = get_kp_forecast()

# Show forecast chart
st.subheader("Kp Index Forecast (3-hour steps)")
fig, ax = plt.subplots()
ax.plot(forecast_df["time_tag"], forecast_df["kp_index"], marker="o")
ax.set_xlabel("Time (UTC)")
ax.set_ylabel("Kp Index")
ax.set_title("Forecasted Geomagnetic Activity")
st.pyplot(fig)

# Current risk snapshot
latest_kp = forecast_df.iloc[0]["kp_index"]
risk_df_current = build_df(latest_kp)

st.subheader(f"Current Risk Snapshot (Kp={latest_kp})")
st.map(risk_df_current, latitude="latitude", longitude="longitude")

# -----------------------------
# Risk scoring legend
# -----------------------------
st.markdown("### 🗺️ Risk Scoring Legend")

legend_text = """
The **risk score** is based on the geomagnetic Kp index and geographic latitude.  
It reflects the likelihood of geomagnetic disturbances affecting power grids and GPS systems.

- 🟢 **Low Risk (0–2)** – Minimal geomagnetic disturbance, normal operations.  
- 🟡 **Moderate Risk (3–4)** – Some disturbances possible at high latitudes, low impact elsewhere.  
- 🟠 **High Risk (5–6)** – Noticeable geomagnetic activity, possible GPS/power fluctuations.  
- 🔴 **Severe Risk (7–9)** – Strong storm conditions, significant disruption risk to energy and GPS systems.  
"""
st.markdown(legend_text)
