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

today_str = str(frappe.utils.today())
p_date = today_str.split("-")
mmyy = p_date[1] + p_date[0][2:]
prefix = "JHAM-" + mmyy + "-"
records = frappe.get_all("Patient", filters={"uid": ["like", prefix + "%"]}, fields=["uid"], limit=10000)
max_seq = 0
for r in records:
    u = r.get("uid") or ""
    parts = u.split("-")
    if len(parts) >= 3 and parts[-1].isdigit():
        val = int(parts[-1])
        if val > max_seq:
            max_seq = val
next_uid = prefix + str(max_seq + 1).zfill(6)

frappe.response["message"] = {
    "practitioners": pr,
    "types": ty,
    "csrf": token,
    "next_uid": next_uid
}
