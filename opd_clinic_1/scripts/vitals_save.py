# Server Script: vitals_save
# type: API
# doctype: -
# event: Before Insert
# api_method: vitals_save
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = (user == "Administrator")
if not is_admin:
    for r in ["Healthcare Administrator", "System Manager"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            is_admin = True
            break
ok = is_admin
if not ok:
    for r in ["Physician", "Nursing User", "Desk User"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            ok = True
            break
if not ok:
    frappe.throw("You don't have access to record vitals.")

def num(v):
    try:
        val = float(v or 0)
        return val if val > 0 else None
    except:
        return None

f = frappe.form_dict
appt_id = (f.get("appointment") or "").strip()
patient_id = (f.get("patient") or "").strip()
vitals_id = (f.get("vitals_id") or f.get("name") or "").strip()
vitals = json.loads(f.get("vitals") or "{}")
req_signs_date = (f.get("signs_date") or "").strip()

if vitals_id and frappe.db.exists("Vital Signs", vitals_id):
    v_doc = frappe.get_doc("Vital Signs", vitals_id)
    if not patient_id:
        patient_id = v_doc.patient
    if not appt_id and v_doc.appointment:
        appt_id = v_doc.appointment

today_date = frappe.utils.getdate(frappe.utils.today())
appt_date = None
appt_time = None
if appt_id and frappe.db.exists("Patient Appointment", appt_id):
    ad_vals = frappe.db.get_value("Patient Appointment", appt_id, ["patient", "appointment_date", "appointment_time"], as_dict=True)
    if ad_vals:
        if not patient_id:
            patient_id = ad_vals.patient or ""
        appt_date = ad_vals.appointment_date
        appt_time = ad_vals.appointment_time

if appt_date and frappe.utils.getdate(appt_date) < today_date and not is_admin:
    frappe.throw("Only admin accounts can record or modify vitals for past-dated appointments.")

if req_signs_date:
    try:
        req_sd = frappe.utils.getdate(req_signs_date)
    except Exception:
        frappe.throw("Invalid vitals date.")
    if req_sd < today_date and not is_admin:
        frappe.throw("Only admin accounts can record backdated vitals.")

if not patient_id:
    frappe.throw("Patient is required to record vitals.")

if not frappe.db.exists("Patient", patient_id):
    frappe.throw("Patient not found: " + patient_id)

company = frappe.db.get_single_value("Global Defaults", "default_company")

# Check existing doc by vitals_id or appointment
vs = None
if vitals_id and frappe.db.exists("Vital Signs", vitals_id):
    vs = frappe.get_doc("Vital Signs", vitals_id)
elif appt_id:
    old = frappe.get_all("Vital Signs", filters={"appointment": appt_id, "docstatus": ["<", 2]},
        fields=["name"], order_by="creation desc", limit=1)
    if old:
        vs = frappe.get_doc("Vital Signs", old[0].name)

if vs and vs.get("signs_date") and frappe.utils.getdate(str(vs.signs_date)[:10]) < today_date and not is_admin:
    frappe.throw("Only admin accounts can modify past-dated vitals.")

if not vs:
    vs = frappe.new_doc("Vital Signs")
    vs.patient = patient_id
    vs.appointment = appt_id
    vs.company = company
    target_sdate = None
    if req_signs_date:
        target_sdate = frappe.utils.getdate(req_signs_date)
    elif appt_date and frappe.utils.getdate(appt_date) <= today_date:
        target_sdate = frappe.utils.getdate(appt_date)
    if target_sdate and target_sdate < today_date:
        t_str = str(appt_time or frappe.utils.nowtime()).split(".")[0]
        vs.signs_date = frappe.utils.get_datetime(str(target_sdate) + " " + t_str)
    else:
        vs.signs_date = frappe.utils.now_datetime()

# Calculate BMI
h = num(vitals.get("height"))
w = num(vitals.get("weight"))
bmi_val = None
if h and w and h > 0 and w > 0:
    bmi_val = round(w / ((h / 100.0) ** 2), 1)

note = (vitals.get("note") or vitals.get("nutrition_note") or "").strip()
meta = frappe.get_meta("Vital Signs")

if vs.docstatus == 1:
    # Submitted document - update via db_set
    for k in ["temperature", "pulse", "respiratory_rate", "bp_systolic", "bp_diastolic", "height", "weight"]:
        if meta.has_field(k):
            val = num(vitals.get(k))
            vs.db_set(k, val, update_modified=True)
    if meta.has_field("bmi"):
        vs.db_set("bmi", bmi_val, update_modified=True)
    if meta.has_field("nutrition_note"):
        vs.db_set("nutrition_note", note, update_modified=True)
    frappe.db.commit()
else:
    # Draft document or new document
    for k in ["temperature", "pulse", "respiratory_rate", "bp_systolic", "bp_diastolic", "height", "weight"]:
        if meta.has_field(k):
            val = num(vitals.get(k))
            if val is not None:
                vs.set(k, val)
            else:
                vs.set(k, None)

    if meta.has_field("bmi"):
        vs.bmi = bmi_val
    if meta.has_field("nutrition_note"):
        vs.nutrition_note = note

    if vs.is_new():
        vs.insert(ignore_permissions=True)
    else:
        vs.save(ignore_permissions=True)

frappe.response["message"] = {
    "vitals": vs.name,
    "docstatus": vs.docstatus,
    "bmi": vs.get("bmi"),
    "saved": True
}
