import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
import requests
from collections import Counter

# Streamlit page config
st.set_page_config(page_title="Tea Estate Daily Report", layout="wide")

users = st.secrets["users"]

workers = [
    "M1 - Kokila", "M2 - Sunil", "M3 - Nimal - Podi", "M4 - Nimal - Loku", "M6 - Sarath",
    "M7 - Sirinayaka", "F1 - Seetha", "F3 - Soma", "F4 - Sawrna", "F6 - Nilanthi",
    "F8 - Lakmali", "F11 - Samathi Udapotha", "F20 - Surangi", "F24 - Anusha",
    "F23 - Deepa Kumari", "F26 - Dilshani",
]
sections = ["1A -1", "1A -2", "1A -3", "1B-1", "1B-2", "1B-3", "1B-4", "1C-1", "1C-2", "1C-3", "1D", "2A-1", "2B", "2C-1", "2C-2", "2C-3", "3A-1", "3A-2", "3B-1", "3B-2", "3B-3", "4"]
work_periods = ["7.30-1.30", "7.30-10.30", "7.30-4.30"]
work_types = ["Tea_Plucking", "Fertilizing", "Tea_Pruning", "Weeding"]

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

# Function to calculate payment
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
    
@st.cache_data(show_spinner=False)
def get_weather_for_period(target_date, start_hour, end_hour):
    latitude, longitude = 7.095024817437363, 80.36483435225661
    date_str = target_date.strftime("%Y-%m-%d")
    url = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={latitude}&longitude={longitude}"
    f"&start_date={date_str}&end_date={date_str}"
    f"&hourly=temperature_2m,weathercode"
    f"&timezone=Asia%2FColombo"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        temps = data["hourly"]["temperature_2m"]
        codes = data["hourly"]["weathercode"]
        hours = data["hourly"]["time"]
        # Extract hour from ISO time string
        hour_indices = [
            i for i, t in enumerate(hours)
            if start_hour <= int(t.split("T")[1][:2]) < end_hour
        ]
        if not hour_indices:
            return None, "Weather data unavailable for period"
        period_temps = [temps[i] for i in hour_indices]
        period_codes = [codes[i] for i in hour_indices]
        avg_temp = sum(period_temps) / len(period_temps)
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
        return round(avg_temp, 1), weather_word
    except Exception as e:
        return None, f"Weather data unavailable: {e}"
        
# --- Google Sheets Write Function ---
def write_to_gsheet(df, sheet_name, transport_login, transport_logout, transport_payment, tea_collect_attended, tea_collect_payment, weather_period_1, weather_period_2):
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
        sheet.append_row(["6.00am - 6.00pm", f"{weather_period_1[0]}°C", weather_period_1[1]])
        sheet.append_row(["6.00am - 2.00pm", f"{weather_period_2[0]}°C", weather_period_2[1]])

        return True, f"✅ Data successfully written to sheet '{sheet_name}'."
    except Exception as e:
        return False, f"❌ Error writing to Google Sheets: {e}"


# --- Session State Initialization ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "all_worker_data" not in st.session_state:
    st.session_state.all_worker_data = [
        {
            "Worker Name": worker,
            "Arrived": False,
            "Section": None,
            "Work Period": None,
            "Work Type": None,
            "Amount (kg)": None,
            "Advanced Payment": 0,
        }
        for worker in workers
    ]
if "transport_arrived_login_state" not in st.session_state:
    st.session_state.transport_arrived_login_state = False
if "transport_arrived_logout_state" not in st.session_state:
    st.session_state.transport_arrived_logout_state = False
if "transport_payment_state" not in st.session_state:
    st.session_state.transport_payment_state = 0
if "tea_collect_arrived_state" not in st.session_state:
    st.session_state.tea_collect_arrived_state = False
if "tea_collect_payment_state" not in st.session_state:
    st.session_state.tea_collect_payment_state = 0

if "weather_period_1" not in st.session_state:
    st.session_state.weather_period_1 = [None, None]
if "weather_period_2" not in st.session_state:
    st.session_state.weather_period_2 = [None, None]

if "saved" not in st.session_state:
    st.session_state.saved = False
if "page" not in st.session_state:
    st.session_state.page = "login"

