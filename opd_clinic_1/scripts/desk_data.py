# Server Script: desk_data
# type: API
# doctype: -
# event: Before Insert
# api_method: desk_data
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = False
if frappe.db.exists("Has Role", {"parent": user, "role": "Healthcare Administrator"}):
    is_admin = True
if frappe.db.exists("Has Role", {"parent": user, "role": "System Manager"}):
    is_admin = True
is_doctor = bool(frappe.db.exists("Has Role", {"parent": user, "role": "Physician"}))
if not (is_admin or is_doctor):
    frappe.throw("You don't have access to the doctor desk.")

date = frappe.form_dict.get("date") or frappe.utils.today()
mine = frappe.get_all("Healthcare Practitioner", filters={"user_id": user},
    fields=["name", "practitioner_name"], limit=1)

if mine and not is_admin:
    prac = mine[0].name
    practitioners = [mine[0]]
    can_pick = False
elif is_admin:
    prac = frappe.form_dict.get("practitioner") or ""
    practitioners = frappe.get_all("Healthcare Practitioner", filters={"status": "Active"},
        fields=["name", "practitioner_name"], order_by="practitioner_name")
    can_pick = True
else:
    frappe.throw("Your user isn't linked to a Healthcare Practitioner. Ask an administrator to set the User ID on your practitioner record.")

filters = {"appointment_date": date, "status": ["!=", "Cancelled"]}
if prac:
    filters["practitioner"] = prac
rows = frappe.get_all("Patient Appointment", filters=filters,
    fields=["name", "patient", "patient_name", "practitioner", "practitioner_name",
            "appointment_time", "duration", "appointment_type", "status", "notes"],
    order_by="appointment_time asc")

info = {}
if rows:
    ids = []
    for r in rows:
        ids.append(r.patient)
    for p in frappe.get_all("Patient", filters={"name": ["in", ids]},
            fields=["name", "dob", "sex", "mobile"]):
        info[p.name] = p

def find_invoice(appt):
    try:
        for r in frappe.get_all("Sales Invoice Item",
                filters={"reference_dt": "Patient Appointment", "reference_dn": appt},
                fields=["parent"], limit=5):
            if frappe.db.get_value("Sales Invoice", r.parent, "docstatus") < 2:
                return r.parent
    except:
        pass
    found = frappe.get_all("Sales Invoice",
        filters={"remarks": ["like", "%Consultation: " + appt + "%"], "docstatus": ["<", 2]},
        fields=["name"], limit=1)
    if found:
        return found[0].name
    return ""

today = frappe.utils.getdate(frappe.utils.today())
out = []
for r in rows:
    p = info.get(r.patient)
    age = None
    sex = ""
    mobile = ""
    if p:
        sex = p.sex or ""
        mobile = p.mobile or ""
        if p.dob:
            d = frappe.utils.getdate(p.dob)
            age = today.year - d.year - (1 if (today.month, today.day) < (d.month, d.day) else 0)
    inv = ""
    if r.status in ["Closed", "Checked Out"]:
        inv = find_invoice(r.name)
    has_encounter = bool(frappe.db.exists("Patient Encounter",
        {"appointment": r.name, "docstatus": ["<", 2]}))
    t = str(r.appointment_time).split(":")
    out.append({
        "id": r.name, "patient": r.patient, "name": r.patient_name,
        "age": age, "sex": sex, "mobile": mobile,
        "practitioner": r.practitioner, "practitioner_name": r.practitioner_name,
        "time": t[0].zfill(2) + ":" + t[1], "duration": r.duration,
        "type": r.appointment_type, "status": r.status, "notes": r.notes or "", "invoice": inv,
        "has_encounter": has_encounter,
    })

statuses = []
for s in (frappe.get_meta("Patient Appointment").get_field("status").options or "").split("\n"):
    if s:
        statuses.append(s)

modes = []
for m in frappe.get_all("Mode of Payment", filters={"enabled": 1}, fields=["name"], order_by="name"):
    modes.append(m.name)

token = ""
try:
    token = frappe.session.get("csrf_token") or ""
except:
    token = ""

frappe.response["message"] = {
    "appointments": out, "practitioners": practitioners, "prac": prac,
    "can_pick": can_pick, "statuses": statuses, "csrf": token, "modes": modes,
}
