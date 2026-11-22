# Server Script: patient_uid
# type: DocType Event
# doctype: Patient
# event: Before Insert
# disabled: 0

if not doc.uid:
    today_str = str(frappe.utils.today())
    p_date = today_str.split("-")
    mmyy = p_date[1] + p_date[0][2:]
    prefix = "JHAM-" + mmyy + "-"
    rows = frappe.db.sql("""
        select uid from `tabPatient`
        where uid like %s
    """, (prefix + "%",), as_dict=True)
    max_seq = 0
    for r in rows:
        u = (r.get("uid") or "").strip()
        parts = u.split("-")
        if len(parts) >= 3 and parts[-1].isdigit():
            val = int(parts[-1])
            if val > max_seq:
                max_seq = val
    doc.uid = prefix + str(max_seq + 1).zfill(6)
