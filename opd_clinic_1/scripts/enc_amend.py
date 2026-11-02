# Server Script: enc_amend
# type: API
# doctype: -
# event: Before Insert
# api_method: enc_amend
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
admin = False
ok = False
for r in ["Physician", "Healthcare Administrator", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
for r in ["Healthcare Administrator", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        admin = True
if not ok:
    frappe.throw("Only doctors can edit a consultation.")

f = frappe.form_dict
name = (f.get("encounter") or "").strip()
if not name:
    appt = (f.get("appointment") or "").strip()
    if appt:
        enc = frappe.get_all("Patient Encounter", filters={"appointment": appt, "docstatus": 1},
            fields=["name"], order_by="modified desc", limit=1)
        if enc:
            name = enc[0].name
if not name or not frappe.db.exists("Patient Encounter", name):
    frappe.throw("That consultation was not found.")
old = frappe.get_doc("Patient Encounter", name)
if old.docstatus != 1:
    frappe.throw("Only a completed consultation can be edited this way.")
if not old.appointment:
    frappe.throw("This consultation has no appointment, so it cannot be reopened from this page. Amend it in Desk.")
if not admin:
    mine = frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, "name")
    if mine and old.practitioner != mine:
        frappe.throw("This consultation belongs to another doctor.")

# Check if form data with updated symptoms/diagnosis/drugs was submitted
has_form_data = "symptoms" in f or "diagnosis" in f or "drugs" in f
complete = f.get("complete") == "1" or f.get("complete") is True

symptoms = json.loads(f.get("symptoms") or "[]") if has_form_data else [x.complaint for x in old.symptoms]
diagnoses = json.loads(f.get("diagnosis") or "[]") if has_form_data else [x.diagnosis for x in old.diagnosis]
drugs = json.loads(f.get("drugs") or "[]") if has_form_data else None
labs = json.loads(f.get("labs") or "[]") if has_form_data else [x.lab_test_code for x in old.lab_test_prescription]

for c in symptoms:
    if not frappe.db.exists("Complaint", c):
        frappe.get_doc({"doctype": "Complaint", "complaints": c}).insert(ignore_permissions=True)
for d in diagnoses:
    if not frappe.db.exists("Diagnosis", d):
        frappe.get_doc({"doctype": "Diagnosis", "diagnosis": d}).insert(ignore_permissions=True)

# Marley creates a Medication Request for each medicine when an encounter is completed.
# They block the cancel, so cancel them first (completing the amended copy creates fresh ones).
reqs = []
link_fields = ["order_group", "patient_encounter", "encounter", "reference_dn"]
try:
    for df in frappe.get_meta("Medication Request").fields:
        if df.fieldtype == "Link" and df.options == "Patient Encounter" and df.fieldname not in link_fields:
            link_fields.append(df.fieldname)
except:
    pass

for fld in link_fields:
    try:
        for x in frappe.get_all("Medication Request", filters={fld: old.name}, fields=["name", "docstatus"]):
            seen = False
            for y in reqs:
                if y.name == x.name:
                    seen = True
            if not seen:
                reqs.append(x)
    except:
        pass
for x in reqs:
    mr = frappe.get_doc("Medication Request", x.name)
    mr.flags.ignore_permissions = True
    try:
        if mr.docstatus == 1:
            mr.cancel()
        elif mr.docstatus == 0:
            frappe.delete_doc("Medication Request", mr.name, ignore_permissions=True)
    except Exception as e:
        frappe.throw("Could not cancel Medication Request " + mr.name + ": " + str(e))

old.flags.ignore_permissions = True
try:
    old.cancel()
except Exception as e:
    frappe.throw("Could not cancel the completed consultation: " + str(e))

new = frappe.new_doc("Patient Encounter")
new.patient = old.patient
new.practitioner = old.practitioner
new.appointment = old.appointment
new.company = old.company
new.encounter_comment = (f.get("comment") if has_form_data else old.encounter_comment) or ""
if old.encounter_date:
    new.encounter_date = old.encounter_date
new.amended_from = old.name

new.set("symptoms", [])
for c in symptoms:
    new.append("symptoms", {"complaint": c})
new.set("diagnosis", [])
for d in diagnoses:
    new.append("diagnosis", {"diagnosis": d})

new.set("drug_prescription", [])
if drugs is not None:
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
        new.append("drug_prescription", row)
else:
    for x in old.drug_prescription:
        row = {"drug_code": x.drug_code, "dosage_form": x.dosage_form, "comment": x.comment or ""}
        if x.dosage:
            row["dosage"] = x.dosage
        if x.period:
            row["period"] = x.period
        new.append("drug_prescription", row)

new.set("lab_test_prescription", [])
for lt in labs:
    new.append("lab_test_prescription", {"lab_test_code": lt})

new.insert(ignore_permissions=True)
if complete:
    new.submit()

frappe.response["message"] = {"encounter": new.name, "appointment": new.appointment, "completed": complete}
