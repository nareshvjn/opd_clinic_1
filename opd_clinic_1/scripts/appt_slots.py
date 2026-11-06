# Server Script: appt_slots
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_slots
# allow_guest: 1
# frequency: All
# disabled: 0

SLOT_MINUTES = 10
# Used only when the doctor has no schedule for that weekday (6 PM to 9 PM)
DEFAULT_WINDOWS = [[18 * 60, 21 * 60]]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

prac = frappe.form_dict.get("practitioner")
date = frappe.form_dict.get("date")
exclude = frappe.form_dict.get("exclude")
if not prac or not date:
    frappe.throw("Choose a doctor and a date.")

d = frappe.utils.getdate(date)
day = DAYS[d.weekday()]

# 1. Working hours from the doctor's Practitioner Schedule(s) for that weekday
windows = []
source = "schedule"
try:
    doc = frappe.get_doc("Healthcare Practitioner", prac)
    for row in doc.practitioner_schedules:
        sch = frappe.get_doc("Practitioner Schedule", row.schedule)
        for ts in sch.time_slots:
            if ts.day == day:
                a = str(ts.from_time).split(":")
                b = str(ts.to_time).split(":")
                windows.append([int(a[0]) * 60 + int(a[1]), int(b[0]) * 60 + int(b[1])])
except:
    windows = []
if not windows:
    windows = DEFAULT_WINDOWS
    source = "default"

# 2. Time already taken by booked appointments
busy = []
booked = frappe.get_all("Patient Appointment",
    filters={"practitioner": prac, "appointment_date": date, "status": ["!=", "Cancelled"]},
    fields=["name", "appointment_time", "duration"])
for x in booked:
    if exclude and x.name == exclude:
        continue
    p = str(x.appointment_time).split(":")
    start = int(p[0]) * 60 + int(p[1])
    busy.append([start, start + max(int(x.duration or 0), SLOT_MINUTES)])

# 3. Hide times that have already passed today
now = 0
if d == frappe.utils.getdate(frappe.utils.today()):
    n = str(frappe.utils.now_datetime()).split(" ")[1].split(":")
    now = int(n[0]) * 60 + int(n[1])

# 4. Cut the working hours into 10-minute slots
slots = []
for w in windows:
    for t in range(w[0], w[1] - SLOT_MINUTES + 1, SLOT_MINUTES):
        if t < now:
            continue
        taken = False
        for b in busy:
            if t < b[1] and t + SLOT_MINUTES > b[0]:
                taken = True
        if not taken:
            slots.append(str(t // 60).zfill(2) + ":" + str(t % 60).zfill(2))

frappe.response["message"] = {"slots": sorted(set(slots)), "source": source}
