# Server Script: ph_patients
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_patients
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the pharmacy.")

q = (frappe.form_dict.get("q") or "").strip()
if len(q) < 2:
    frappe.throw("Type at least 2 characters of the name or mobile number.")

rows = frappe.get_all("Patient",
    filters=[["Patient", "status", "=", "Active"]],
    or_filters=[["Patient", "patient_name", "like", "%" + q + "%"],
                ["Patient", "mobile", "like", "%" + q + "%"]],
    fields=["name", "patient_name", "mobile", "dob"], order_by="patient_name", limit=10)

today = frappe.utils.getdate(frappe.utils.today())
out = []
for r in rows:
    age = None
    if r.dob:
        d = frappe.utils.getdate(r.dob)
        age = today.year - d.year - (1 if (today.month, today.day) < (d.month, d.day) else 0)
    out.append({"id": r.name, "name": r.patient_name, "age": age, "mobile": r.mobile or ""})
frappe.response["message"] = {"patients": out}
