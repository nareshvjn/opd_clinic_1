# Server Script: appt_search
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_search
# allow_guest: 1
# frequency: All
# disabled: 0

MASK_MOBILE = False  # set True to show numbers like 98****3210

q = (frappe.form_dict.get("query") or frappe.form_dict.get("q") or "").strip()
name = (frappe.form_dict.get("name") or "").strip()
mobile = (frappe.form_dict.get("mobile") or "").strip()

if not q:
    q = name or mobile

if len(q) < 2:
    frappe.throw("Enter at least 2 characters to search by name, mobile, or ID.")

q_wild = "%" + q + "%"
rows = frappe.get_all("Patient",
    filters=[["Patient", "status", "=", "Active"]],
    or_filters=[
        ["Patient", "patient_name", "like", q_wild],
        ["Patient", "mobile", "like", q_wild],
        ["Patient", "uid", "like", q_wild],
        ["Patient", "name", "like", q_wild]
    ],
    fields=["name", "patient_name", "mobile", "dob", "uid"],
    order_by="patient_name", limit=10)

today = frappe.utils.getdate(frappe.utils.today())
out = []
for r in rows:
    age = None
    if r.dob:
        d = frappe.utils.getdate(r.dob)
        age = today.year - d.year - (1 if (today.month, today.day) < (d.month, d.day) else 0)
    m = r.mobile or ""
    if MASK_MOBILE and len(m) > 6:
        m = m[:2] + "****" + m[-4:]
    out.append({"id": r.name, "uid": r.uid or "", "name": r.patient_name, "age": age, "mobile": m})
frappe.response["message"] = {"patients": out}
