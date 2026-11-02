# Server Script: enc_load
# type: API
# doctype: -
# event: Before Insert
# api_method: enc_load
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = False
for r in ["Healthcare Administrator", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        is_admin = True
ok = is_admin
for r in ["Physician", "Nursing User"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to consultations.")

def names(dt):
    out = []
    try:
        for r in frappe.get_all(dt, fields=["name"], order_by="name", limit=500):
            out.append(r.name)
    except:
        pass
    return out

appt_id = frappe.form_dict.get("appointment")
patient_id = frappe.form_dict.get("patient")
enc_id = (frappe.form_dict.get("encounter") or "").strip()

if enc_id and frappe.db.exists("Patient Encounter", enc_id):
    curr_enc = frappe.get_doc("Patient Encounter", enc_id)
    if not patient_id:
        patient_id = curr_enc.patient
    if not appt_id and curr_enc.appointment:
        appt_id = curr_enc.appointment
appt = None
if appt_id:
    appt = frappe.get_doc("Patient Appointment", appt_id)
    patient_id = appt.patient
    if not is_admin:
        mine = frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, "name")
        if mine and appt.practitioner != mine:
            frappe.throw("This appointment belongs to another doctor.")
if not patient_id:
    frappe.throw("No patient selected. Open this page from the doctor desk.")

pat = frappe.get_doc("Patient", patient_id)
age = None
if pat.dob:
    d = frappe.utils.getdate(pat.dob)
    t = frappe.utils.getdate(frappe.utils.today())
    age = t.year - d.year - (1 if (t.month, t.day) < (d.month, d.day) else 0)

enc = None
vit = None
if enc_id and frappe.db.exists("Patient Encounter", enc_id):
    e = frappe.get_doc("Patient Encounter", enc_id)
    enc = {
        "name": e.name,
        "docstatus": e.docstatus,
        "amended_from": e.amended_from or "",
        "comment": e.encounter_comment or "",
        "symptoms": [x.complaint for x in e.symptoms],
        "diagnosis": [x.diagnosis for x in e.diagnosis],
        "drugs": [{"drug": x.drug_code, "form": x.dosage_form or "", "dosage": x.dosage or "",
                   "period": x.period or "", "comment": x.comment or ""} for x in e.drug_prescription],
        "labs": [x.lab_test_code for x in e.lab_test_prescription],
    }
elif appt_id:
    found = frappe.get_all("Patient Encounter",
        filters={"appointment": appt_id, "docstatus": ["<", 2]}, fields=["name"], limit=1)
    if found:
        e = frappe.get_doc("Patient Encounter", found[0].name)
        enc = {
            "name": e.name,
            "docstatus": e.docstatus,
            "amended_from": e.amended_from or "",
            "comment": e.encounter_comment or "",
            "symptoms": [x.complaint for x in e.symptoms],
            "diagnosis": [x.diagnosis for x in e.diagnosis],
            "drugs": [{"drug": x.drug_code, "form": x.dosage_form or "", "dosage": x.dosage or "",
                       "period": x.period or "", "comment": x.comment or ""} for x in e.drug_prescription],
            "labs": [x.lab_test_code for x in e.lab_test_prescription],
        }
    v = frappe.get_all("Vital Signs", filters={"appointment": appt_id, "docstatus": ["<", 2]},
        fields=["name", "docstatus", "temperature", "pulse", "respiratory_rate",
                "bp_systolic", "bp_diastolic", "height", "weight"], limit=1)
    if v:
        vit = v[0]

current_enc_name = enc.get("name") if enc else ""
current_appt_name = appt_id or ""

history = []
hx_filters = {"patient": patient_id, "docstatus": 1}
if current_enc_name:
    hx_filters["name"] = ["!=", current_enc_name]
elif current_appt_name:
    hx_filters["appointment"] = ["!=", current_appt_name]

for h in frappe.get_all("Patient Encounter", filters=hx_filters,
        fields=["name", "appointment", "encounter_date", "encounter_comment"],
        order_by="encounter_date desc", limit=5):
    if current_enc_name and h.name == current_enc_name:
        continue
    if current_appt_name and h.appointment == current_appt_name:
        continue
    hd = frappe.get_doc("Patient Encounter", h.name)
    history.append({
        "encounter": h.name,
        "name": h.name,
        "date": str(h.encounter_date),
        "appointment": h.appointment or "",
        "diagnosis": [x.diagnosis for x in hd.diagnosis],
        "comment": h.encounter_comment or "",
    })

# Pharmacy stock items that are not Medications yet (including ones with no batches or no stock).
# Choosing one in the consultation creates the Medication and links it to that item.
stock_items = []
try:
    meds = names("Medication")
    linked = []
    try:
        for r in frappe.get_all("Medication", fields=["item"], limit=500):
            if r.get("item"):
                linked.append(r.get("item"))
    except:
        pass
    try:
        for r in frappe.get_all("Medication Linked Item", fields=["item"], limit=2000):
            if r.get("item"):
                linked.append(r.get("item"))
    except:
        pass
    cands = frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1, "item_group": "Drug"},
        fields=["name", "item_name"], order_by="item_name", limit=500)
    if len(cands) < 500:
        for x in frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1, "has_batch_no": 1},
                fields=["name", "item_name"], order_by="item_name", limit=500):
            dup = False
            for y in cands:
                if y.name == x.name:
                    dup = True
            if not dup:
                cands.append(x)
    for x in cands:
        nm = x.item_name or x.name
        if x.name in linked or nm in meds or x.name in meds or nm in stock_items:
            continue
        stock_items.append(nm)
except:
    pass

igs = []
try:
    for r in frappe.get_all("Item Group", filters={"is_group": 0}, fields=["name"], order_by="name", limit=200):
        igs.append(r.name)
except:
    pass

med_forms = {}
try:
    for m in frappe.get_all("Medication", fields=["name", "dosage_form"], limit=500):
        if m.dosage_form:
            med_forms[m.name] = m.dosage_form
except:
    pass

token = ""
try:
    token = frappe.session.get("csrf_token") or ""
except:
    token = ""

appt_out = None
if appt:
    appt_out = {"id": appt.name, "date": str(appt.appointment_date),
                "time": str(appt.appointment_time), "type": appt.appointment_type}

frappe.response["message"] = {
    "patient": {"id": pat.name, "name": pat.patient_name, "age": age,
                "sex": pat.sex or "", "mobile": pat.mobile or ""},
    "appointment": appt_out,
    "practitioner": appt.practitioner if appt else "",
    "encounter": enc,
    "vitals": vit,
    "history": history,
    "lists": {
        "complaints": names("Complaint"),
        "diagnoses": names("Diagnosis"),
        "medications": names("Medication"),
        "items": stock_items,
        "item_groups": igs,
        "dosages": names("Prescription Dosage"),
        "periods": names("Prescription Duration"),
        "labs": names("Lab Test Template"),
        "forms": names("Dosage Form"),
        "classes": names("Medication Class"),
        "uoms": names("UOM"),
    },
    "med_forms": med_forms,
    "csrf": token,
}
