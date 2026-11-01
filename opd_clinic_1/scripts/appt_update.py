# Server Script: appt_update
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_update
# allow_guest: 0
# frequency: All
# disabled: 0

if frappe.session.user == "Guest":
    frappe.throw("Log in with a staff account to edit appointments.")

f = frappe.form_dict
name = f.get("appointment")
patient = f.get("patient")
if not name or not patient:
    frappe.throw("Choose the appointment to edit.")

doc = frappe.get_doc("Patient Appointment", name)
if not doc.has_permission("write"):
    frappe.throw("You don't have permission to edit this appointment.")
if doc.patient != patient:
    frappe.throw("That appointment doesn't belong to this patient.")
if doc.status in ["Cancelled", "Closed"]:
    frappe.throw("This appointment can no longer be changed.")

today = frappe.utils.getdate(frappe.utils.today())
if frappe.utils.getdate(doc.appointment_date) < today:
    frappe.throw("Past appointments can't be changed.")
for k in ("practitioner", "appointment_type", "date", "time"):
    if not f.get(k):
        frappe.throw("Please complete all appointment details.")
if frappe.utils.getdate(f.get("date")) < today:
    frappe.throw("Choose today or a later date.")

def to_min(t):
    parts = str(t).split(":")
    return int(parts[0]) * 60 + int(parts[1])

dur = frappe.db.get_value("Appointment Type", f.get("appointment_type"), "default_duration") or 0
new_start = to_min(f.get("time"))
new_end = new_start + max(int(dur), 10)
others = frappe.get_all("Patient Appointment",
    filters={"practitioner": f.get("practitioner"), "appointment_date": f.get("date"),
             "status": ["!=", "Cancelled"], "name": ["!=", name]},
    fields=["appointment_time", "duration"])
for b in others:
    b_start = to_min(b.appointment_time)
    b_end = b_start + max(int(b.duration or 0), 10)
    if new_start < b_end and new_end > b_start:
        frappe.throw("This time slot is already booked. Please choose another time.")

doc.practitioner = f.get("practitioner")
doc.appointment_type = f.get("appointment_type")
doc.appointment_date = f.get("date")
doc.appointment_time = f.get("time")
doc.notes = f.get("notes")
if dur:
    doc.duration = int(dur)
doc.save(ignore_permissions=True)

frappe.response["message"] = {"appointment": doc.name}
