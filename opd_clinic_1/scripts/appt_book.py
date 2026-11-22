# Server Script: appt_book
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_book
# allow_guest: 1
# frequency: All
# disabled: 0

f = frappe.form_dict
mode = f.get("mode")

for k in ("practitioner", "appointment_type", "date", "time"):
    if not f.get(k):
        frappe.throw("Please complete all appointment details.")
if frappe.utils.getdate(f.get("date")) < frappe.utils.getdate(frappe.utils.today()):
    frappe.throw("Choose today or a later date.")

# Refuse the booking if the doctor already has an appointment overlapping this time
def to_min(t):
    parts = str(t).split(":")
    return int(parts[0]) * 60 + int(parts[1])

dur = frappe.db.get_value("Appointment Type", f.get("appointment_type"), "default_duration") or 0
new_start = to_min(f.get("time"))
new_end = new_start + max(int(dur), 10)
existing = frappe.get_all("Patient Appointment",
    filters={"practitioner": f.get("practitioner"), "appointment_date": f.get("date"), "status": ["!=", "Cancelled"]},
    fields=["appointment_time", "duration"])
for b in existing:
    b_start = to_min(b.appointment_time)
    b_end = b_start + max(int(b.duration or 0), 10)
    if new_start < b_end and new_end > b_start:
        frappe.throw("This time slot is already booked. Please choose another time.")

if mode == "existing":
    patient = f.get("patient")
    if not patient or not frappe.db.exists("Patient", {"name": patient, "status": "Active"}):
        frappe.throw("Select the patient from the search results.")
else:
    first = (f.get("first_name") or "").strip()
    last = (f.get("last_name") or "").strip()
    dob = f.get("dob")
    mobile = (f.get("mobile") or "").strip()
    if not first or not f.get("sex"):
        frappe.throw("Please fill in first name and gender.")
    if not mobile:
        frappe.throw("Please enter a mobile number.")
    clean_m = "".join([c for c in mobile if c.isdigit()])
    if len(clean_m) < 10:
        frappe.throw("Please enter a valid 10-digit mobile number.")

    flt = {"first_name": first, "mobile": mobile}
    if last:
        flt["last_name"] = last
    if dob:
        flt["dob"] = dob
    if frappe.db.exists("Patient", flt):
        frappe.throw("This patient already exists. Please use 'Existing patient' to find your record.")
    p = frappe.new_doc("Patient")
    p.first_name = first
    p.last_name = last
    p.sex = f.get("sex")
    if dob:
        p.dob = dob
    p.mobile = mobile
    p.email = f.get("email")
    today_str = str(frappe.utils.today())
    p_date = today_str.split("-")
    mmyy = p_date[1] + p_date[0][2:]
    prefix = "JHAM-" + mmyy + "-"

    # Direct database query so we always check true assigned UIDs even in Guest sessions
    rows = frappe.db.sql("""
        select uid from `tabPatient`
        where uid like %s
    """, (prefix + "%",), as_dict=True)

    existing_uids = set()
    max_seq = 0
    for r in rows:
        u = (r.get("uid") or "").strip()
        if u:
            existing_uids.add(u)
            parts = u.split("-")
            if len(parts) >= 3 and parts[-1].isdigit():
                val = int(parts[-1])
                if val > max_seq:
                    max_seq = val

    req_uid = (f.get("uid") or "").strip()
    # If a valid, unassigned UID was submitted and belongs to this month's prefix, accept it;
    # otherwise, assign the next unallocated sequence.
    if req_uid and req_uid.startswith(prefix) and req_uid not in existing_uids:
        assigned_uid = req_uid
    else:
        assigned_uid = prefix + str(max_seq + 1).zfill(6)

    p.uid = assigned_uid
    p.insert(ignore_permissions=True)
    patient = p.name

    # Force database persistence to bypass guest permission stripping on custom field
    try:
        frappe.db.set_value("Patient", patient, "uid", assigned_uid, update_modified=False)
    except:
        try:
            frappe.db.set_value("Patient", patient, "uid", assigned_uid)
        except:
            pass
    frappe.db.commit()

a = frappe.new_doc("Patient Appointment")
a.patient = patient
a.appointment_for = "Practitioner"
a.practitioner = f.get("practitioner")
a.appointment_type = f.get("appointment_type")
a.appointment_date = f.get("date")
a.appointment_time = f.get("time")
a.company = frappe.db.get_single_value("Global Defaults", "default_company")
a.notes = f.get("notes")
a.insert(ignore_permissions=True)

pt_name = (first + (" " + last if last else "")).strip() if first else patient
frappe.response["message"] = {
    "appointment": a.name,
    "patient": patient,
    "patient_name": pt_name,
    "uid": assigned_uid if mode != "existing" else (frappe.db.get_value("Patient", patient, "uid") or "")
}
