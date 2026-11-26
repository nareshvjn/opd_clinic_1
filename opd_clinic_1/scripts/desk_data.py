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
            "appointment_date", "appointment_time", "duration", "appointment_type", "status", "notes"],
    order_by="appointment_time asc")

inv_cache = {
    "consult_items": set(["CONSULT-GEN"]),
    "drug_items": set(),
    "items": {},
}
try:
    hp_meta = frappe.get_meta("Healthcare Practitioner")
    if hp_meta.has_field("op_consulting_charge_item"):
        for hp in frappe.get_all("Healthcare Practitioner", fields=["op_consulting_charge_item"], limit=200):
            if hp.get("op_consulting_charge_item"):
                inv_cache["consult_items"].add(hp.get("op_consulting_charge_item"))
except Exception:
    pass
try:
    if frappe.db.exists("DocType", "Medication"):
        med_meta = frappe.get_meta("Medication")
        for mf in ("item", "item_code"):
            if med_meta.has_field(mf):
                for mr in frappe.get_all("Medication", fields=[mf], limit=2000):
                    if mr.get(mf):
                        inv_cache["drug_items"].add(mr.get(mf))
    if frappe.db.exists("DocType", "Medication Linked Item"):
        mli_meta = frappe.get_meta("Medication Linked Item")
        if mli_meta.has_field("item"):
            for mr in frappe.get_all("Medication Linked Item", fields=["item"], limit=2000):
                if mr.get("item"):
                    inv_cache["drug_items"].add(mr.get("item"))
except Exception:
    pass

info = {}
if rows:
    ids = []
    for r in rows:
        ids.append(r.patient)
    for p in frappe.get_all("Patient", filters={"name": ["in", ids]},
            fields=["name", "dob", "sex", "mobile", "uid"]):
        info[p.name] = p

