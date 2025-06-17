from datetime import datetime, timedelta

def get_weather_date(data):
    avg_temp_dict = {}
    avg_humidity_dict = {}

    for entry in data:
        date = entry.get("date")
        weather = entry.get("weather", {})
        avg_temp = weather.get("avg_temp")
        avg_humidity = weather.get("avg_humidity")
        if date and avg_temp is not None:
            avg_temp_dict[date] = float(avg_temp)
        if date and avg_humidity is not None:
            avg_humidity_dict[date] = float(avg_humidity)

    return avg_temp_dict, avg_humidity_dict


def get_missing_dates(data, start_date, end_date):
    present_dates = set(entry.get("date") for entry in data if entry.get("date"))

    missing_dates = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str not in present_dates:
            missing_dates.append(date_str)
        current_date += timedelta(days=1)
    return missing_dates

def get_worker_progress(data, workers):
    """
    Given the data (list of dicts, each with 'date' and 'df' as list of worker dicts),
    and a list of worker names, returns a dict:
    {worker_name: [ {date, Arrived, Num Tasks, Work Period, Sections, Work Type, Amount (kg), Advanced Payment, Payment}, ... ]}
    """
    progress = {w: [] for w in workers}
    for day in data:
        date_str = day.get('date')
        df = day.get('df', [])
        for w in workers:
            # Find this worker's record for the day
            rec = next((row for row in df if row.get('Worker Name') == w), None)
            if rec:
                progress[w].append({
                    'date': date_str,
                    'Arrived': rec.get('Arrived'),
                    'Num Tasks': rec.get('Num Tasks'),
                    'Work Period': rec.get('Work Period'),
                    'Sections': rec.get('Sections'),
                    'Work Type': rec.get('Work Type'),
                    'Amount (kg)': rec.get('Amount (kg)'),
                    'Advanced Payment': rec.get('Advanced Payment'),
                    'Payment': rec.get('Payment'),
                })
            else:
                # If no record for this worker on this day, can append None or skip
                pass
    return progress

def get_section_progress(data, sections):
    """
    For each section, returns a list of dicts with date, work_type, amount, and worker_name for all workers and all days.
    {section: [ {date, work_type, amount, worker_name}, ... ] }
    """
    progress = {s: [] for s in sections}
    for day in data:
        date_str = day.get('date')
        df = day.get('df', [])
        for row in df:
            # Sections and Work Type may be comma-separated lists (for multi-task days)
            worker = row.get('Worker Name')
            sections_str = row.get('Sections', '')
            work_types_str = row.get('Work Type', '')
            amounts_str = row.get('Amount (kg)', '')
            if not sections_str:
                continue
            section_list = [s.strip() for s in sections_str.split(',')]
            work_type_list = [w.strip() for w in work_types_str.split(',')] if work_types_str else ['']*len(section_list)
            amount_list = [a.strip() for a in amounts_str.split(',')] if amounts_str else ['']*len(section_list)
            for i, section in enumerate(section_list):
                if section in progress:
                    progress[section].append({
                        'date': date_str,
                        'work_type': work_type_list[i] if i < len(work_type_list) else '',
                        'amount': amount_list[i] if i < len(amount_list) else '',
                        'worker_name': worker
                    })
    return progress


