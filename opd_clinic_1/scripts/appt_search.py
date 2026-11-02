# Server Script: appt_search
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_search
# allow_guest: 1
# frequency: All
# disabled: 0

MASK_MOBILE = False  # set True to show numbers like 98****3210

name = (frappe.form_dict.get("name") or "").strip()
mobile = (frappe.form_dict.get("mobile") or "").strip()
if len(name) < 2 and len(mobile) < 4:
    frappe.throw("Enter at least 2 letters of the name or 4 digits of the mobile number.")

filters = [["Patient", "status", "=", "Active"]]
if name:
    filters.append(["Patient", "patient_name", "like", "%" + name + "%"])
if mobile:
    filters.append(["Patient", "mobile", "like", "%" + mobile + "%"])

rows = frappe.get_all("Patient", filters=filters,
    fields=["name", "patient_name", "mobile", "dob"],
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
    out.append({"id": r.name, "name": r.patient_name, "age": age, "mobile": m})
frappe.response["message"] = {"patients": out}
