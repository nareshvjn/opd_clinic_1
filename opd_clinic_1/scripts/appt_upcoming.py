# Server Script: appt_upcoming
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_upcoming
# allow_guest: 1
# frequency: All
# disabled: 0

patient = frappe.form_dict.get("patient")
if not patient:
    frappe.throw("Choose a patient first.")

if frappe.session.user == "Guest":
    # guests can book, but never see or edit existing appointments
    frappe.response["message"] = {"appointments": [], "guest": True}
else:
    rows = frappe.get_all("Patient Appointment",
        filters={"patient": patient, "appointment_date": [">=", frappe.utils.today()],
                 "status": ["not in", ["Cancelled", "Closed"]]},
        fields=["name", "practitioner", "practitioner_name", "appointment_date",
                "appointment_time", "appointment_type", "notes"],
        order_by="appointment_date asc, appointment_time asc", limit=10)

    out = []
    for r in rows:
        # only list what this user is allowed to change (Role Permissions Manager decides)
        if frappe.get_doc("Patient Appointment", r.name).has_permission("write"):
            t = str(r.appointment_time).split(":")
            out.append({"id": r.name, "practitioner": r.practitioner, "practitioner_name": r.practitioner_name,
                "date": str(r.appointment_date), "time": t[0].zfill(2) + ":" + t[1],
                "type": r.appointment_type, "notes": r.notes or ""})
    frappe.response["message"] = {"appointments": out, "guest": False}
