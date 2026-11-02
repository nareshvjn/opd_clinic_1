# Server Script: appt_book
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_book
# allow_guest: 1
# frequency: All
# disabled: 0

f = frappe.form_dict
mode = f.get("mode")

for k in ("practitioner", "appointment_type", "date", "time"):
    if not f.get(k):
        frappe.throw("Please complete all appointment details.")
if frappe.utils.getdate(f.get("date")) < frappe.utils.getdate(frappe.utils.today()):
    frappe.throw("Choose today or a later date.")

# Refuse the booking if the doctor already has an appointment overlapping this time
def to_min(t):
    parts = str(t).split(":")
    return int(parts[0]) * 60 + int(parts[1])

dur = frappe.db.get_value("Appointment Type", f.get("appointment_type"), "default_duration") or 0
new_start = to_min(f.get("time"))
new_end = new_start + max(int(dur), 10)
existing = frappe.get_all("Patient Appointment",
    filters={"practitioner": f.get("practitioner"), "appointment_date": f.get("date"), "status": ["!=", "Cancelled"]},
    fields=["appointment_time", "duration"])
for b in existing:
    b_start = to_min(b.appointment_time)
    b_end = b_start + max(int(b.duration or 0), 10)
    if new_start < b_end and new_end > b_start:
        frappe.throw("This time slot is already booked. Please choose another time.")

if mode == "existing":
    patient = f.get("patient")
    if not patient or not frappe.db.exists("Patient", {"name": patient, "status": "Active"}):
        frappe.throw("Select the patient from the search results.")
else:
    first = (f.get("first_name") or "").strip()
    last = (f.get("last_name") or "").strip()
    dob = f.get("dob")
    mobile = (f.get("mobile") or "").strip()
    if not first or not f.get("sex"):
        frappe.throw("Please fill in first name and gender.")
    if dob or mobile:
        flt = {"first_name": first}
        if last:
            flt["last_name"] = last
        if dob:
            flt["dob"] = dob
        if mobile:
            flt["mobile"] = mobile
        if frappe.get_all("Patient", filters=flt, limit=1):
            frappe.throw("This patient already exists. Use 'I'm an existing patient' to find them.")
    p = frappe.new_doc("Patient")
    p.first_name = first
    p.last_name = last
    p.sex = f.get("sex")
    if dob:
        p.dob = dob
    p.mobile = mobile
    p.email = f.get("email")
    p.insert(ignore_permissions=True)
    patient = p.name

a = frappe.new_doc("Patient Appointment")
a.patient = patient
a.appointment_for = "Practitioner"
a.practitioner = f.get("practitioner")
a.appointment_type = f.get("appointment_type")
a.appointment_date = f.get("date")
a.appointment_time = f.get("time")
a.company = frappe.db.get_single_value("Global Defaults", "default_company")
a.notes = f.get("notes")
a.insert(ignore_permissions=True)

frappe.response["message"] = {"appointment": a.name}
