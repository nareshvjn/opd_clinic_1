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

# Direct database SQL so search works reliably for both guest and logged in users without permission blocks
rows = frappe.db.sql("""
    select name, patient_name, mobile, dob, uid, status
    from `tabPatient`
    where (status is null or status = '' or status != 'Disabled')
      and (
          patient_name like %(q_wild)s
          or mobile like %(q_wild)s
          or ifnull(uid, '') like %(q_wild)s
          or name like %(q_wild)s
      )
    order by patient_name asc
    limit 15
""", {"q_wild": q_wild}, as_dict=True)

today = frappe.utils.getdate(frappe.utils.today())
out = []
for r in rows:
    age = None
    if r.get("dob"):
        try:
            d = frappe.utils.getdate(r.get("dob"))
            age = today.year - d.year - (1 if (today.month, today.day) < (d.month, d.day) else 0)
        except:
            age = None
    m = r.get("mobile") or ""
    if MASK_MOBILE and len(m) > 6:
        m = m[:2] + "****" + m[-4:]
    out.append({
        "id": r.get("name"),
        "uid": r.get("uid") or "",
        "name": r.get("patient_name") or r.get("name"),
        "age": age,
        "mobile": m
    })
frappe.response["message"] = {"patients": out}
