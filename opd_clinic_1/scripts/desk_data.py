# Server Script: desk_data
# type: API
# doctype: -
# event: Before Insert
# api_method: desk_data
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = (user == "Administrator")
if not is_admin and frappe.db.exists("Has Role", {"parent": user, "role": "Healthcare Administrator"}):
    is_admin = True
if not is_admin and frappe.db.exists("Has Role", {"parent": user, "role": "System Manager"}):
    is_admin = True
is_doctor = bool(frappe.db.exists("Has Role", {"parent": user, "role": "Physician"}))
if not (is_admin or is_doctor):
    frappe.throw("You don't have access to the doctor desk.")

date = frappe.form_dict.get("date") or frappe.utils.today()
mine = frappe.get_all("Healthcare Practitioner", filters={"user_id": user},
    fields=["name", "practitioner_name"], limit=1)
my_prac = mine[0].name if mine else ""

# If practitioner is explicitly sent in form_dict (even if empty string for "All doctors"):
req_prac = frappe.form_dict.get("practitioner")
if "practitioner" in frappe.form_dict:
    prac = req_prac or ""
else:
    # First load / default: filter by logged-in doctor if linked!
    prac = my_prac

if is_admin:
    practitioners = frappe.get_all("Healthcare Practitioner", filters={"status": "Active"},
        fields=["name", "practitioner_name"], order_by="practitioner_name")
    can_pick = True
elif mine:
    prac = my_prac
    practitioners = [mine[0]]
    can_pick = False
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
            fields=["name", "dob", "sex", "mobile", "uid"]):
        info[p.name] = p

def find_invoice_info(appt):
    active_draft = None
    try:
        for r in frappe.get_all("Sales Invoice Item",
                filters={"reference_dt": "Patient Appointment", "reference_dn": appt},
                fields=["parent"], order_by="modified desc", limit=20):
            vals = frappe.db.get_value("Sales Invoice", r.parent, ["name", "docstatus", "grand_total"], as_dict=True)
            if not vals or vals.docstatus >= 2:
                continue
            if vals.docstatus == 1:
                return vals
            if active_draft is None:
                active_draft = vals
    except:
        pass
    found = frappe.get_all("Sales Invoice",
        filters={"remarks": ["like", "%Consultation: " + appt + "%"], "docstatus": ["<", 2]},
        fields=["name", "docstatus", "grand_total"], order_by="docstatus desc, modified desc", limit=1)
    if found:
        return found[0]
    return active_draft

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
    inv_info = find_invoice_info(r.name)
    inv = inv_info.name if inv_info else ""
    inv_docstatus = inv_info.docstatus if inv_info else None
    inv_total = float(inv_info.grand_total or 0) if inv_info else 0.0
    enc_found = frappe.get_all("Patient Encounter",
        filters={"appointment": r.name, "docstatus": ["!=", 2]}, fields=["name"], limit=1)
    has_encounter = bool(enc_found or r.status in ["Closed", "Checked Out"])
    vs_found = frappe.get_all("Vital Signs",
        filters={"appointment": r.name, "docstatus": ["<", 2]}, fields=["name"], limit=1)
    if not vs_found and r.patient:
        vs_found = frappe.get_all("Vital Signs",
            filters={"patient": r.patient, "signs_date": ["between", [str(date) + " 00:00:00", str(date) + " 23:59:59"]], "docstatus": ["<", 2]},
            fields=["name"], limit=1)
    has_vitals = bool(vs_found)
    t = str(r.appointment_time).split(":")
    out.append({
        "id": r.name, "patient": r.patient, "uid": (p.uid if p and p.uid else ""), "name": r.patient_name,
        "age": age, "sex": sex, "mobile": mobile,
        "practitioner": r.practitioner, "practitioner_name": r.practitioner_name,
        "time": t[0].zfill(2) + ":" + t[1], "duration": r.duration,
        "type": r.appointment_type, "status": r.status, "notes": r.notes or "", "invoice": inv,
        "invoice_docstatus": inv_docstatus,
        "invoice_total": inv_total,
        "has_encounter": has_encounter,
        "has_vitals": has_vitals,
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
    "appointments": out, "practitioners": practitioners, "prac": prac, "my_prac": my_prac,
    "can_pick": can_pick, "is_admin": is_admin, "today": str(frappe.utils.today()),
    "statuses": statuses, "csrf": token, "modes": modes,
}
