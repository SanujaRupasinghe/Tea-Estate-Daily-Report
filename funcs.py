import streamlit as st
from collections import Counter
import requests
import gspread
from google.oauth2.service_account import Credentials

# Define constants
base_rate = 400
expected_tea_kg = 18
extra_kg_rate = 50
# Map period to number of base units
period_unit_map = {
    "7.30-10.30": 1,
    "7.30-1.30": 2,
    "7.30-4.30": 3
}

# --- Payment Calculation Function ---
def calculate_payment(row):
    period = row["Work Period"]
    work_type = row["Work Type"]
    units = period_unit_map.get(period, 0)
    
    if work_type == "Tea_Plucking":
        base_payment = base_rate * units
        amount = row.get("Amount (kg)", 0) or 0
        extra_kg = amount - expected_tea_kg
        adjustment = extra_kg * extra_kg_rate  # positive or negative
        return base_payment + adjustment
    elif work_type in ["Fertilizing", "Tea_Pruning", "Weeding"]:
        return base_rate * units
    else:
        return 0  # or some default if needed

# --- Weather Data Fetch Function ---
@st.cache_data(show_spinner=False)
def get_weather(target_date, start_hour, end_hour):
    latitude, longitude = 7.095024817437363, 80.36483435225661
    date_str = target_date.strftime("%Y-%m-%d")
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&start_date={date_str}&end_date={date_str}"
        f"&hourly=temperature_2m,weathercode,relative_humidity_2m"
        f"&timezone=Asia%2FColombo"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        temps = data["hourly"]["temperature_2m"]
        codes = data["hourly"]["weathercode"]
        humidity = data["hourly"]["relative_humidity_2m"]
        hours = data["hourly"]["time"]

        # 24 values for full day
        full_day_temps = temps[:24]
        full_day_humidity = humidity[:24]

        # Filter for given time range
        hour_indices = [
            i for i, t in enumerate(hours)
            if start_hour <= int(t.split("T")[1][:2]) < end_hour
        ]
        if not hour_indices:
            return None, "Weather data unavailable for period", None, [], []

        period_temps = [temps[i] for i in hour_indices]
        period_codes = [codes[i] for i in hour_indices]
        period_humidity = [humidity[i] for i in hour_indices]
        avg_temp = sum(period_temps) / len(period_temps)
        avg_humidity = sum(period_humidity) / len(period_humidity)
        code = Counter(period_codes).most_common(1)[0][0]

        weather_map = {
            0: "Sunny", 1: "Mainly clear", 2: "Partly cloudy", 3: "Cloudy",
            45: "Foggy", 48: "Depositing rime fog", 51: "Light drizzle",
            53: "Drizzle", 55: "Dense drizzle", 56: "Freezing drizzle",
            57: "Dense freezing drizzle", 61: "Slight rain", 63: "Rain",
            65: "Heavy rain", 66: "Freezing rain", 67: "Heavy freezing rain",
            71: "Slight snow fall", 73: "Snow fall", 75: "Heavy snow fall",
            77: "Snow grains", 80: "Slight rain showers", 81: "Rain showers",
            82: "Violent rain showers", 85: "Slight snow showers",
            86: "Heavy snow showers", 95: "Thunderstorm",
            96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"
        }

        weather_word = weather_map.get(code, "Unknown")
        return start_hour, end_hour, weather_word, round(avg_temp, 1), round(avg_humidity, 1), full_day_temps, full_day_humidity

    except Exception as e:
        return None, f"Weather data unavailable: {e}", None, [], []
        
# --- Google Sheets Write Function ---
def write_to_gsheet(df, sheet_name, transport_login, transport_logout, transport_payment, tea_collect_attended, tea_collect_payment, weather, additional_notes=""):
    try:
        if "Work Period" in df.columns:
            df["Payment"] = df.apply(calculate_payment, axis=1)

        df = df.fillna("")

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["google_service_account"]
        creds = Credentials.from_service_account_info(dict(creds_dict), scopes=scope)
        client = gspread.authorize(creds)

        spreadsheet = client.open("Tea Estate Daily Report")
        try:
            sheet = spreadsheet.worksheet(sheet_name)
            sheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")

        sheet.append_row(df.columns.tolist())
        for row in df.values.tolist():
            sheet.append_row(row)

        sheet.append_row(["==== TRANSPORT ===="])
        sheet.append_row([
            "transport Arrived (Login/Logout)", "TRUE" if transport_login else "FALSE",
            "TRUE" if transport_logout else "FALSE"
        ])
        sheet.append_row(["transport Paid", str(transport_payment)])

        sheet.append_row(["==== Tea Collect ===="])
        sheet.append_row(["tea collect Arrived", "TRUE" if tea_collect_attended else "FALSE"])
        sheet.append_row(["tea collect Received", str(tea_collect_payment)])

        sheet.append_row(["==== Weather ===="])
        # First row: period, weather word, avg temp, avg humidity
        sheet.append_row([
            f"{weather[0]}:00 - {weather[1]}:00",
            weather[2],  # weather word
            weather[3],  # avg temp
            weather[4]   # avg humidity
        ])
        # Second row: 24-hour temperature values
        sheet.append_row(["Temp 24hr"] + list(weather[5]))
        # Third row: 24-hour humidity values
        sheet.append_row(["Humidity 24hr"] + list(weather[6]))

        sheet.append_row(["==== Additional Notes ===="])
        if additional_notes:
            sheet.append_row([additional_notes])
        else:
            sheet.append_row(["No additional notes."])

        return True, f"✅ Data successfully written to sheet '{sheet_name}'."
    except Exception as e:
        return False, f"❌ Error writing to Google Sheets: {e}"
    

# --- Google Sheets Read Function ---
@st.cache_data(show_spinner=False)
def read_from_gsheet(start_date, end_date):
    return