def find_invoice_info(appt, patient_id=None, encounter_id=None, appt_date=None, prac_id=None, cache=None):
    if not appt and not encounter_id and not (patient_id and appt_date):
        return None
    if cache is None:
        cache = {}
    consult_codes = set(cache.get("consult_items") or ["CONSULT-GEN"])
    drug_codes = set(cache.get("drug_items") or [])
    item_cache = cache.setdefault("items", {})

    direct_appt_names = set()
    direct_enc_names = set()
    pat_date_names = set()
    seen_candidates = set()
    candidate_names = []

    if appt:
        try:
            for r in frappe.get_all("Sales Invoice Item",
                    filters={"reference_dt": "Patient Appointment", "reference_dn": appt},
                    fields=["parent"], limit=50):
                if r.parent:
                    direct_appt_names.add(r.parent)
                    if r.parent not in seen_candidates:
                        seen_candidates.add(r.parent)
                        candidate_names.append(r.parent)
        except Exception:
            pass

    if encounter_id:
        try:
            for r in frappe.get_all("Sales Invoice Item",
                    filters={"reference_dt": "Patient Encounter", "reference_dn": encounter_id},
                    fields=["parent"], limit=50):
                if r.parent:
                    direct_enc_names.add(r.parent)
                    if r.parent not in seen_candidates:
                        seen_candidates.add(r.parent)
                        candidate_names.append(r.parent)
        except Exception:
            pass

    si_meta = None
    try:
        si_meta = frappe.get_meta("Sales Invoice")
        if appt and si_meta.has_field("appointment"):
            for r in frappe.get_all("Sales Invoice",
                    filters={"appointment": appt, "docstatus": ["<", 2]},
                    fields=["name"], limit=20):
                if r.name:
                    direct_appt_names.add(r.name)
                    if r.name not in seen_candidates:
                        seen_candidates.add(r.name)
                        candidate_names.append(r.name)
        if encounter_id:
            for enc_fld in ("encounter", "patient_encounter"):
                if si_meta.has_field(enc_fld):
                    for r in frappe.get_all("Sales Invoice",
                            filters={enc_fld: encounter_id, "docstatus": ["<", 2]},
                            fields=["name"], limit=20):
                        if r.name:
                            direct_enc_names.add(r.name)
                            if r.name not in seen_candidates:
                                seen_candidates.add(r.name)
                                candidate_names.append(r.name)
    except Exception:
        pass

    marker = ("Consultation: " + appt) if appt else ""
    if marker:
        try:
            for r in frappe.get_all("Sales Invoice",
                    filters={"remarks": ["like", "%" + marker + "%"], "docstatus": ["<", 2]},
                    fields=["name", "remarks"], limit=20):
                rem = r.get("remarks") or ""
                idx = rem.find(marker)
                if idx < 0:
                    continue
                after = rem[idx + len(marker):idx + len(marker) + 1]
                if after and after not in " \t\r\n|,;":
                    continue
                if r.name:
                    direct_appt_names.add(r.name)
                    if r.name not in seen_candidates:
                        seen_candidates.add(r.name)
                        candidate_names.append(r.name)
        except Exception:
            pass

    enc_marker = ("Encounter: " + encounter_id) if encounter_id else ""
    if enc_marker:
        try:
            for r in frappe.get_all("Sales Invoice",
                    filters={"remarks": ["like", "%" + enc_marker + "%"], "docstatus": ["<", 2]},
                    fields=["name", "remarks"], limit=20):
                rem = r.get("remarks") or ""
                idx = rem.find(enc_marker)
                if idx < 0:
                    continue
                after = rem[idx + len(enc_marker):idx + len(enc_marker) + 1]
                if after and after not in " \t\r\n|,;":
                    continue
                if r.name:
                    direct_enc_names.add(r.name)
                    if r.name not in seen_candidates:
                        seen_candidates.add(r.name)
                        candidate_names.append(r.name)
        except Exception:
            pass

    if patient_id and appt_date and si_meta and si_meta.has_field("patient"):
        try:
            for r in frappe.get_all("Sales Invoice",
                    filters={"patient": patient_id, "posting_date": str(appt_date), "docstatus": ["<", 2]},
                    fields=["name"], order_by="docstatus desc, modified desc", limit=25):
                if r.name:
                    pat_date_names.add(r.name)
                    if r.name not in seen_candidates:
                        seen_candidates.add(r.name)
                        candidate_names.append(r.name)
        except Exception:
            pass

    if not candidate_names:
        return None

    si_fields = ["name", "docstatus", "grand_total", "is_return", "modified", "update_stock", "set_warehouse", "remarks"]
    for opt_f in ("patient", "appointment", "encounter", "patient_encounter", "ref_practitioner", "practitioner"):
        if si_meta and si_meta.has_field(opt_f):
            si_fields.append(opt_f)

    sii_meta = None
    sii_fields = ["item_code", "item_name", "description"]
    try:
        sii_meta = frappe.get_meta("Sales Invoice Item")
        for opt_f in ("batch_no", "warehouse", "item_group", "is_stock_item", "reference_dt", "reference_dn"):
            if sii_meta.has_field(opt_f):
                sii_fields.append(opt_f)
    except Exception:
        pass

    item_meta = None
    item_fields = ["name", "item_name"]
    try:
        item_meta = frappe.get_meta("Item")
        for opt_f in ("item_group", "is_stock_item"):
            if item_meta.has_field(opt_f):
                item_fields.append(opt_f)
    except Exception:
        pass

    best_vals = None
    best_rank = None
    for inv_name in candidate_names:
        try:
            vals = frappe.db.get_value("Sales Invoice", inv_name, si_fields, as_dict=True)
            if not vals or int(vals.get("docstatus") or 0) >= 2 or int(vals.get("is_return") or 0):
                continue
            if int(vals.get("docstatus") or 0) == 1:
                has_ret = False
                try:
                    has_ret = bool(frappe.db.exists("Sales Invoice", {"return_against": vals.name, "docstatus": 1}))
                except Exception:
                    has_ret = False
                if has_ret:
                    continue

            inv_pat = vals.get("patient") or ""
            if patient_id and inv_pat and inv_pat != patient_id:
                continue

            inv_appt = str(vals.get("appointment") or "").strip()
            if appt and inv_appt and inv_appt != appt:
                continue

            inv_enc = str(vals.get("encounter") or vals.get("patient_encounter") or "").strip()
            if encounter_id and inv_enc and inv_enc != encounter_id:
                continue

            is_direct_appt = inv_name in direct_appt_names
            is_direct_enc = inv_name in direct_enc_names
            is_direct = is_direct_appt or is_direct_enc

            if not is_direct and prac_id:
                inv_prac = str(vals.get("ref_practitioner") or vals.get("practitioner") or "").strip()
                if inv_prac and inv_prac != prac_id:
                    continue

            # Drug/pharmacy invoices deduct stock (update_stock = 1) whereas consultation invoices do not
            if int(vals.get("update_stock") or 0) == 1:
                continue

            inv_items = frappe.get_all("Sales Invoice Item", filters={"parent": inv_name}, fields=sii_fields, limit=100)

            # Skip invoices explicitly tied via line reference to another appointment/encounter
            other_ref = False
            matched_ref_here = False
            missing_codes = []
            for it in inv_items:
                rdt = str(it.get("reference_dt") or "").strip()
                rdn = str(it.get("reference_dn") or "").strip()
                if rdt == "Patient Appointment" and rdn:
                    if appt and rdn == appt:
                        matched_ref_here = True
                    elif appt and rdn != appt:
                        other_ref = True
                if rdt == "Patient Encounter" and rdn:
                    if encounter_id and rdn == encounter_id:
                        matched_ref_here = True
                    elif encounter_id and rdn != encounter_id:
                        other_ref = True
                ic = str(it.get("item_code") or "").strip()
                if ic and ic not in item_cache and ic not in missing_codes:
                    missing_codes.append(ic)
            if other_ref and not matched_ref_here and not is_direct:
                continue
            if inv_enc and not encounter_id and not is_direct:
                continue

            if missing_codes:
                try:
                    for itm in frappe.get_all("Item", filters={"name": ["in", missing_codes]}, fields=item_fields):
                        item_cache[itm.name] = itm
                except Exception:
                    pass
                for mc in missing_codes:
                    item_cache.setdefault(mc, {})

            has_drug = False
            all_drug = bool(inv_items)
            all_lab = bool(inv_items)
            has_consult = False
            has_fee_service = False
            for it in inv_items:
                ic = str(it.get("item_code") or "").strip()
                im = item_cache.get(ic) or {}
                ig = str(it.get("item_group") or im.get("item_group") or "").strip().lower()
                is_stock = int(im.get("is_stock_item") or it.get("is_stock_item") or 0)
                has_batch = bool(str(it.get("batch_no") or "").strip())
                rdt = str(it.get("reference_dt") or "").strip()
                row_txt = (" ".join([
                    ic,
                    str(it.get("item_name") or ""),
                    str(im.get("item_name") or ""),
                    str(it.get("description") or ""),
                    ig,
                ])).lower()

                is_drug_row = (
                    rdt == "Drug Prescription"
                    or has_batch
                    or is_stock == 1
                    or (bool(ic) and ic in drug_codes)
                    or ("drug" in ig)
                    or ("medic" in ig)
                    or ("pharm" in ig)
                    or ("consult" not in row_txt and ("drug" in row_txt or "medic" in row_txt or "pharm" in row_txt or "tablet" in row_txt or "capsule" in row_txt or "syrup" in row_txt))
                )
                is_lab_row = (
                    rdt in ("Lab Test", "Sample Collection", "Radiology", "Clinical Procedure")
                    or ("lab" in ig and "consult" not in row_txt)
                    or ("diagnostic" in ig and "consult" not in row_txt)
                )
                is_consult_row = (not is_drug_row) and (
                    (bool(ic) and ic in consult_codes)
                    or ("consult" in row_txt)
                    or ("opd" in row_txt)
                    or ("doctor visit" in row_txt)
                    or ("doctor fee" in row_txt)
                    or ("checkup" in row_txt)
                )

                if is_drug_row:
                    has_drug = True
                else:
                    all_drug = False
                    if not is_lab_row:
                        has_fee_service = True
                if not is_lab_row:
                    all_lab = False
                if is_consult_row:
                    has_consult = True

            rem_str = str(vals.get("remarks") or "")
            rem_consult = False
            if appt:
                mk = "Consultation: " + appt
                mk_idx = rem_str.find(mk)
                if mk_idx >= 0:
                    mk_after = rem_str[mk_idx + len(mk):mk_idx + len(mk) + 1]
                    if not mk_after or mk_after in " \t\r\n|,;":
                        rem_consult = True
            has_wh = bool(str(vals.get("set_warehouse") or "").strip())

            # Differentiate from drug / pharmacy / lab-only invoices
            if all_drug:
                continue
            if (has_drug or has_wh) and not has_consult:
                continue
            if all_lab and not has_consult:
                continue
            if not (has_fee_service or has_consult or rem_consult) and not is_direct_appt:
                continue

            is_sub = 1 if int(vals.get("docstatus") or 0) == 1 else 0
            consult_flag = 1 if (has_consult or rem_consult) else 0
            direct_rank = 2 if is_direct_appt else (1 if is_direct_enc else 0)
            cand_rank = (is_sub, consult_flag, direct_rank, str(vals.get("modified") or ""))
            if best_rank is None or cand_rank > best_rank:
                best_rank = cand_rank
                best_vals = vals
        except Exception:
            continue

    return best_vals

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
    enc_found = frappe.get_all("Patient Encounter",
        filters={"appointment": r.name, "docstatus": ["!=", 2]}, fields=["name"],
        order_by="docstatus desc, modified desc", limit=1)
    enc_id = enc_found[0].name if enc_found else ""
    inv_info = find_invoice_info(
        r.name,
        r.patient,
        enc_id,
        str(r.get("appointment_date") or date),
        r.practitioner,
        inv_cache,
    )
    inv = inv_info.name if inv_info else ""
    inv_docstatus = inv_info.docstatus if inv_info else None
    inv_total = float(inv_info.grand_total or 0) if inv_info else 0.0
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
        "encounter": enc_id,
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
