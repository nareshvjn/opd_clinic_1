# Server Script: appt_meta
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_meta
# allow_guest: 1
# frequency: All
# disabled: 0

pr = frappe.get_all("Healthcare Practitioner",
    filters={"status": "Active"},
    fields=["name", "practitioner_name", "department"],
    order_by="practitioner_name")
ty = [t.name for t in frappe.get_all("Appointment Type", fields=["name"], order_by="name")]
token = ""
try:
    token = frappe.session.get("csrf_token") or ""
except:
    token = ""
frappe.response["message"] = {"practitioners": pr, "types": ty, "csrf": token}
