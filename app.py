import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

# Streamlit page config
st.set_page_config(page_title="Tea Estate Daily Report", layout="wide")

users = st.secrets["users"]

workers = [
    "M1 - Kokila", "M2 - Sunil", "M3 - Nimal - Podi", "M4 - Nimal - Loku", "M6 - Sarath",
    "M7 - Sirinayaka", "F1 - Seetha", "F3 - Soma", "F4 - Sawrna", "F6 - Nilanthi",
    "F8 - Lakmali", "F11 - Samathi Udapotha", "F20 - Surangi", "F24 - Anusha",
    "F23 - Deepa Kumari", "F26 - Dilshani",
]
sections = ["A", "B", "C", "D"]
work_periods = ["Full Day", "Half Day", "Quarter Day"]
work_types = ["Tea Plucking", "Fertilizing", "Cleaning"]

# --- Google Sheets Write Function ---
def write_to_gsheet(df, sheet_name, driver_attended, driver_payment):
    try:
        if "Date" in df.columns:
            df["Date"] = df["Date"].astype(str)

        if "Work Period" in df.columns:
            payment_map = {"Full Day": 1000, "Half Day": 750, "Quarter Day": 500}
            df["Payment"] = df["Work Period"].map(payment_map).fillna(0)

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

        sheet.append_row([])
        sheet.append_row(["DRIVER"])
        sheet.append_row(["Driver Arrived", "TRUE" if driver_attended else "FALSE"])
        sheet.append_row(["Driver Paid", str(driver_payment)])

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
        day = st.date_input("📅 Date of Work", value=date.today())
        st.session_state.day = day

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

        st.markdown("---")
        st.write("### ✍️ Fill Work Details for Each Worker")
        for i, w_data in enumerate(st.session_state.all_worker_data):
            worker = w_data["Worker Name"]
            with st.expander(f"👷 {worker}"):
                arrived = st.checkbox("Worker Arrived?", key=f"arrived_{worker}", value=w_data["Arrived"])
                st.session_state.all_worker_data[i]["Arrived"] = arrived

                if arrived:
                    section = st.selectbox("Section", sections,
                        index=sections.index(w_data["Section"]) if w_data["Section"] in sections else 0,
                        key=f"section_{worker}")
                    work_period = st.selectbox("Work Period", work_periods,
                        index=work_periods.index(w_data["Work Period"]) if w_data["Work Period"] in work_periods else 0,
                        key=f"period_{worker}")
                    work_type = st.selectbox("Work Type", work_types,
                        index=work_types.index(w_data["Work Type"]) if w_data["Work Type"] in work_types else 0,
                        key=f"type_{worker}")

                    st.session_state.all_worker_data[i]["Section"] = section
                    st.session_state.all_worker_data[i]["Work Period"] = work_period
                    st.session_state.all_worker_data[i]["Work Type"] = work_type

                    if work_type == "Tea Plucking":
                        amount = st.number_input("Tea (kg)", min_value=0, step=1, format="%d",
                            key=f"amount_{worker}_tea", value=w_data["Amount (kg)"] or 0)
                    elif work_type == "Fertilizing":
                        amount = st.number_input("Fertilizer (kg)", min_value=0, step=1, format="%d",
                            key=f"amount_{worker}_fert", value=w_data["Amount (kg)"] or 0)
                    else:
                        st.info("No quantity needed for Cleaning.")
                        amount = 0

                    st.session_state.all_worker_data[i]["Amount (kg)"] = amount

                    adv_payment = st.number_input("Advanced Payment (Rs)", min_value=0, step=1, format="%d",
                        key=f"adv_payment_{worker}", value=w_data.get("Advanced Payment", 0))
                    st.session_state.all_worker_data[i]["Advanced Payment"] = adv_payment
                else:
                    for field in ["Section", "Work Period", "Work Type", "Amount (kg)"]:
                        st.session_state.all_worker_data[i][field] = None

        st.markdown("---")
        st.write("### 🚚 Driver Attendance")
        driver_arrived = st.checkbox("Did the Driver come to work today?", key="driver_arrived")
        st.session_state.driver_attended = driver_arrived
        driver_pay = st.number_input("Driver Payment (Rs)", min_value=0, step=1, format="%d", key="driver_pay")
        st.session_state.driver_payment = driver_pay

        st.markdown("---")
        if st.button("💾 Save Today's Data"):
            st.session_state.saved = True
            st.success("✅ Data saved successfully. Go to 'Data Verify' tab to review.")


    # --- Data Verify Page ---
    elif page == "Data Verify":
        st.title("🌿 Tea Estate Daily Report - Data Verify")
        st.markdown("---")
        if st.session_state.saved and st.session_state.all_worker_data:
            st.markdown(f"### 📅 Date of Work: **{st.session_state.day}**")
            df = pd.DataFrame(st.session_state.all_worker_data)
            st.write("📊 Current data from this session:")
            st.dataframe(df, use_container_width=True)

            st.markdown("### 🚛 Driver Attendance")
            driver_status = st.session_state.get("driver_attended", None)
            st.write("Driver:", "✅ Arrived" if driver_status else "❌ Not Arrived")
            st.write(f"Driver Payment: Rs {st.session_state.get('driver_payment', 0)}")

            if st.button("✅ Final Submit"):
                with st.spinner("Uploading to Google Sheets..."):
                    sheet_name = st.session_state.day.strftime("%Y-%m-%d")
                    success, msg = write_to_gsheet(
                        df,
                        sheet_name=sheet_name,
                        driver_attended=st.session_state.driver_attended,
                        driver_payment=st.session_state.driver_payment,
                    )
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
        else:
            st.warning("⚠️ No data available. Please enter and save data on the 'Data Entry' page first.")
