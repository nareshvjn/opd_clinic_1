# Server Script: enc_load
# type: API
# doctype: -
# event: Before Insert
# api_method: enc_load
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = (user == "Administrator")
if not is_admin:
    for r in ["Healthcare Administrator", "System Manager"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            is_admin = True
ok = is_admin
for r in ["Physician", "Nursing User"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to consultations.")

def names(dt, limit=500):
    out = []
    try:
        if limit:
            records = frappe.get_all(dt, fields=["name"], order_by="name", limit=limit)
        else:
            records = frappe.get_all(dt, fields=["name"], order_by="name")
        for r in records:
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
if not pat.uid:
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
    pat.uid = new_uid
    try:
        frappe.db.set_value("Patient", pat.name, "uid", new_uid, update_modified=False)
        frappe.db.commit()
    except:
        try:
            frappe.db.set_value("Patient", pat.name, "uid", new_uid)
            frappe.db.commit()
        except:
            pass
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
        "date": str(e.encounter_date or ""),
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
            "date": str(e.encounter_date or ""),
            "comment": e.encounter_comment or "",
            "symptoms": [x.complaint for x in e.symptoms],
            "diagnosis": [x.diagnosis for x in e.diagnosis],
            "drugs": [{"drug": x.drug_code, "form": x.dosage_form or "", "dosage": x.dosage or "",
                       "period": x.period or "", "comment": x.comment or ""} for x in e.drug_prescription],
            "labs": [x.lab_test_code for x in e.lab_test_prescription],
        }
    v = frappe.get_all("Vital Signs", filters={"appointment": appt_id, "docstatus": ["<", 2]},
        fields=["name", "docstatus", "temperature", "pulse", "respiratory_rate",
                "bp_systolic", "bp_diastolic", "height", "weight", "bmi", "signs_date"], limit=1)
    if not v and patient_id:
        v = frappe.get_all("Vital Signs", filters={"patient": patient_id, "docstatus": ["<", 2]},
            fields=["name", "docstatus", "temperature", "pulse", "respiratory_rate",
                    "bp_systolic", "bp_diastolic", "height", "weight", "bmi", "signs_date"],
            order_by="signs_date desc", limit=1)
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

# Auto-cleanup: rename any Medications that were prefixed with "Tablet "
if frappe.db.exists("DocType", "Medication"):
    try:
        bad_meds = frappe.get_all("Medication", filters=[["name", "like", "Tablet %"]], fields=["name"], limit=50)
        for bm in bad_meds:
            clean_name = bm.name
            if clean_name.startswith("Tablet "):
                clean_name = clean_name[7:]
            elif clean_name.startswith("tablet "):
                clean_name = clean_name[7:]
            if clean_name.endswith(" mg"):
                clean_name = clean_name[:-3]
            clean_name = clean_name.strip()
            if clean_name and clean_name != bm.name and not frappe.db.exists("Medication", clean_name):
                try:
                    frappe.rename_doc("Medication", bm.name, clean_name, ignore_permissions=True)
                except Exception:
                    pass
    except Exception:
        pass

stock_items = []

igs = []
try:
    for r in frappe.get_all("Item Group", filters={"is_group": 0}, fields=["name"], order_by="name", limit=200):
        igs.append(r.name)
except:
    pass

med_forms = {}
med_meta = {}
med_by_alias = {}
if frappe.db.exists("DocType", "Medication"):
    try:
        m_meta_doc = frappe.get_meta("Medication")
        m_fields = ["name"]
        for kf in ("dosage_form", "generic_name", "medication_name", "item", "item_code"):
            if m_meta_doc.has_field(kf):
                m_fields.append(kf)
        med_linked = {}
        if frappe.db.exists("DocType", "Medication Linked Item"):
            try:
                mli_meta = frappe.get_meta("Medication Linked Item")
                if mli_meta.has_field("item") and mli_meta.has_field("parent"):
                    for mli in frappe.get_all("Medication Linked Item", fields=["parent", "item"], limit=2000):
                        par = (mli.get("parent") or "").strip()
                        itm = (mli.get("item") or "").strip()
                        if par and itm and par not in med_linked:
                            med_linked[par] = itm
            except Exception:
                pass
        for m in frappe.get_all("Medication", fields=m_fields, limit=1000):
            med_by_alias[m.name.lower()] = m.name
            if m.get("dosage_form"):
                med_forms[m.name] = m.get("dosage_form")
            hint_parts = []
            seen_hints = {m.name.lower()}
            for kf in ("medication_name", "generic_name", "item", "item_code"):
                val = (m.get(kf) or "").strip()
                if val:
                    if kf != "generic_name":
                        med_by_alias.setdefault(val.lower(), m.name)
                    if val.lower() not in seen_hints:
                        seen_hints.add(val.lower())
                        hint_parts.append(val)
            linked_item = med_linked.get(m.name, "")
            if linked_item:
                med_by_alias.setdefault(linked_item.lower(), m.name)
                if linked_item.lower() not in seen_hints:
                    seen_hints.add(linked_item.lower())
                    hint_parts.append(linked_item)
            if m.get("dosage_form"):
                hint_parts.append(m.get("dosage_form"))
            if hint_parts:
                med_meta[m.name] = " | ".join(hint_parts)
    except Exception:
        pass

lab_meta = {}
lab_items = {}
lab_by_alias = {}
if frappe.db.exists("DocType", "Lab Test Template"):
    try:
        lt_meta_doc = frappe.get_meta("Lab Test Template")
        lt_fields = ["name"]
        for kf in ("lab_test_name", "item", "item_code", "lab_test_code"):
            if lt_meta_doc.has_field(kf):
                lt_fields.append(kf)
        for lt in frappe.get_all("Lab Test Template", fields=lt_fields, limit=1000):
            lab_by_alias[lt.name.lower()] = lt.name
            lt_item = (lt.get("item") or lt.get("item_code") or lt.get("lab_test_code") or "").strip()
            if lt_item:
                lab_items[lt.name] = lt_item
            hint_parts = []
            seen_hints = {lt.name.lower()}
            for kf in ("item", "item_code", "lab_test_code", "lab_test_name"):
                val = (lt.get(kf) or "").strip()
                if val:
                    lab_by_alias.setdefault(val.lower(), lt.name)
                    if val.lower() not in seen_hints:
                        seen_hints.add(val.lower())
                        hint_parts.append(val)
            if hint_parts:
                lab_meta[lt.name] = " | ".join(hint_parts)
    except Exception:
        pass

if enc:
    for dr in enc.get("drugs") or []:
        dc = (dr.get("drug") or "").strip()
        if dc:
            canon = med_by_alias.get(dc.lower(), dc)
            dr["drug"] = canon
            if not dr.get("form") and med_forms.get(canon):
                dr["form"] = med_forms[canon]
    norm_labs = []
    for lv in enc.get("labs") or []:
        ls = (lv or "").strip()
        if ls:
            norm_labs.append(lab_by_alias.get(ls.lower(), ls))
    enc["labs"] = norm_labs

token = ""
try:
    token = frappe.session.get("csrf_token") or ""
except:
    token = ""

appt_out = None
if appt:
    appt_out = {"id": appt.name, "date": str(appt.appointment_date),
                "time": str(appt.appointment_time), "type": appt.appointment_type}

templates = []
if frappe.db.exists("DocType", "Clinic Treatment Template"):
    try:
        tpl_rows = frappe.get_all(
            "Clinic Treatment Template",
            filters={"is_active": 1},
            fields=["name", "template_name", "practitioner", "notes", "summary", "template_json"],
            order_by="template_name asc",
            limit=200,
        )
        cur_prac = (appt.practitioner if appt else "") or frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, "name") or ""
        for tr in tpl_rows:
            data = {}
            try:
                if tr.get("template_json"):
                    data = json.loads(tr.get("template_json")) or {}
            except Exception:
                data = {}
            raw_tpl_drugs = data.get("drugs") or []
            norm_tpl_drugs = []
            for dr in raw_tpl_drugs:
                if isinstance(dr, str):
                    dr = {"drug": dr}
                elif not isinstance(dr, dict):
                    continue
                dnm = (dr.get("drug") or dr.get("drug_code") or dr.get("medication") or dr.get("item") or dr.get("name") or "").strip()
                if not dnm:
                    continue
                canon_d = med_by_alias.get(dnm.lower(), dnm)
                norm_tpl_drugs.append({
                    "drug": canon_d,
                    "form": (dr.get("form") or dr.get("dosage_form") or med_forms.get(canon_d) or "").strip(),
                    "dosage": (dr.get("dosage") or "").strip(),
                    "period": (dr.get("period") or "").strip(),
                    "comment": (dr.get("comment") or "").strip(),
                })
            norm_tpl_labs = []
            for lv in (data.get("labs") or []):
                ls = (str(lv or "")).strip()
                if ls:
                    canon_l = lab_by_alias.get(ls.lower(), ls)
                    if canon_l not in norm_tpl_labs:
                        norm_tpl_labs.append(canon_l)
            templates.append({
                "name": tr.get("name"),
                "template_name": tr.get("template_name") or tr.get("name"),
                "practitioner": tr.get("practitioner") or "",
                "summary": tr.get("summary") or "",
                "complaints": data.get("complaints") or [],
                "diagnosis": data.get("diagnosis") or [],
                "drugs": norm_tpl_drugs,
                "labs": norm_tpl_labs,
                "notes": data.get("notes") if data.get("notes") is not None else (tr.get("notes") or ""),
            })
        if cur_prac:
            own = []
            shared = []
            others = []
            for t in templates:
                if t["practitioner"] == cur_prac:
                    own.append(t)
                elif not t["practitioner"]:
                    shared.append(t)
                else:
                    others.append(t)
            templates = own + shared + others
    except Exception:
        templates = []

frappe.response["message"] = {
    "patient": {"id": pat.name, "uid": pat.uid or "", "name": pat.patient_name, "age": age,
                "sex": pat.sex or "", "mobile": pat.mobile or ""},
    "appointment": appt_out,
    "practitioner": appt.practitioner if appt else "",
    "encounter": enc,
    "vitals": vit,
    "history": history,
    "templates": templates,
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
        "classes": names("Medication Class", limit=None),
        "uoms": names("UOM"),
    },
    "med_forms": med_forms,
    "med_meta": med_meta,
    "lab_meta": lab_meta,
    "lab_items": lab_items,
    "is_admin": is_admin,
    "today": str(frappe.utils.today()),
    "csrf": token,
}
