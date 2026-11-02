# Server Script: desk_status
# type: API
# doctype: -
# event: Before Insert
# api_method: desk_status
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = False
if frappe.db.exists("Has Role", {"parent": user, "role": "Healthcare Administrator"}):
    is_admin = True
if frappe.db.exists("Has Role", {"parent": user, "role": "System Manager"}):
    is_admin = True
is_doctor = bool(frappe.db.exists("Has Role", {"parent": user, "role": "Physician"}))
if not (is_admin or is_doctor):
    frappe.throw("You don't have access to the doctor desk.")

name = frappe.form_dict.get("appointment")
status = frappe.form_dict.get("status")

allowed = []
for s in (frappe.get_meta("Patient Appointment").get_field("status").options or "").split("\n"):
    if s:
        allowed.append(s)
if status not in allowed:
    frappe.throw("That status isn't available.")

doc = frappe.get_doc("Patient Appointment", name)
if not is_admin:
    mine = frappe.get_all("Healthcare Practitioner", filters={"user_id": user}, fields=["name"], limit=1)
    if not mine or doc.practitioner != mine[0].name:
        frappe.throw("You can only update your own appointments.")

doc.status = status
doc.save(ignore_permissions=True)
frappe.response["message"] = {"status": doc.status}