# --- LOGIN PAGE ---
def login_page():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

    if login_btn:
        if username in users and users[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.page = "Data Entry"
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")


# --- LOGOUT ---
def logout():
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.page = "login"
    st.rerun()


# --- NAVIGATION ---
def nav_buttons():
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("Data Entry"):
            st.session_state.page = "Data Entry"
            st.rerun()
    with col2:
        if st.button("Data Verify"):
            st.session_state.page = "Data Verify"
            st.rerun()
    with col3:
        if st.button("Logout"):
            logout()


# --- MAIN CONTENT ---
if not st.session_state.authenticated:
    login_page()
else:
    st.markdown(f"👤 Logged in as: **{st.session_state.username}**")
    nav_buttons()
    page = st.session_state.page

    # --- Data Entry Page ---
    if page == "Data Entry":
        st.title("🌿 Tea Estate Daily Report - Data Entry")
        st.markdown("---")

        st.write("### 📅 Select Date")
        day = st.date_input("", value=date.today())
        st.session_state.day = day

        # Get weather for the whole day
        temp_weather_period_1, weather_word_weather_period_1 = get_weather_for_period(day, 6, 18)
        temp_weather_period_2, weather_word_weather_period_2 = get_weather_for_period(day, 7, 14)
        st.session_state.weather_period_1 = [temp_weather_period_1, weather_word_weather_period_1]
        st.session_state.weather_period_2 = [temp_weather_period_2, weather_word_weather_period_2]

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🌦️ 6.00am to 6.00pm weather")
            if temp_weather_period_1 is not None:
                st.info(f"**Weather:** {weather_word_weather_period_1} | **Avg Temp:** {temp_weather_period_1}°C")
            else:
                st.warning(weather_word_weather_period_1)
        with col2:
            st.subheader("🌤️ 6.00am - 2.00pm Weather")
            if temp_weather_period_2 is not None:
                st.info(f"**Weather:** {weather_word_weather_period_2} | **Avg Temp:** {temp_weather_period_2}°C")
            else:
                st.warning(weather_word_weather_period_2)

        st.markdown("---")
        # Add New Worker
        with st.expander("➕ Add New Worker"):
            new_worker_name = st.text_input("Enter New Worker Name")
            add_worker_btn = st.button("Add Worker")
            if add_worker_btn:
                new_worker_name = new_worker_name.strip()
                if new_worker_name:
                    exists = any(d["Worker Name"] == new_worker_name for d in st.session_state.all_worker_data)
                    if exists:
                        st.warning(f"Worker '{new_worker_name}' already exists in the list.")
                    else:
                        new_worker_entry = {
                            "Worker Name": new_worker_name,
                            "Arrived": False,
                            "Section": None,
                            "Work Period": None,
                            "Work Type": None,
                            "Amount (kg)": None,
                            "Advanced Payment": 0,
                        }
                        st.session_state.all_worker_data.append(new_worker_entry)
                        st.success(f"Worker '{new_worker_name}' added successfully!")

        st.write("### ✍️ Fill Work Details for Each Worker")
        for i, w_data in enumerate(st.session_state.all_worker_data):
            worker = w_data["Worker Name"]
            with st.expander(f"👷 {worker}"):
                arrived = st.checkbox("Worker Arrived?", key=f"arrived_{worker}", value=w_data["Arrived"])
                st.session_state.all_worker_data[i]["Arrived"] = arrived

                if arrived:
                    section = st.selectbox("Section", sections, index=sections.index(w_data["Section"]) if w_data["Section"] in sections else 0, key=f"section_{worker}")
                    work_period = st.selectbox("Work Period", work_periods, index=work_periods.index(w_data["Work Period"]) if w_data["Work Period"] in work_periods else 0, key=f"period_{worker}")
                    work_type = st.selectbox("Work Type", work_types, index=work_types.index(w_data["Work Type"]) if w_data["Work Type"] in work_types else 0, key=f"type_{worker}")

                    st.session_state.all_worker_data[i]["Section"] = section
                    st.session_state.all_worker_data[i]["Work Period"] = work_period
                    st.session_state.all_worker_data[i]["Work Type"] = work_type

                    if work_type == "Tea_Plucking":
                        amount = st.number_input("Tea (kg)", min_value=0, step=1, format="%d", key=f"amount_{worker}_tea", value=w_data["Amount (kg)"] or 0)
                    elif work_type == "Fertilizing":
                        amount = st.number_input("Fertilizer (kg)", min_value=0, step=1, format="%d", key=f"amount_{worker}_fert", value=w_data["Amount (kg)"] or 0)
                    else:
                        st.info("No quantity needed for Weeding or Tea_Pruning.")
                        amount = 0

                    st.session_state.all_worker_data[i]["Amount (kg)"] = amount

                    adv_payment = st.number_input("Advanced Payment (Rs)", min_value=0, step=1, format="%d", key=f"adv_payment_{worker}", value=w_data.get("Advanced Payment", 0))
                    st.session_state.all_worker_data[i]["Advanced Payment"] = adv_payment
                else:
                    for field in ["Section", "Work Period", "Work Type", "Amount (kg)"]:
                        st.session_state.all_worker_data[i][field] = None

        st.markdown("---")
        st.write("### 🚚 transport Attendance")
        st.session_state.transport_arrived_login_state = st.checkbox(
            "Login?", key="transport_arrived_login", value=st.session_state.transport_arrived_login_state
        )
        st.session_state.transport_arrived_logout_state = st.checkbox(
            "Logout?", key="transport_arrived_logout", value=st.session_state.transport_arrived_logout_state
        )
        st.session_state.transport_payment_state = st.number_input(
            "Transport Payment (Rs)", min_value=0, step=1, format="%d", key="transport_payment",
            value=st.session_state.transport_payment_state
        )


        st.markdown("---")
        st.write("### 🚛 tea collect Attendance")
        st.session_state.tea_collect_arrived_state = st.checkbox(
            "Tea Collect Arrived?", key="tea_collect_arrived", value=st.session_state.tea_collect_arrived_state
        )
        st.session_state.tea_collect_payment_state = st.number_input(
            "Tea Collect Payment (Rs)", min_value=0, step=1, format="%d", key="tea_collect_payment",
            value=st.session_state.tea_collect_payment_state
        )


        st.markdown("---")
        if st.button("💾 Save Today's Data"):
            st.session_state.saved = True
            st.success("✅ Data saved successfully. Go to 'Data Verify' tab to review.")


    # --- Data Verify Page ---
    elif page == "Data Verify":
        st.title("🌿 Tea Estate Daily Report - Data Verify")
        st.markdown("---")
        if st.session_state.saved:
            st.markdown(f"### 📅 Date of Work: **{st.session_state.day}**")

            col1, col2 = st.columns(2)
            st.markdown("### 🌤️ Weather Information")
            with col1:
                st.write("🌦️ Whole Day Weather")
                temp_weather_period_1, weather_word_weather_period_1 = st.session_state.weather_period_1
                if temp_weather_period_1 is not None:
                    st.info(f"**Weather:** {weather_word_weather_period_1} | **Avg Temp:** {temp_weather_period_1}°C")
                else:
                    st.warning(weather_word_weather_period_1)
            with col2:
                st.write("🌤️ 7.30am - 1.30pm Weather")
                temp_weather_period_2, weather_word_weather_period_2 = st.session_state.weather_period_2
                if temp_weather_period_2 is not None:
                    st.info(f"**Weather:** {weather_word_weather_period_2} | **Avg Temp:** {temp_weather_period_2}°C")
                else:
                    st.warning(weather_word_weather_period_2)

            df = pd.DataFrame(st.session_state.all_worker_data)
            st.write("📊 Current data from this session:")
            st.dataframe(df, use_container_width=True)

            st.markdown("### 🚛 transport Attendance")
            transport_login_verify = st.session_state.get("transport_arrived_login_state", None)
            st.write("transport:", "✅ Arrived" if transport_login_verify else "❌ Not Arrived")
            transport_logout_verify = st.session_state.get("transport_arrived_logout_state", None)
            st.write("transport:", "✅ Left" if transport_logout_verify else "❌ Not Left")
            transport_payment_verify = st.session_state.get("transport_payment_state", 0)
            st.write(f"transport Payment: Rs {transport_payment_verify}")

            st.markdown("### 🚚 tea collect Attendance")
            tea_collect_arrived_verify = st.session_state.get("tea_collect_arrived_state", None)
            st.write("tea collect:", "✅ Arrived" if tea_collect_arrived_verify else "❌ Not Arrived")
            tea_collect_payment_verify = st.session_state.get("tea_collect_payment_state", 0)
            st.write(f"tea collect Payment: Rs {tea_collect_payment_verify}")

            if st.button("✅ Final Submit"):
                with st.spinner("Uploading to Google Sheets..."):
                    sheet_name = st.session_state.day.strftime("%Y-%m-%d")
                    success, msg = write_to_gsheet(
                        df=df,
                        sheet_name=sheet_name,
                        transport_login=st.session_state.transport_arrived_login_state,
                        transport_logout=st.session_state.transport_arrived_logout_state,
                        transport_payment=st.session_state.transport_payment_state,
                        tea_collect_attended=st.session_state.tea_collect_arrived_state,
                        tea_collect_payment=st.session_state.tea_collect_payment_state,
                        weather_period_1=st.session_state.weather_period_1,
                        weather_period_2=st.session_state.weather_period_2
                    )
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
        else:
            st.warning("⚠️ No data available. Please enter and save data on the 'Data Entry' page first.")
            
