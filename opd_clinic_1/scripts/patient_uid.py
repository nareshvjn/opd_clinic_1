# Server Script: patient_uid
# type: DocType Event
# doctype: Patient
# event: Before Save
# disabled: 0

if not doc.uid:
    mmyy = frappe.utils.now_datetime().strftime("%m%y")
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
