# Server Script: enc_save
# type: API
# doctype: -
# event: Before Insert
# api_method: enc_save
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = (user == "Administrator")
if not is_admin:
    for r in ["Healthcare Administrator", "System Manager"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            is_admin = True
            break
ok = is_admin
if not ok and frappe.db.exists("Has Role", {"parent": user, "role": "Physician"}):
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

today_str = str(frappe.utils.today())
today_date = frappe.utils.getdate(today_str)
appt_date = None
appt_time = None
if appt_id and frappe.db.exists("Patient Appointment", appt_id):
    ad_vals = frappe.db.get_value("Patient Appointment", appt_id, ["appointment_date", "appointment_time"], as_dict=True)
    if ad_vals:
        appt_date = ad_vals.appointment_date
        appt_time = ad_vals.appointment_time
if appt_date and frappe.utils.getdate(appt_date) < today_date and not is_admin:
    frappe.throw("Only admin accounts can create or save consultations for past-dated appointments.")

req_enc_date = (f.get("encounter_date") or "").strip()
if req_enc_date:
    try:
        req_ed = frappe.utils.getdate(req_enc_date)
    except Exception:
        frappe.throw("Invalid consultation date.")
    if req_ed < today_date and not is_admin:
        frappe.throw("Only admin accounts can save backdated consultations.")

target_enc_date = req_enc_date or (
    str(appt_date) if (appt_date and frappe.utils.getdate(appt_date) <= today_date) else today_str
)

# Ensure patient has UID
if patient and frappe.db.exists("Patient", patient):
    p_uid = frappe.db.get_value("Patient", patient, "uid")
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
            frappe.db.set_value("Patient", patient, "uid", new_uid, update_modified=False)
            frappe.db.commit()
        except:
            try:
                frappe.db.set_value("Patient", patient, "uid", new_uid)
                frappe.db.commit()
            except:
                pass

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
        if target_enc_date and frappe.utils.getdate(target_enc_date) < today_date:
            t_str = str(appt_time or frappe.utils.nowtime()).split(".")[0]
            vs.signs_date = frappe.utils.get_datetime(str(target_enc_date) + " " + t_str)
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
        if enc.get("encounter_date") and frappe.utils.getdate(enc.encounter_date) < today_date and not is_admin:
            frappe.throw("Only admin accounts can modify past-dated consultations.")
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

if req_enc_date:
    enc.encounter_date = req_enc_date
elif not enc.get("encounter_date"):
    enc.encounter_date = target_enc_date
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
    enc.append("drug_prescription", row)
enc.set("lab_test_prescription", [])
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
    enc.append("lab_test_prescription", lab_row)

if fresh:
    enc.insert(ignore_permissions=True)
else:
    enc.save(ignore_permissions=True)

if complete:
    if vs and vs.docstatus == 0:
        vs.submit()
    elif appt_id:
        unsub_vs = frappe.get_all("Vital Signs", filters={"appointment": appt_id, "docstatus": 0}, fields=["name"], limit=1)
        if unsub_vs:
            try:
                frappe.get_doc("Vital Signs", unsub_vs[0].name).submit()
            except Exception:
                pass
    enc.submit()

frappe.response["message"] = {"encounter": enc.name, "completed": complete}
