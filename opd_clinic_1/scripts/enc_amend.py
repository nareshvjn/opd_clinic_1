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
else:
    new.encounter_date = frappe.utils.today()
if old.get("encounter_time"):
    new.encounter_time = old.encounter_time
else:
    new.encounter_time = frappe.utils.nowtime()

if old.get("appointment_type"):
    new.appointment_type = old.appointment_type
else:
    appt_type = None
    if old.appointment:
        appt_type = frappe.db.get_value("Patient Appointment", old.appointment, "appointment_type")
    if not appt_type and frappe.db.exists("DocType", "Appointment Type"):
        appt_type = frappe.db.get_value("Appointment Type", {}, "name")
    if appt_type:
        new.appointment_type = appt_type
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
