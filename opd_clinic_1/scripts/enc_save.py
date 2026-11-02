# Server Script: enc_save
# type: API
# doctype: -
# event: Before Insert
# api_method: enc_save
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
ok = False
for r in ["Physician", "Healthcare Administrator", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
if not ok:
    frappe.throw("Only doctors can save a consultation.")

f = frappe.form_dict
appt_id = f.get("appointment")
patient = f.get("patient")
prac = f.get("practitioner")
complete = f.get("complete") == "1" or f.get("complete") is True
if not patient or not prac:
    frappe.throw("Open this page from the doctor desk so the patient and doctor are known.")

company = frappe.db.get_single_value("Global Defaults", "default_company")
symptoms = json.loads(f.get("symptoms") or "[]")
diagnoses = json.loads(f.get("diagnosis") or "[]")
drugs = json.loads(f.get("drugs") or "[]")
labs = json.loads(f.get("labs") or "[]")
vitals = json.loads(f.get("vitals") or "{}")

for c in symptoms:
    if not frappe.db.exists("Complaint", c):
        frappe.get_doc({"doctype": "Complaint", "complaints": c}).insert(ignore_permissions=True)
for d in diagnoses:
    if not frappe.db.exists("Diagnosis", d):
        frappe.get_doc({"doctype": "Diagnosis", "diagnosis": d}).insert(ignore_permissions=True)

# Vital signs (optional)
vs = None
has_vitals = False
for k in vitals:
    if vitals.get(k):
        has_vitals = True
if has_vitals:
    old = []
    if appt_id:
        old = frappe.get_all("Vital Signs", filters={"appointment": appt_id, "docstatus": 0},
            fields=["name"], limit=1)
    if old:
        vs = frappe.get_doc("Vital Signs", old[0].name)
    else:
        vs = frappe.new_doc("Vital Signs")
        vs.patient = patient
        vs.appointment = appt_id
        vs.company = company
    for k in ["temperature", "pulse", "respiratory_rate", "bp_systolic", "bp_diastolic", "height", "weight"]:
        if vitals.get(k):
            vs.set(k, float(vitals.get(k)))
    if old:
        vs.save(ignore_permissions=True)
    else:
        vs.insert(ignore_permissions=True)

# Encounter
enc = None
fresh = True
old_name = ""
if appt_id:
    found = frappe.get_all("Patient Encounter",
        filters={"appointment": appt_id, "docstatus": ["<", 2]}, fields=["name"], limit=1)
    if found:
        enc = frappe.get_doc("Patient Encounter", found[0].name)
        fresh = False
        if enc.docstatus == 1:
            frappe.throw("This consultation is already completed. Use enc_amend to edit it.")
if not enc:
    enc = frappe.new_doc("Patient Encounter")
    enc.patient = patient
    enc.practitioner = prac
    enc.appointment = appt_id
    enc.company = company
    if old_name:
        enc.amended_from = old_name

enc.encounter_comment = f.get("comment") or ""
enc.set("symptoms", [])
for c in symptoms:
    enc.append("symptoms", {"complaint": c})
enc.set("diagnosis", [])
for d in diagnoses:
    enc.append("diagnosis", {"diagnosis": d})
enc.set("drug_prescription", [])
for dr in drugs:
    nm = (dr.get("drug") or "").strip()
    if not nm:
        continue
    med = frappe.db.exists("Medication", nm)
    if not med:
        med = frappe.db.get_value("Medication", {"generic_name": nm}, "name")
    if not med:
        try:
            med = frappe.db.get_value("Medication", {"item": nm}, "name")
        except:
            med = None
    if not med:
        try:
            med = frappe.db.get_value("Medication Linked Item", {"item": nm}, "parent")
        except:
            med = None
    form = dr.get("form") or ""
    if not med:
        if not form:
            frappe.throw("Choose a dosage form for the new medicine " + nm + ".")
        cls = dr.get("mclass") or ""
        if not cls:
            first = frappe.get_all("Medication Class", fields=["name"], limit=1)
            if first:
                cls = first[0].name
        if not cls:
            try:
                frappe.get_doc({"doctype": "Medication Class", "medication_class": "General"}).insert(ignore_permissions=True)
                cls = "General"
            except:
                frappe.throw("Create a Medication Class in Desk first, or choose one for the new medicine.")
        strength = dr.get("strength")
        unit = (dr.get("unit") or "").strip()
        if not strength or not unit:
            frappe.throw("Enter the strength and unit of the new medicine " + nm + " (for example 10 and mg).")
        if not frappe.db.exists("UOM", unit):
            frappe.get_doc({"doctype": "UOM", "uom_name": unit}).insert(ignore_permissions=True)
        # Marley links every medication to an Item: use the pharmacy item if there is one, else create it
        item = None
        if frappe.db.exists("Item", nm):
            item = nm
        else:
            item = frappe.db.get_value("Item", {"item_name": nm}, "name")
        if not item:
            grp = "Drug"
            if not frappe.db.exists("Item Group", "Drug"):
                grp = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
            it = frappe.new_doc("Item")
            it.item_code = nm
            it.item_name = nm
            it.item_group = grp
            it.stock_uom = "Nos"
            it.is_stock_item = 1
            it.has_batch_no = 1
            it.has_expiry_date = 1
            it.create_new_batch = 0
            it.insert(ignore_permissions=True)
            item = it.name
        m = frappe.new_doc("Medication")
        m.generic_name = nm
        m.item_code = item
        m.item = item
        m.dosage_form = form
        m.medication_class = cls
        m.strength = float(strength)
        m.strength_uom = unit
        m.insert(ignore_permissions=True)
        med = m.name
    if not form:
        form = frappe.db.get_value("Medication", med, "dosage_form") or ""
    if not form:
        frappe.throw("Choose a dosage form for " + nm + ".")
    row = {"drug_code": med, "dosage_form": form, "comment": dr.get("comment") or ""}
    if dr.get("dosage"):
        row["dosage"] = dr.get("dosage")
    if dr.get("period"):
        row["period"] = dr.get("period")
    enc.append("drug_prescription", row)
enc.set("lab_test_prescription", [])
for lt in labs:
    enc.append("lab_test_prescription", {"lab_test_code": lt})

if fresh:
    enc.insert(ignore_permissions=True)
else:
    enc.save(ignore_permissions=True)

if complete:
    if vs and vs.docstatus == 0:
        vs.submit()
    enc.submit()

frappe.response["message"] = {"encounter": enc.name, "completed": complete}
