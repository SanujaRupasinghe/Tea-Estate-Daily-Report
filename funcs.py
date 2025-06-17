from fpdf import FPDF
from io import BytesIO
import streamlit as st
from collections import Counter
import requests
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta

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
        amount = int(amount)
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

        sheet.append_row(["==== Trasnport ===="])
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
    # Setup Google Sheets client
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["google_service_account"]
    creds = Credentials.from_service_account_info(dict(creds_dict), scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("Tea Estate Daily Report")

    # Prepare date range
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end_date - start_date).days + 1
    date_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    all_data = []
    for sheet_name in date_list:
        try:
            sheet = spreadsheet.worksheet(sheet_name)
            rows = sheet.get_all_values()
            if not rows:
                continue

            # Find section indices
            def find_section(label):
                for idx, row in enumerate(rows):
                    if row and row[0].strip() == label:
                        return idx
                return -1

            # Main DataFrame
            df_start = 0
            transport_idx = find_section("==== Trasnport ====")
            if transport_idx == -1:
                continue
            df_header = rows[df_start]
            df_rows = rows[df_start+1:transport_idx]
            # Convert each row to dict using header
            df_dicts = []
            for row in df_rows:
                # Pad row if shorter than header
                padded_row = row + [""] * (len(df_header) - len(row))
                df_dicts.append(dict(zip(df_header, padded_row)))

            # Transport
            transport_login = transport_logout = transport_payment = None
            tea_collect_attended = tea_collect_payment = None
            weather = {}
            additional_notes = ""

            # Transport section
            transport_paid_idx = find_section("transport Paid")
            if transport_paid_idx != -1:
                transport_row = rows[transport_idx+1]
                transport_login = transport_row[1] == "TRUE"
                transport_logout = transport_row[2] == "TRUE"
                transport_payment = rows[transport_paid_idx][1]

            # Tea Collect section
            tea_collect_idx = find_section("==== Tea Collect ====")
            if tea_collect_idx != -1:
                tea_collect_attended = rows[tea_collect_idx+1][1] == "TRUE"
                tea_collect_payment = rows[tea_collect_idx+2][1]

            # Weather section
            weather_idx = find_section("==== Weather ====")
            if weather_idx != -1:
                weather_row = rows[weather_idx+1]
                weather['period'] = weather_row[0]
                weather['word'] = weather_row[1]
                weather['avg_temp'] = weather_row[2]
                weather['avg_humidity'] = weather_row[3]
                weather['temp_24hr'] = rows[weather_idx+2][1:]
                weather['humidity_24hr'] = rows[weather_idx+3][1:]

            # Additional Notes
            notes_idx = find_section("==== Additional Notes ====")
            if notes_idx != -1:
                additional_notes = rows[notes_idx+1][0] if len(rows) > notes_idx+1 else ""

            all_data.append({
                "date": sheet_name,
                "df": df_dicts,
                "transport_login": transport_login,
                "transport_logout": transport_logout,
                "transport_payment": transport_payment,
                "tea_collect_attended": tea_collect_attended,
                "tea_collect_payment": tea_collect_payment,
                "weather": weather,
                "additional_notes": additional_notes
            })
        except gspread.exceptions.WorksheetNotFound:
            continue
        except Exception as e:
            st.warning(f"Error reading sheet {sheet_name}: {e}")
            continue

    return all_data


def read_info_from_gsheet():
    creds_dict = st.secrets["google_service_account"]
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open("Tea Estate Daily Report")
    info = {}
    for ws in sh.worksheets():
        rows = ws.get_all_values()
        # Flatten: take only the first column, skip empty rows
        points = [row[0] for row in rows if row and row[0].strip()]
        info[ws.title] = points
    return info



# class ReportPDF(FPDF):
#     def header(self):
#         self.set_font("Arial", "B", 14)
#         self.cell(0, 10, "Tea Estate Daily Report", ln=True, align="C")
#         self.ln(5)

#     def add_day_report(self, day_data):
#         self.set_font("Arial", "B", 12)
#         self.cell(0, 10, f"Date: {day_data['date']}", ln=True)

#         self.set_font("Arial", "", 11)
#         self.cell(0, 8, f"Weather: {day_data['weather']['word']} | Period: {day_data['weather']['period']}", ln=True)
#         self.cell(0, 8, f"Avg Temp: {day_data['weather']['avg_temp']}°C | Avg Humidity: {day_data['weather']['avg_humidity']}%", ln=True)

#         self.cell(0, 8, f"Transport: Login - {day_data['transport_login']} | Logout - {day_data['transport_logout']} | Payment - {day_data['transport_payment']}", ln=True)
#         self.cell(0, 8, f"Tea Collection Attended: {day_data['tea_collect_attended']} | Payment: {day_data['tea_collect_payment']}", ln=True)

#         self.ln(4)
#         self.set_font("Arial", "B", 11)
#         self.cell(0, 8, "Worker Summary", ln=True)
#         self.set_font("Courier", "", 8)

#         df_text = day_data['df']
#         if hasattr(df_text, "to_string"):
#             df_text = df_text.to_string(index=False)

#         for line in df_text.split("\n"):
#             self.cell(0, 4, line.strip(), ln=True)

#         self.ln(4)
#         self.set_font("Arial", "I", 10)
#         self.multi_cell(0, 6, f"Notes: {day_data['additional_notes']}")
#         self.ln(6)
#         self.set_draw_color(180)
#         self.line(10, self.get_y(), 200, self.get_y())
#         self.ln(6)

# def create_full_report(data_list):
#     pdf = ReportPDF()
#     pdf.set_auto_page_break(auto=True, margin=15)
#     pdf.add_page()

#     for entry in data_list:
#         pdf.add_day_report(entry)

#     # Generate PDF content as bytes
#     pdf_str = pdf.output(dest='S')  # returns a str in Python 3
#     pdf_bytes = pdf_str.encode('latin-1')

#     # Write to BytesIO
#     pdf_buffer = BytesIO()
#     pdf_buffer.write(pdf_bytes)
#     pdf_buffer.seek(0)
#     return pdf_buffer