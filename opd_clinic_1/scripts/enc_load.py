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

# Look up existing consultation / fee invoice (excluding drug/pharmacy/stock/lab-only invoices)
inv_out = None
inv_check_date = (enc.get("date") if enc else "") or (str(appt.appointment_date) if appt else "")
if current_appt_name or current_enc_name or (patient_id and inv_check_date):
    try:
        inv_cands = []
        seen_cands = set()
        direct_appt_inv = set()
        direct_enc_inv = set()
        if current_appt_name:
            for r in frappe.get_all("Sales Invoice Item",
                    filters={"reference_dt": "Patient Appointment", "reference_dn": current_appt_name},
                    fields=["parent"], limit=50):
                if r.parent:
                    direct_appt_inv.add(r.parent)
                    if r.parent not in seen_cands:
                        seen_cands.add(r.parent)
                        inv_cands.append(r.parent)
        if current_enc_name:
            for r in frappe.get_all("Sales Invoice Item",
                    filters={"reference_dt": "Patient Encounter", "reference_dn": current_enc_name},
                    fields=["parent"], limit=50):
                if r.parent:
                    direct_enc_inv.add(r.parent)
                    if r.parent not in seen_cands:
                        seen_cands.add(r.parent)
                        inv_cands.append(r.parent)
        si_meta = frappe.get_meta("Sales Invoice")
        if current_appt_name and si_meta.has_field("appointment"):
            for r in frappe.get_all("Sales Invoice",
                    filters={"appointment": current_appt_name, "docstatus": ["<", 2]},
                    fields=["name"], limit=20):
                if r.name:
                    direct_appt_inv.add(r.name)
                    if r.name not in seen_cands:
                        seen_cands.add(r.name)
                        inv_cands.append(r.name)
        if current_enc_name:
            for efld in ("encounter", "patient_encounter"):
                if si_meta.has_field(efld):
                    for r in frappe.get_all("Sales Invoice",
                            filters={efld: current_enc_name, "docstatus": ["<", 2]},
                            fields=["name"], limit=20):
                        if r.name:
                            direct_enc_inv.add(r.name)
                            if r.name not in seen_cands:
                                seen_cands.add(r.name)
                                inv_cands.append(r.name)
        for mk_pfx, mk_id, mk_set in (
            ("Consultation: ", current_appt_name, direct_appt_inv),
            ("Encounter: ", current_enc_name, direct_enc_inv),
        ):
            if mk_id:
                mk = mk_pfx + mk_id
                for r in frappe.get_all("Sales Invoice",
                        filters={"remarks": ["like", "%" + mk + "%"], "docstatus": ["<", 2]},
                        fields=["name", "remarks"], limit=20):
                    rem = r.get("remarks") or ""
                    pos = rem.find(mk)
                    if pos < 0:
                        continue
                    aft = rem[pos + len(mk):pos + len(mk) + 1]
                    if aft and aft not in " \t\r\n|,;":
                        continue
                    if r.name:
                        mk_set.add(r.name)
                        if r.name not in seen_cands:
                            seen_cands.add(r.name)
                            inv_cands.append(r.name)
        if patient_id and inv_check_date and si_meta.has_field("patient"):
            for r in frappe.get_all("Sales Invoice",
                    filters={"patient": patient_id, "posting_date": str(inv_check_date), "docstatus": ["<", 2]},
                    fields=["name"], order_by="docstatus desc, modified desc", limit=25):
                if r.name and r.name not in seen_cands:
                    seen_cands.add(r.name)
                    inv_cands.append(r.name)

        if inv_cands:
            consult_codes = {"CONSULT-GEN"}
            try:
                if frappe.db.exists("DocType", "Healthcare Practitioner"):
                    for hp in frappe.get_all("Healthcare Practitioner", fields=["op_consulting_charge_item"], limit=200):
                        if hp.get("op_consulting_charge_item"):
                            consult_codes.add(hp.get("op_consulting_charge_item"))
            except Exception:
                pass
            drug_codes = set()
            try:
                if frappe.db.exists("DocType", "Medication"):
                    m_meta_i = frappe.get_meta("Medication")
                    for mf in ("item", "item_code"):
                        if m_meta_i.has_field(mf):
                            for mr in frappe.get_all("Medication", fields=[mf], limit=2000):
                                if mr.get(mf):
                                    drug_codes.add(mr.get(mf))
                if frappe.db.exists("DocType", "Medication Linked Item"):
                    mli_i = frappe.get_meta("Medication Linked Item")
                    if mli_i.has_field("item"):
                        for mr in frappe.get_all("Medication Linked Item", fields=["item"], limit=2000):
                            if mr.get("item"):
                                drug_codes.add(mr.get("item"))
            except Exception:
                pass

            si_flds = ["name", "docstatus", "grand_total", "is_return", "modified", "update_stock", "set_warehouse", "remarks"]
            for opt_f in ("patient", "appointment", "encounter", "patient_encounter", "ref_practitioner", "practitioner"):
                if si_meta.has_field(opt_f):
                    si_flds.append(opt_f)
            sii_flds = ["item_code", "item_name", "description"]
            try:
                sii_m = frappe.get_meta("Sales Invoice Item")
                for opt_f in ("batch_no", "warehouse", "item_group", "is_stock_item", "reference_dt", "reference_dn"):
                    if sii_m.has_field(opt_f):
                        sii_flds.append(opt_f)
            except Exception:
                pass
            item_flds = ["name", "item_name"]
            try:
                itm_m = frappe.get_meta("Item")
                for opt_f in ("item_group", "is_stock_item"):
                    if itm_m.has_field(opt_f):
                        item_flds.append(opt_f)
            except Exception:
                pass
            item_map_inv = {}
            prac_id_chk = (appt.practitioner if appt else "") or (curr_enc.practitioner if (enc_id and frappe.db.exists("Patient Encounter", enc_id)) else "") or ""

            best_inv = None
            best_rank = None
            for cname in inv_cands:
                vals = frappe.db.get_value("Sales Invoice", cname, si_flds, as_dict=True)
                if not vals or int(vals.get("docstatus") or 0) >= 2 or int(vals.get("is_return") or 0):
                    continue
                if int(vals.get("docstatus") or 0) == 1:
                    try:
                        if frappe.db.exists("Sales Invoice", {"return_against": vals.name, "docstatus": 1}):
                            continue
                    except Exception:
                        pass
                inv_pat = vals.get("patient") or ""
                if patient_id and inv_pat and inv_pat != patient_id:
                    continue
                inv_appt = str(vals.get("appointment") or "").strip()
                if current_appt_name and inv_appt and inv_appt != current_appt_name:
                    continue
                inv_enc = str(vals.get("encounter") or vals.get("patient_encounter") or "").strip()
                if current_enc_name and inv_enc and inv_enc != current_enc_name:
                    continue
                is_direct_appt = cname in direct_appt_inv
                is_direct_enc = cname in direct_enc_inv
                is_direct = is_direct_appt or is_direct_enc
                if not is_direct and prac_id_chk:
                    inv_prac = str(vals.get("ref_practitioner") or vals.get("practitioner") or "").strip()
                    if inv_prac and inv_prac != prac_id_chk:
                        continue
                if int(vals.get("update_stock") or 0) == 1:
                    continue

                inv_items = frappe.get_all("Sales Invoice Item", filters={"parent": cname}, fields=sii_flds, limit=100)
                other_ref = False
                matched_ref = False
                miss_codes = []
                for it in inv_items:
                    rdt = str(it.get("reference_dt") or "").strip()
                    rdn = str(it.get("reference_dn") or "").strip()
                    if rdt == "Patient Appointment" and rdn:
                        if current_appt_name and rdn == current_appt_name:
                            matched_ref = True
                        elif current_appt_name and rdn != current_appt_name:
                            other_ref = True
                    if rdt == "Patient Encounter" and rdn:
                        if current_enc_name and rdn == current_enc_name:
                            matched_ref = True
                        elif current_enc_name and rdn != current_enc_name:
                            other_ref = True
                    ic = str(it.get("item_code") or "").strip()
                    if ic and ic not in item_map_inv and ic not in miss_codes:
                        miss_codes.append(ic)
                if other_ref and not matched_ref and not is_direct:
                    continue
                if inv_enc and not current_enc_name and not is_direct:
                    continue
                if miss_codes:
                    try:
                        for itm in frappe.get_all("Item", filters={"name": ["in", miss_codes]}, fields=item_flds):
                            item_map_inv[itm.name] = itm
                    except Exception:
                        pass
                    for mc in miss_codes:
                        item_map_inv.setdefault(mc, {})

                has_drug = False
                all_drug = bool(inv_items)
                all_lab = bool(inv_items)
                has_consult = False
                has_fee_svc = False
                for it in inv_items:
                    ic = str(it.get("item_code") or "").strip()
                    im = item_map_inv.get(ic) or {}
                    ig = str(it.get("item_group") or im.get("item_group") or "").strip().lower()
                    is_stk = int(im.get("is_stock_item") or it.get("is_stock_item") or 0)
                    has_bch = bool(str(it.get("batch_no") or "").strip())
                    rdt = str(it.get("reference_dt") or "").strip()
                    rtxt = " ".join([ic, str(it.get("item_name") or ""), str(im.get("item_name") or ""), str(it.get("description") or ""), ig]).lower()
                    is_drg = (
                        rdt == "Drug Prescription"
                        or has_bch
                        or is_stk == 1
                        or (bool(ic) and ic in drug_codes)
                        or ("drug" in ig) or ("medic" in ig) or ("pharm" in ig)
                        or ("consult" not in rtxt and ("drug" in rtxt or "medic" in rtxt or "pharm" in rtxt or "tablet" in rtxt or "capsule" in rtxt or "syrup" in rtxt))
                    )
                    is_lb = (
                        rdt in ("Lab Test", "Sample Collection", "Radiology", "Clinical Procedure")
                        or ("lab" in ig and "consult" not in rtxt)
                        or ("diagnostic" in ig and "consult" not in rtxt)
                    )
                    is_con = (not is_drg) and (
                        (bool(ic) and ic in consult_codes)
                        or ("consult" in rtxt) or ("opd" in rtxt)
                        or ("doctor visit" in rtxt) or ("doctor fee" in rtxt) or ("checkup" in rtxt)
                    )
                    if is_drg:
                        has_drug = True
                    else:
                        all_drug = False
                        if not is_lb:
                            has_fee_svc = True
                    if not is_lb:
                        all_lab = False
                    if is_con:
                        has_consult = True

                rem_str = str(vals.get("remarks") or "")
                rem_con = False
                if current_appt_name:
                    mk = "Consultation: " + current_appt_name
                    mi = rem_str.find(mk)
                    if mi >= 0:
                        ma = rem_str[mi + len(mk):mi + len(mk) + 1]
                        if not ma or ma not in " \t\r\n|,;":
                            rem_con = True
                has_wh = bool(str(vals.get("set_warehouse") or "").strip())
                if all_drug:
                    continue
                if (has_drug or has_wh) and not has_consult:
                    continue
                if all_lab and not has_consult:
                    continue
                if not (has_fee_svc or has_consult or rem_con) and not is_direct_appt:
                    continue

                rank = (1 if int(vals.get("docstatus") or 0) == 1 else 0, 1 if (has_consult or rem_con) else 0, 2 if is_direct_appt else (1 if is_direct_enc else 0), str(vals.get("modified") or ""))
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_inv = vals
            if best_inv:
                inv_out = {
                    "name": best_inv.name,
                    "docstatus": int(best_inv.get("docstatus") or 0),
                    "total": float(best_inv.get("grand_total") or 0),
                }
    except Exception:
        inv_out = None

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
                    for mli in frappe.get_all("Medication Linked Item", fields=["parent", "item"], limit=5000):
                        par = (mli.get("parent") or "").strip()
                        itm = (mli.get("item") or "").strip()
                        if par and itm and par not in med_linked:
                            med_linked[par] = itm
            except Exception:
                pass
        for m in frappe.get_all("Medication", fields=m_fields, limit=5000):
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
        for lt in frappe.get_all("Lab Test Template", fields=lt_fields, limit=5000):
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

if frappe.form_dict.get("only_invoice") == "1":
    frappe.response["message"] = {"invoice": inv_out}
else:
    frappe.response["message"] = {
        "patient": {"id": pat.name, "uid": pat.uid or "", "name": pat.patient_name, "age": age,
                    "sex": pat.sex or "", "mobile": pat.mobile or ""},
        "appointment": appt_out,
        "practitioner": appt.practitioner if appt else "",
        "encounter": enc,
        "invoice": inv_out,
        "vitals": vit,
        "history": history,
        "templates": templates,
        "lists": {
            "complaints": names("Complaint", limit=None),
            "diagnoses": names("Diagnosis", limit=None),
            "medications": names("Medication", limit=None),
            "items": stock_items,
            "item_groups": igs,
            "dosages": names("Prescription Dosage"),
            "periods": names("Prescription Duration"),
            "labs": names("Lab Test Template", limit=None),
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
