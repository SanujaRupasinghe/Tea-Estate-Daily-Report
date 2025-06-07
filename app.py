import streamlit as st
import pandas as pd
from datetime import date
from funcs import get_weather, write_to_gsheet, read_from_gsheet

# Streamlit page config
st.set_page_config(page_title="Tea Estate Daily Report", layout="wide")

users = st.secrets["users"]

workers = [
    "M1 - Kokila", "M2 - Sunil", "M3 - Nimal - Podi", "M4 - Nimal - Loku", "M6 - Sarath",
    "M7 - Sirinayaka", "F1 - Seetha", "F3 - Soma", "F4 - Sawrna", "F6 - Nilanthi",
    "F8 - Lakmali", "F11 - Samathi Udapotha", "F20 - Surangi", "F24 - Anusha",
    "F23 - Deepa Kumari", "F26 - Dilshani", "F27 - Irosha",
]
sections = ["1A -1", "1A -2", "1A -3", "1B-1", "1B-2", "1B-3", "1B-4", "1C-1", "1C-2", "1C-3", "1D", "2A-1", "2B", "2C-1", "2C-2", "2C-3", "3A-1", "3A-2", "3B-1", "3B-2", "3B-3", "4"]
work_periods = ["7.30-1.30", "7.30-10.30", "7.30-4.30"]
work_types = ["Tea_Plucking", "Fertilizing", "Tea_Pruning", "Weeding"]


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
            "Sections": None,
            "Work Period": None,
            "Work Type": None,
            "Amount (kg)": None,
            "Advanced Payment": 0,
            "Num Tasks": 0, 
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

if "weather" not in st.session_state:
    st.session_state.weather = [None, None, None, None, None, None, None]

