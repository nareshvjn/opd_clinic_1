# Server Script: patient_backfill_uid
# type: API
# doctype: -
# event: Before Insert
# api_method: patient_backfill_uid
# allow_guest: 0
# disabled: 0

user = frappe.session.user
ok = False
for r in ["Healthcare Administrator", "System Manager", "Desk User"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
if not ok:
    frappe.throw("Not permitted.")

today_str = str(frappe.utils.today())
p_date = today_str.split("-")
mmyy = p_date[1] + p_date[0][2:]
prefix = "JHAM-" + mmyy + "-"

# Fetch all patients ordered by creation date to handle both NULL and empty string UIDs safely
patients = frappe.get_all("Patient", fields=["name", "uid"], order_by="creation asc", limit=10000)

max_seq = 0
for r in patients:
    u = (r.get("uid") or "").strip()
    if u.startswith(prefix):
        parts = u.split("-")
        if len(parts) >= 3 and parts[-1].isdigit():
            val = int(parts[-1])
            if val > max_seq:
                max_seq = val

count = 0
for p in patients:
    u = (p.get("uid") or "").strip()
    if not u:
        max_seq += 1
        new_uid = prefix + str(max_seq).zfill(6)
        frappe.db.set_value("Patient", p.name, "uid", new_uid, update_modified=False)
        count += 1

frappe.db.commit()
frappe.response["message"] = {
    "updated": count,
    "message": "Successfully backfilled " + str(count) + " patient UIDs."
}
