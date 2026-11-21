# Server Script: vitals_load
# type: API
# doctype: -
# event: Before Insert
# api_method: vitals_load
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
ok = False
for r in ["Healthcare Administrator", "System Manager", "Physician", "Nursing User", "Desk User"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to vitals.")

f = frappe.form_dict
appt_id = (f.get("appointment") or "").strip()
patient_id = (f.get("patient") or "").strip()
vitals_id = (f.get("vitals_id") or f.get("name") or "").strip()

if vitals_id and frappe.db.exists("Vital Signs", vitals_id):
    v_doc = frappe.get_doc("Vital Signs", vitals_id)
    if not patient_id:
        patient_id = v_doc.patient
    if not appt_id and v_doc.appointment:
        appt_id = v_doc.appointment

if not patient_id and appt_id and frappe.db.exists("Patient Appointment", appt_id):
    patient_id = frappe.db.get_value("Patient Appointment", appt_id, "patient") or ""

if not patient_id:
    frappe.throw("Patient is required.")

if not frappe.db.exists("Patient", patient_id):
    frappe.throw("Patient not found: " + patient_id)

patient = frappe.get_doc("Patient", patient_id)
if not patient.uid:
    today_str = str(frappe.utils.today())
    p_date = today_str.split("-")
    mmyy = p_date[1] + p_date[0][2:]
    prefix = "JHAM-" + mmyy + "-"
    records = frappe.get_all("Patient", filters={"uid": ["like", prefix + "%"]}, fields={"uid"}, limit=10000)
    max_seq = 0
    for r in records:
        u = r.get("uid") or ""
        parts = u.split("-")
        if len(parts) >= 3 and parts[-1].isdigit():
            val = int(parts[-1])
            if val > max_seq:
                max_seq = val
    new_uid = prefix + str(max_seq + 1).zfill(6)
    try:
        patient.db_set("uid", new_uid, update_modified=False)
        patient.uid = new_uid
    except:
        pass
today = frappe.utils.getdate(frappe.utils.today())
age = None
if patient.dob:
    d = frappe.utils.getdate(patient.dob)
    age = today.year - d.year - (1 if (today.month, today.day) < (d.month, d.day) else 0)

appt_info = {}
practitioner = (f.get("practitioner") or "").strip()
if appt_id and frappe.db.exists("Patient Appointment", appt_id):
    a = frappe.get_doc("Patient Appointment", appt_id)
    t = str(a.appointment_time).split(":")
    practitioner = a.practitioner or practitioner
    appt_info = {
        "id": a.name,
        "date": str(a.appointment_date),
        "time": t[0].zfill(2) + ":" + t[1] if len(t) >= 2 else str(a.appointment_time),
        "practitioner": a.practitioner or "",
        "practitioner_name": a.practitioner_name or "",
        "type": a.appointment_type or "",
        "status": a.status or ""
    }

# Current vitals for this appointment or specified vitals_id
current_vs = {}
if vitals_id and frappe.db.exists("Vital Signs", vitals_id):
    v = frappe.get_all("Vital Signs", filters={"name": vitals_id},
        fields=["name", "docstatus", "temperature", "pulse", "respiratory_rate",
                "bp_systolic", "bp_diastolic", "height", "weight", "bmi",
                "signs_date", "nutrition_note"], limit=1)
    if v:
        current_vs = v[0]
elif appt_id:
    v = frappe.get_all("Vital Signs", filters={"appointment": appt_id, "docstatus": ["<", 2]},
        fields=["name", "docstatus", "temperature", "pulse", "respiratory_rate",
                "bp_systolic", "bp_diastolic", "height", "weight", "bmi",
                "signs_date", "nutrition_note"],
        order_by="creation desc", limit=1)
    if v:
        current_vs = v[0]

# Previous vitals history for this patient
history = []
h_filters = {"patient": patient_id, "docstatus": ["<", 2]}
if current_vs and current_vs.get("name"):
    h_filters["name"] = ["!=", current_vs.get("name")]
elif appt_id:
    h_filters["appointment"] = ["!=", appt_id]

prev = frappe.get_all("Vital Signs", filters=h_filters,
    fields=["name", "docstatus", "signs_date", "creation", "temperature", "pulse", "respiratory_rate",
            "bp_systolic", "bp_diastolic", "height", "weight", "bmi", "nutrition_note"],
    order_by="creation desc", limit=10)

for p in prev:
    dt = str(p.get("signs_date") or p.get("creation") or "")
    history.append({
        "name": p.name,
        "docstatus": p.docstatus,
        "date": dt[:10],
        "time": dt[11:16] if len(dt) > 16 else "",
        "temperature": p.temperature,
        "pulse": p.pulse,
        "respiratory_rate": p.respiratory_rate,
        "bp_systolic": p.bp_systolic,
        "bp_diastolic": p.bp_diastolic,
        "height": p.height,
        "weight": p.weight,
        "bmi": p.bmi,
        "note": p.nutrition_note or ""
    })

token = ""
try:
    token = frappe.session.get("csrf_token") or ""
except:
    token = ""

frappe.response["message"] = {
    "patient": {
        "id": patient.name,
        "uid": patient.uid or patient.name,
        "name": patient.patient_name,
        "sex": patient.sex or "",
        "age": age,
        "mobile": patient.mobile or ""
    },
    "practitioner": practitioner,
    "appointment": appt_info,
    "vitals": current_vs,
    "history": history,
    "csrf": token
}