if "additional_notes" not in st.session_state:
    st.session_state.additional_notes = ""

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
    col1, col2, col3, col4 = st.columns([1,1,1,1])
    with col1:
        if st.button("Data Entry"):
            st.session_state.page = "Data Entry"
            st.rerun()
    with col2:
        if st.button("Data Verify"):
            st.session_state.page = "Data Verify"
            st.rerun()
    with col3:
        if st.button("Analysis"):
            st.session_state.page = "Analysis"
            st.rerun()
    with col4:
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
        w_start, w_end, w_word_range, w_temp_range, w_humidi_range, w_temp_24, w_humidi_24 = get_weather(day, 6, 18)
        st.session_state.weather = [w_start, w_end, w_word_range, w_temp_range, w_humidi_range, w_temp_24, w_humidi_24]

        st.subheader(f"🌦️ {w_start}.am to {w_end}.pm weather")
        if w_temp_range is not None:       
            st.info(f"**Weather:** {w_word_range} | **Avg Temp:** {w_temp_range}°C | **Avg Humidity:** {w_humidi_range}%")
        else:
            st.warning(w_word_range)


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
                            "Sections": None,
                            "Work Period": None,
                            "Work Type": None,
                            "Amount (kg)": None,
                            "Advanced Payment": 0,
                            "Num Tasks": 0,
                        }
                        st.session_state.all_worker_data.append(new_worker_entry)
                        st.success(f"Worker '{new_worker_name}' added successfully!")

        st.write("### ✍️ Fill Work Details for Each Worker")
        for i, w_data in enumerate(st.session_state.all_worker_data):
            worker = w_data["Worker Name"]
            with st.expander(f"👷 {worker}"):
                arrived = st.checkbox("Worker Arrived?", key=f"arrived_{worker}", value=w_data.get("Arrived", False))
                st.session_state.all_worker_data[i]["Arrived"] = arrived

                if arrived:
                    work_period = st.selectbox(
                        "Work Period",
                        work_periods,
                        index=work_periods.index(w_data.get("Work Period", work_periods[0])) if w_data.get("Work Period") in work_periods else 0,
                        key=f"period_{worker}"
                    )
                    st.session_state.all_worker_data[i]["Work Period"] = work_period

                    adv_payment = st.number_input(
                        "Advanced Payment (Rs)",
                        min_value=0,
                        step=1,
                        format="%d",
                        key=f"adv_payment_{worker}",
                        value=w_data.get("Advanced Payment", 0)
                    )
                    st.session_state.all_worker_data[i]["Advanced Payment"] = adv_payment

                    num_tasks = st.number_input("Number of Tasks", min_value=0, max_value=3, value=w_data.get("Num Tasks", 1), key=f"num_tasks_{worker}")
                    st.session_state.all_worker_data[i]["Num Tasks"] = num_tasks
                   
                    # Default values if not present
                    sections_list = w_data.get("Sections", "").split(", ") if w_data.get("Sections") else []
                    work_types_list = w_data.get("Work Type", "").split(", ") if w_data.get("Work Type") else []
                    amount_list = w_data.get("Amount (kg)", "").split(", ") if w_data.get("Amount (kg)") else []

                    sections_result = []
                    work_types_result = []
                    amounts_result = []

                    if num_tasks > 0:
                        cols = st.columns(num_tasks)
                        for task_id in range(num_tasks):
                            with cols[task_id]:
                                st.markdown(f"**Task {task_id + 1}**")

                                section_default = sections_list[task_id] if task_id < len(sections_list) else sections[0]
                                section = st.selectbox(
                                    f"Section {task_id + 1}",
                                    sections,
                                    index=sections.index(section_default) if section_default in sections else 0,
                                    key=f"section_{worker}_{task_id}"
                                )

                                work_type_default = work_types_list[task_id] if task_id < len(work_types_list) else work_types[0]
                                work_type = st.selectbox(
                                    f"Work Type {task_id + 1}",
                                    work_types,
                                    index=work_types.index(work_type_default) if work_type_default in work_types else 0,
                                    key=f"type_{worker}_{task_id}"
                                )

                                if work_type == "Tea_Plucking":
                                    default_amt = int(amount_list[task_id]) if task_id < len(amount_list) else 0
                                    amount = st.number_input(f"Tea (kg)", min_value=0, step=1, format="%d", value=default_amt, key=f"amount_{worker}_tea_{task_id}")
                                elif work_type == "Fertilizing":
                                    default_amt = int(amount_list[task_id]) if task_id < len(amount_list) else 0
                                    amount = st.number_input(f"Fertilizer (kg)", min_value=0, step=1, format="%d", value=default_amt, key=f"amount_{worker}_fert_{task_id}")
                                else:
                                    st.info("No quantity needed for Weeding or Tea_Pruning.")
                                    amount = 0

                                sections_result.append(section)
                                work_types_result.append(work_type)
                                amounts_result.append(str(amount))

                    # Save updated flattened format
                    st.session_state.all_worker_data[i]["Sections"] = ", ".join(sections_result)
                    st.session_state.all_worker_data[i]["Work Type"] = ", ".join(work_types_result)
                    st.session_state.all_worker_data[i]["Amount (kg)"] = ", ".join(amounts_result)

                else:
                    st.session_state.all_worker_data[i]["Work Period"] = ""
                    st.session_state.all_worker_data[i]["Advanced Payment"] = 0
                    st.session_state.all_worker_data[i]["Sections"] = ""
                    st.session_state.all_worker_data[i]["Work Type"] = ""
                    st.session_state.all_worker_data[i]["Amount (kg)"] = ""
                    st.session_state.all_worker_data[i]["Num Tasks"] = 0


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
        st.write("### 📝 Additional Notes")
        st.session_state.additional_notes = st.text_area(
            "Enter any additional notes or comments here:", 
            value=st.session_state.additional_notes, 
            height=100
        )
        st.session_state.additional_notes = st.session_state.additional_notes.strip()

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

            st.markdown("### 🌤️ Weather Information")
            st.write("🌦️ Whole Day Weather")
            w_start, w_end, w_word_range, w_temp_range, w_humidi_range, w_temp_24, w_humidi_24 = st.session_state.weather
            if w_temp_range is not None:
                st.info(f"**Weather:** {w_word_range} | **Avg Temp:** {w_temp_range}°C | **Avg Humidity:** {w_humidi_range}%")
            else:
                st.warning(w_word_range)
            

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

            st.markdown("### 📝 Additional Notes")
            additional_notes = st.session_state.get("additional_notes", "")
            if additional_notes:
                st.write(additional_notes)
            else:
                st.warning("No additional notes provided.")
            
            st.markdown("---")
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
                        weather=st.session_state.weather,
                        additional_notes=st.session_state.additional_notes
                    )
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
        else:
            st.warning("⚠️ No data available. Please enter and save data on the 'Data Entry' page first.")

    # --- Analysis Page ---
    elif page == "Analysis":
        st.title("📊 Tea Estate Daily Report - Analysis")
        st.markdown("---")
        st.write("### 📅 Select Date Range for Analysis")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=date.today())
        with col2:
            end_date = st.date_input("End Date", value=date.today())

