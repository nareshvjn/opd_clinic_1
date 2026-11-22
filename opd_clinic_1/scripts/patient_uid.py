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
    records = frappe.get_all("Patient", filters={"uid": ["like", prefix + "%"]}, fields=["uid"], limit=10000)
    max_seq = 0
    for r in records:
        u = r.get("uid") or ""
        parts = u.split("-")
        if len(parts) >= 3 and parts[-1].isdigit():
            val = int(parts[-1])
            if val > max_seq:
                max_seq = val
    doc.uid = prefix + str(max_seq + 1).zfill(6)
