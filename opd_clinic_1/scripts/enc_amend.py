# Server Script: enc_amend
# type: API
# doctype: -
# event: Before Insert
# api_method: enc_amend
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
admin = (user == "Administrator")
ok = admin
for r in ["Physician", "Healthcare Administrator", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
if not admin:
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

today_str = str(frappe.utils.today())
today_date = frappe.utils.getdate(today_str)
old_enc_date = frappe.utils.getdate(old.encounter_date) if old.encounter_date else today_date
appt_date = None
if old.appointment:
    ad = frappe.db.get_value("Patient Appointment", old.appointment, "appointment_date")
    if ad:
        appt_date = frappe.utils.getdate(ad)
if not admin and (old_enc_date < today_date or (appt_date and appt_date < today_date)):
    frappe.throw("Only admin accounts can modify past-dated consultations.")

req_enc_date = (f.get("encounter_date") or "").strip()
if req_enc_date:
    try:
        req_ed = frappe.utils.getdate(req_enc_date)
    except Exception:
        frappe.throw("Invalid consultation date.")
    if req_ed < today_date and not admin:
        frappe.throw("Only admin accounts can set a backdated consultation date.")

# Ensure patient has UID
if old.patient and frappe.db.exists("Patient", old.patient):
    p_uid = frappe.db.get_value("Patient", old.patient, "uid")
    if not p_uid:
        today_str = str(frappe.utils.today())
        p_date = today_str.split("-")
        mmyy = p_date[1] + p_date[0][2:]
        prefix = "JHAM-" + mmyy + "-"
        records = frappe.get_all("Patient", filters={"uid": ["like", prefix + "%"]}, fields=["uid"], limit=10000)
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
            frappe.db.set_value("Patient", old.patient, "uid", new_uid, update_modified=False)
            frappe.db.commit()
        except:
            try:
                frappe.db.set_value("Patient", old.patient, "uid", new_uid)
                frappe.db.commit()
            except:
                pass

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
if req_enc_date:
    new.encounter_date = req_enc_date
elif old.encounter_date:
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

        # 1. Resolve existing Medication strictly (do not create new Medication or Item)
        meta_med = frappe.get_meta("Medication") if frappe.db.exists("DocType", "Medication") else None
        has_med_name = meta_med.has_field("medication_name") if meta_med else False
        has_item_fld = meta_med.has_field("item") if meta_med else False
        has_item_code_fld = meta_med.has_field("item_code") if meta_med else False

        med = None
        if meta_med:
            med = frappe.db.get_value("Medication", nm, "name")
            if not med and has_med_name:
                med = frappe.db.get_value("Medication", {"medication_name": nm}, "name")

        if not med:
            frappe.throw("Medication '" + nm + "' is not available in the Medication list. Please select an existing medication.")

        # 2. Resolve linked Item without creating one
        item_code = None
        if has_item_fld:
            item_code = frappe.db.get_value("Medication", med, "item")
        elif has_item_code_fld:
            item_code = frappe.db.get_value("Medication", med, "item_code")
        if not item_code and frappe.db.exists("DocType", "Medication Linked Item"):
            try:
                item_code = frappe.db.get_value("Medication Linked Item", {"parent": med}, "item")
            except Exception:
                item_code = None
        if not item_code and frappe.db.exists("Item", med):
            item_code = frappe.db.get_value("Item", med, "name")
        if not item_code and frappe.db.exists("Item", nm):
            item_code = frappe.db.get_value("Item", nm, "name")
        if not item_code:
            try:
                item_code = frappe.db.get_value("Item", {"item_name": med}, "name") or frappe.db.get_value("Item", {"item_code": nm}, "name")
            except Exception:
                item_code = None

        # 3. Dosage form
        if not form and med:
            try:
                form = frappe.db.get_value("Medication", med, "dosage_form") or ""
            except Exception:
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
        except Exception:
            target_dt = "Item"

        if target_dt == "Medication":
            final_code = med
        else:
            final_code = item_code
            if not final_code or not frappe.db.exists(target_dt, final_code):
                frappe.throw("Medication '" + med + "' does not have a linked " + target_dt + ".")

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
has_lab_dt = frappe.db.exists("DocType", "Lab Test Template")
lt_meta = frappe.get_meta("Lab Test Template") if has_lab_dt else None
lab_rx_meta = None
lab_target_dt = "Lab Test Template"
try:
    lab_rx_meta = frappe.get_meta("Lab Prescription")
    df_lab = lab_rx_meta.get_field("lab_test_code")
    if df_lab and df_lab.options:
        lab_target_dt = df_lab.options
except Exception:
    lab_target_dt = "Lab Test Template"

for lt in labs:
    lt_val = (lt or "").strip()
    if not lt_val:
        continue
    lt_name = None
    lt_item = ""
    lt_label = ""
    if has_lab_dt:
        lt_name = frappe.db.get_value("Lab Test Template", lt_val, "name")
        if not lt_name and lt_meta:
            for fld in ("item", "item_code", "lab_test_name", "lab_test_code"):
                if lt_meta.has_field(fld):
                    try:
                        lt_name = frappe.db.get_value("Lab Test Template", {fld: lt_val}, "name")
                        if lt_name:
                            break
                    except Exception:
                        pass
        if not lt_name:
            frappe.throw("Lab test '" + lt_val + "' was not found in Lab Test Template. Please choose a test from the list.")
        if lt_meta:
            for fld in ("item", "item_code", "lab_test_code"):
                if lt_meta.has_field(fld):
                    try:
                        val = (frappe.db.get_value("Lab Test Template", lt_name, fld) or "").strip()
                        if val:
                            lt_item = val
                            break
                    except Exception:
                        pass
            if lt_meta.has_field("lab_test_name"):
                try:
                    lt_label = (frappe.db.get_value("Lab Test Template", lt_name, "lab_test_name") or "").strip()
                except Exception:
                    pass
    else:
        lt_name = lt_val
        lt_item = lt_val

    if lab_target_dt == "Item":
        if not lt_item or not frappe.db.exists("Item", lt_item):
            frappe.throw("Lab test '" + lt_name + "' does not have a linked Item.")
        final_lab_code = lt_item
    else:
        final_lab_code = lt_name

    lab_row = {"lab_test_code": final_lab_code}
    if lab_rx_meta:
        if lt_item and lab_rx_meta.has_field("item"):
            lab_row["item"] = lt_item
        elif lt_item and lab_rx_meta.has_field("item_code"):
            lab_row["item_code"] = lt_item
        if lt_label and lab_rx_meta.has_field("lab_test_name"):
            lab_row["lab_test_name"] = lt_label
    new.append("lab_test_prescription", lab_row)

new.insert(ignore_permissions=True)
if complete:
    new.submit()

frappe.response["message"] = {"encounter": new.name, "appointment": new.appointment, "completed": complete}
