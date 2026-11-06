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

# Ensure appointment_type, encounter_date and encounter_time are set
if not enc.get("appointment_type"):
    appt_type = None
    if appt_id:
        appt_type = frappe.db.get_value("Patient Appointment", appt_id, "appointment_type")
    if not appt_type:
        appt_type = f.get("appointment_type")
    if not appt_type and frappe.db.exists("DocType", "Appointment Type"):
        appt_type = frappe.db.get_value("Appointment Type", {}, "name")
    if appt_type:
        enc.appointment_type = appt_type

if not enc.get("encounter_date"):
    enc.encounter_date = frappe.utils.today()
if not enc.get("encounter_time"):
    enc.encounter_time = frappe.utils.nowtime()

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

    form = (dr.get("form") or "").strip()
    strength = dr.get("strength")
    unit = (dr.get("unit") or "").strip()
    cls = (dr.get("mclass") or "").strip()

    # 1. Resolve or create Item (medicine name saved as both item_code and item_name)
    item_code = None
    if frappe.db.exists("Item", nm):
        item_code = nm
    else:
        try:
            item_code = frappe.db.get_value("Item", {"item_name": nm}, "name")
        except:
            pass
    if not item_code:
        try:
            item_code = frappe.db.get_value("Item", {"item_code": nm}, "name")
        except:
            pass

    meta_med = frappe.get_meta("Medication") if frappe.db.exists("DocType", "Medication") else None
    has_med_name = meta_med.has_field("medication_name") if meta_med else False
    has_item_fld = meta_med.has_field("item") if meta_med else False
    has_item_code_fld = meta_med.has_field("item_code") if meta_med else False
    has_generic_fld = meta_med.has_field("generic_name") if meta_med else False

    if not item_code and meta_med:
        if frappe.db.exists("Medication", nm):
            if has_item_fld:
                item_code = frappe.db.get_value("Medication", nm, "item")
            elif has_item_code_fld:
                item_code = frappe.db.get_value("Medication", nm, "item_code")

    if not item_code:
        grp = "Drug"
        if not frappe.db.exists("Item Group", "Drug"):
            grp = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
        
        stock_uom = "Nos"
        if unit:
            if not frappe.db.exists("UOM", unit):
                try:
                    frappe.get_doc({"doctype": "UOM", "uom_name": unit}).insert(ignore_permissions=True)
                except:
                    pass
            if frappe.db.exists("UOM", unit):
                stock_uom = unit
        if not frappe.db.exists("UOM", stock_uom):
            try:
                frappe.get_doc({"doctype": "UOM", "uom_name": stock_uom}).insert(ignore_permissions=True)
            except:
                pass

        try:
            it = frappe.new_doc("Item")
            it.item_code = nm
            it.item_name = nm
            it.item_group = grp
            it.stock_uom = stock_uom
            it.is_stock_item = 1
            it.has_batch_no = 1
            it.has_expiry_date = 1
            it.create_new_batch = 0
            it.flags.ignore_mandatory = True
            it.insert(ignore_permissions=True, ignore_mandatory=True)
            item_code = it.name or nm
        except Exception:
            item_code = frappe.db.exists("Item", nm) or nm

    # 2. Resolve or create Medication
    med = None
    if meta_med:
        if frappe.db.exists("Medication", nm):
            med = nm
        if not med:
            for pfx in ["Tablet ", "tablet "]:
                for sfx in [" mg", ""]:
                    old_cand = pfx + nm + sfx
                    if frappe.db.exists("Medication", old_cand):
                        try:
                            frappe.rename_doc("Medication", old_cand, nm, ignore_permissions=True)
                            med = nm
                            break
                        except Exception:
                            med = old_cand
                            break
                if med:
                    break

        if not med and item_code:
            if has_item_fld:
                med = frappe.db.get_value("Medication", {"item": item_code}, "name")
            elif has_item_code_fld:
                med = frappe.db.get_value("Medication", {"item_code": item_code}, "name")
        if not med and has_generic_fld:
            med = frappe.db.get_value("Medication", {"generic_name": nm}, "name")
        if not med and has_med_name:
            med = frappe.db.get_value("Medication", {"medication_name": nm}, "name")
        if not med and item_code and frappe.db.exists("DocType", "Medication Linked Item"):
            try:
                med = frappe.db.get_value("Medication Linked Item", {"item": item_code}, "parent")
            except:
                pass

        if not med:
            if not cls:
                first_cls = frappe.get_all("Medication Class", fields=["name"], limit=1)
                if first_cls:
                    cls = first_cls[0].name
                elif frappe.db.exists("DocType", "Medication Class"):
                    try:
                        frappe.get_doc({"doctype": "Medication Class", "medication_class": "General"}).insert(ignore_permissions=True)
                        cls = "General"
                    except:
                        pass

            st_val = 1.0
            if strength:
                try:
                    st_val = float(strength)
                except:
                    st_val = 1.0

            uom_val = unit or "Nos"
            if not frappe.db.exists("UOM", uom_val):
                try:
                    frappe.get_doc({"doctype": "UOM", "uom_name": uom_val}).insert(ignore_permissions=True)
                except:
                    pass

            try:
                m = frappe.new_doc("Medication")
                m.name = nm
                m.flags.name_set = True
                if has_med_name:
                    m.medication_name = nm
                if has_generic_fld:
                    m.generic_name = nm
                if has_item_fld:
                    m.item = item_code
                if has_item_code_fld:
                    m.item_code = item_code
                if form and meta_med.has_field("dosage_form"):
                    m.dosage_form = form
                if cls and meta_med.has_field("medication_class"):
                    m.medication_class = cls
                if meta_med.has_field("strength"):
                    m.strength = st_val
                if meta_med.has_field("strength_uom"):
                    m.strength_uom = uom_val
                m.flags.ignore_mandatory = True
                m.insert(ignore_permissions=True, ignore_mandatory=True)
                med = m.name or nm
            except Exception:
                med = None

    # 3. Dosage form
    if not form and med:
        try:
            form = frappe.db.get_value("Medication", med, "dosage_form") or ""
        except:
            pass
    if not form:
        first_form = frappe.get_all("Dosage Form", fields=["name"], limit=1)
        if first_form:
            form = first_form[0].name
        else:
            form = "Tablet"

    # 4. Target field linking for Drug Prescription.drug_code
    target_dt = "Item"
    try:
        df = frappe.get_meta("Drug Prescription").get_field("drug_code")
        if df and df.options:
            target_dt = df.options
    except:
        target_dt = "Item"

    final_code = item_code
    if target_dt == "Medication" and med and frappe.db.exists("Medication", med):
        final_code = med
    elif target_dt == "Item" and item_code and frappe.db.exists("Item", item_code):
        final_code = item_code
    elif frappe.db.exists(target_dt, item_code):
        final_code = item_code
    elif med and frappe.db.exists(target_dt, med):
        final_code = med
    else:
        final_code = item_code or med

    row = {
        "drug_code": final_code,
        "dosage_form": form,
        "comment": dr.get("comment") or ""
    }
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
