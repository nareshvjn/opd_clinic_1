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

empty_patients = frappe.get_all("Patient", filters={"uid": ["in", ["", None]]}, fields=["name"], order_by="creation asc", limit=1000)
count = 0
for p in empty_patients:
    max_seq += 1
    new_uid = prefix + str(max_seq).zfill(6)
    frappe.db.set_value("Patient", p.name, "uid", new_uid, update_modified=False)
    count += 1

frappe.db.commit()
frappe.response["message"] = {"updated": count}
