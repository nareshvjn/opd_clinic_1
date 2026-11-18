# Server Script: vitals_save
# type: API
# doctype: -
# event: Before Insert
# api_method: vitals_save
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
ok = False
for r in ["Healthcare Administrator", "System Manager", "Physician", "Nursing User", "Desk User"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
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
vitals = json.loads(f.get("vitals") or "{}")

if not patient_id and appt_id and frappe.db.exists("Patient Appointment", appt_id):
    patient_id = frappe.db.get_value("Patient Appointment", appt_id, "patient") or ""

if not patient_id:
    frappe.throw("Patient is required to record vitals.")

if not frappe.db.exists("Patient", patient_id):
    frappe.throw("Patient not found: " + patient_id)

company = frappe.db.get_single_value("Global Defaults", "default_company")

# Check existing doc for this appointment
old = []
if appt_id:
    old = frappe.get_all("Vital Signs", filters={"appointment": appt_id, "docstatus": 0},
        fields=["name"], limit=1)

if old:
    vs = frappe.get_doc("Vital Signs", old[0].name)
else:
    vs = frappe.new_doc("Vital Signs")
    vs.patient = patient_id
    vs.appointment = appt_id
    vs.company = company

vs.signs_date = frappe.utils.now_datetime()

meta = frappe.get_meta("Vital Signs")
for k in ["temperature", "pulse", "respiratory_rate", "bp_systolic", "bp_diastolic", "height", "weight"]:
    if meta.has_field(k):
        val = num(vitals.get(k))
        if val is not None:
            vs.set(k, val)
        else:
            vs.set(k, None)

# Calculate BMI
h = num(vitals.get("height"))
w = num(vitals.get("weight"))
if h and w and h > 0 and w > 0:
    bmi_val = round(w / ((h / 100.0) ** 2), 1)
    if meta.has_field("bmi"):
        vs.bmi = bmi_val
elif meta.has_field("bmi"):
    vs.bmi = None

# Optional note
note = (vitals.get("note") or vitals.get("nutrition_note") or "").strip()
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
