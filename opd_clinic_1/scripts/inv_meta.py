# Server Script: inv_meta
# type: API
# doctype: -
# event: Before Insert
# api_method: inv_meta
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
if not ok:
    for r in ["Physician", "Accounts Manager", "Accounts User", "Sales User", "Stock Manager", "Stock User"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            ok = True
            break
if not ok:
    frappe.throw("You do not have permission to create invoices.")

def default_service_rate(code, name, std_rate):
    val = float(std_rate or 0)
    if val > 0:
        return val
    nm = (name or "").strip().lower()
    cd = (code or "").strip().upper()
    if cd == "CONSULT-GEN" or "consultation" in nm:
        return 100.0
    if "iv fluid" in nm:
        return 100.0
    if "injection" in nm or "nebulis" in nm or "nebuliz" in nm:
        return 50.0
    return 0.0

def build_patient_obj(pv, today_d):
    if not pv:
        return None
    age = None
    if pv.get("dob"):
        d = frappe.utils.getdate(pv.get("dob"))
        age = today_d.year - d.year - (1 if (today_d.month, today_d.day) < (d.month, d.day) else 0)
    return {
        "id": pv.name,
        "uid": pv.get("uid") or "",
        "name": pv.get("patient_name") or pv.name,
        "age": age,
        "mobile": pv.get("mobile") or "",
        "customer": pv.get("customer") or ""
    }


def get_patient_encounters(patient_id):
    out = []
    if not patient_id or not frappe.db.exists("DocType", "Patient Encounter"):
        return out
    try:
        rows = frappe.get_all(
            "Patient Encounter",
            filters={"patient": patient_id, "docstatus": ["<", 2]},
            fields=["name", "encounter_date", "practitioner", "practitioner_name", "appointment", "docstatus"],
            order_by="encounter_date desc, modified desc",
            limit=20,
        )
        for r in rows:
            status_lbl = "Draft" if int(r.docstatus or 0) == 0 else "Completed"
            doc_lbl = r.get("practitioner_name") or r.get("practitioner") or ""
            label_parts = [r.name]
            if r.get("encounter_date"):
                label_parts.append(str(r.get("encounter_date")))
            if doc_lbl:
                label_parts.append(doc_lbl)
            label_parts.append(status_lbl)
            out.append({
                "id": r.name,
                "date": str(r.get("encounter_date") or ""),
                "practitioner": r.get("practitioner") or "",
                "appointment": r.get("appointment") or "",
                "docstatus": int(r.docstatus or 0),
                "label": " | ".join(label_parts),
            })
    except Exception:
        pass
    return out


f = frappe.form_dict
action = (f.get("action") or "").strip()
q = (f.get("q") or "").strip()

if action == "search_patients":
    if len(q) < 2:
        frappe.response["message"] = {"patients": []}
    else:
        rows = frappe.get_all("Patient",
            filters=[["Patient", "status", "=", "Active"]],
            or_filters=[["Patient", "patient_name", "like", "%" + q + "%"],
                        ["Patient", "mobile", "like", "%" + q + "%"],
                        ["Patient", "uid", "like", "%" + q + "%"],
                        ["Patient", "name", "like", "%" + q + "%"]],
            fields=["name", "patient_name", "mobile", "dob", "uid", "customer"],
            order_by="patient_name asc",
            limit=12)
        today_d = frappe.utils.getdate(frappe.utils.today())
        frappe.response["message"] = {"patients": [build_patient_obj(r, today_d) for r in rows]}

elif action == "search_items":
    filters = {"disabled": 0, "is_sales_item": 1}
    or_filters = []
    if q:
        or_filters = [
            ["Item", "item_name", "like", "%" + q + "%"],
            ["Item", "item_code", "like", "%" + q + "%"],
            ["Item", "item_group", "like", "%" + q + "%"]
        ]
    rows = frappe.get_all("Item",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "item_name", "item_group", "stock_uom", "standard_rate", "is_stock_item", "has_batch_no", "description"],
        order_by="is_stock_item asc, item_name asc",
        limit=25)
    out = []
    for it in rows:
        out.append({
            "code": it.name,
            "name": it.item_name or it.name,
            "group": it.item_group or "",
            "uom": it.stock_uom or "Nos",
            "rate": default_service_rate(it.name, it.item_name, it.standard_rate),
            "is_stock": int(it.is_stock_item or 0),
            "has_batch": int(it.has_batch_no or 0),
            "description": it.description or ""
        })
    frappe.response["message"] = {"items": out}

elif action == "search_customers":
    or_filters = []
    if q:
        or_filters = [
            ["Customer", "customer_name", "like", "%" + q + "%"],
            ["Customer", "name", "like", "%" + q + "%"],
            ["Customer", "mobile_no", "like", "%" + q + "%"]
        ]
    rows = frappe.get_all("Customer",
        filters={"disabled": 0},
        or_filters=or_filters,
        fields=["name", "customer_name", "mobile_no"],
        order_by="customer_name asc",
        limit=15)
    out = []
    for c in rows:
        out.append({
            "name": c.name,
            "customer_name": c.customer_name or c.name,
            "mobile": c.mobile_no or ""
        })
    frappe.response["message"] = {"customers": out}

elif action == "patient_encounters":
    patient_id = (f.get("patient") or "").strip()
    frappe.response["message"] = {"encounters": get_patient_encounters(patient_id)}

elif action == "load_invoice":
    inv_name = (f.get("name") or "").strip()
    if not inv_name or not frappe.db.exists("Sales Invoice", inv_name):
        frappe.throw("Invoice not found.")
    doc = frappe.get_doc("Sales Invoice", inv_name)
    if doc.docstatus == 2:
        frappe.throw("Cancelled invoices cannot be edited.")

    today_d = frappe.utils.getdate(frappe.utils.today())
    doc_d = frappe.utils.getdate(doc.posting_date) if doc.posting_date else today_d
    if doc_d < today_d and not is_admin:
        frappe.throw("Only admin accounts can edit past-dated invoices.")

    mode = ""
    if doc.payments:
        mode = doc.payments[0].mode_of_payment or ""
    if not mode and doc.docstatus == 1:
        pe_rows = frappe.db.sql("""
            select pe.mode_of_payment
            from `tabPayment Entry` pe
            join `tabPayment Entry Reference` per on per.parent = pe.name
            where per.reference_doctype = 'Sales Invoice' and per.reference_name = %s and pe.docstatus = 1
            limit 1
        """, inv_name, as_dict=True)
        if pe_rows and pe_rows[0].get("mode_of_payment"):
            mode = pe_rows[0].get("mode_of_payment")
    if not mode:
        mode = "Credit" if float(doc.outstanding_amount or 0) > 0 and doc.docstatus == 1 else "Cash"

    pat_obj = None
    if doc.get("patient") and frappe.db.exists("Patient", doc.patient):
        pv = frappe.db.get_value("Patient", doc.patient, ["name", "patient_name", "mobile", "uid", "customer"], as_dict=True)
        if pv:
            pat_obj = {
                "id": pv.name,
                "name": pv.patient_name or pv.name,
                "mobile": pv.mobile or "",
                "uid": pv.get("uid") or "",
                "customer": pv.get("customer") or ""
            }

    prac_id = doc.get("ref_practitioner") or doc.get("practitioner") or ""
    rem_appt = ""
    rem_enc = ""
    kept_rem = []
    for rpart in (doc.remarks or "").strip().split(" | "):
        rs = rpart.strip()
        if not rs:
            continue
        if rs.startswith("Doctor: "):
            continue
        if rs.startswith("Consultation: "):
            tok = rs[len("Consultation: "):].strip().split()[0] if rs[len("Consultation: "):].strip() else ""
            if tok and frappe.db.exists("Patient Appointment", tok):
                if not rem_appt:
                    rem_appt = tok
                continue
        if rs.startswith("Encounter: "):
            tok = rs[len("Encounter: "):].strip().split()[0] if rs[len("Encounter: "):].strip() else ""
            if tok and frappe.db.exists("Patient Encounter", tok):
                if not rem_enc:
                    rem_enc = tok
                continue
        kept_rem.append(rs)
    clean_remarks = " | ".join(kept_rem)

    charge_amt = 0.0
    charge_name = ""
    for tx in (doc.taxes or []):
        if tx.charge_type == "Actual" or (tx.tax_amount and not tx.rate):
            charge_amt = float(tx.tax_amount or 0)
            charge_name = tx.description or ""
            break

    inv_lines = []
    for it in (doc.items or []):
        qty = float(it.qty or 1)
        disc = float(it.discount_percentage or 0)
        pl_rate = float(it.price_list_rate or 0)
        net_rate = float(it.rate or 0)
        if pl_rate > 0:
            base_rate = pl_rate
        elif 0 < disc < 100 and net_rate > 0:
            base_rate = round(net_rate / (1.0 - disc / 100.0), 2)
        else:
            base_rate = net_rate
        if disc <= 0 and base_rate > 0 and net_rate < base_rate - 0.01:
            disc = round((1.0 - net_rate / base_rate) * 100.0, 4)

        ic = "" if it.item_code in ["MISC-SERVICE", "CLINIC-SERVICE"] else (it.item_code or "")
        iname = it.item_name or it.item_code or ""
        desc = it.description or ""
        if desc == iname:
            desc = ""
        inv_lines.append({
            "item_code": ic,
            "item_name": iname,
            "description": desc,
            "qty": qty,
            "rate": base_rate,
            "disc": disc
        })

    appt_id = (doc.get("appointment") or "").strip() if hasattr(doc, "appointment") else ""
    enc_id = ""
    for enc_fld in ("encounter", "patient_encounter"):
        if hasattr(doc, enc_fld) and doc.get(enc_fld):
            enc_id = (doc.get(enc_fld) or "").strip()
            break
    for it in (doc.items or []):
        if not appt_id and it.get("reference_dt") == "Patient Appointment" and it.get("reference_dn"):
            appt_id = it.get("reference_dn")
        if not enc_id and it.get("reference_dt") == "Patient Encounter" and it.get("reference_dn"):
            enc_id = it.get("reference_dn")
    if not appt_id and rem_appt:
        appt_id = rem_appt
    if not enc_id and rem_enc:
        enc_id = rem_enc

    encounters_list = get_patient_encounters(doc.get("patient") or "")

    frappe.response["message"] = {
        "invoice": {
            "name": doc.name,
            "docstatus": doc.docstatus,
            "customer": doc.customer or "",
            "patient": pat_obj,
            "appointment": appt_id,
            "encounter": enc_id,
            "encounters": encounters_list,
            "practitioner": prac_id,
            "posting_date": str(doc.posting_date or today_d),
            "mode": mode,
            "remarks": clean_remarks,
            "charge": charge_amt,
            "charge_name": charge_name,
            "lines": inv_lines
        }
    }

else:
    company = frappe.db.get_single_value("Global Defaults", "default_company") or ""
    currency = "INR"
    if company:
        currency = frappe.db.get_value("Company", company, "default_currency") or "INR"

    modes = []
    for m in frappe.get_all("Mode of Payment", filters={"enabled": 1}, fields=["name"], order_by="name asc"):
        modes.append(m.name)
    if not modes:
        modes = ["Cash"]
    cash_modes = [m for m in modes if m.strip().lower() == "cash"]
    other_modes = [m for m in modes if m.strip().lower() != "cash"]
    modes = cash_modes + other_modes

    # Preload non-stock service / procedure / lab items first for quick picking
    service_items = []
    for it in frappe.get_all("Item",
            filters={"disabled": 0, "is_sales_item": 1, "is_stock_item": 0},
            fields=["name", "item_name", "item_group", "stock_uom", "standard_rate", "description"],
            order_by="item_name asc",
            limit=100):
        service_items.append({
            "code": it.name,
            "name": it.item_name or it.name,
            "group": it.item_group or "",
            "uom": it.stock_uom or "Nos",
            "rate": default_service_rate(it.name, it.item_name, it.standard_rate),
            "description": it.description or ""
        })

    practitioners = []
    if frappe.db.exists("DocType", "Healthcare Practitioner"):
        for pr in frappe.get_all("Healthcare Practitioner",
                filters={"status": "Active"},
                fields=["name", "practitioner_name"],
                order_by="practitioner_name asc",
                limit=50):
            practitioners.append({
                "id": pr.name,
                "name": pr.practitioner_name or pr.name
            })

    customers = []
    for c in frappe.get_all("Customer",
            filters={"disabled": 0},
            fields=["name", "customer_name"],
            order_by="customer_name asc",
            limit=200):
        customers.append({
            "name": c.name,
            "customer_name": c.customer_name or c.name
        })

    pat_obj = None
    patient_id = (f.get("patient") or "").strip()
    enc_id = (f.get("encounter") or "").strip()
    appt_id = (f.get("appointment") or "").strip()
    if enc_id and frappe.db.exists("Patient Encounter", enc_id):
        ev = frappe.db.get_value("Patient Encounter", enc_id, ["patient", "appointment"], as_dict=True) or {}
        if not patient_id and ev.get("patient"):
            patient_id = ev.get("patient")
        if not appt_id and ev.get("appointment"):
            appt_id = ev.get("appointment")
    if appt_id and not patient_id and frappe.db.exists("Patient Appointment", appt_id):
        patient_id = frappe.db.get_value("Patient Appointment", appt_id, "patient") or ""

    if patient_id and frappe.db.exists("Patient", patient_id):
        pv = frappe.db.get_value("Patient", patient_id, ["name", "patient_name", "mobile", "dob", "uid", "customer"], as_dict=True)
        pat_obj = build_patient_obj(pv, frappe.utils.getdate(frappe.utils.today()))

    encounters_list = get_patient_encounters(patient_id)
    if not enc_id and appt_id:
        for eo in encounters_list:
            if eo.get("appointment") == appt_id:
                enc_id = eo.get("id") or ""
                break

    token = ""
    try:
        token = frappe.session.get("csrf_token") or ""
    except Exception:
        token = ""

    frappe.response["message"] = {
        "company": company,
        "currency": currency,
        "modes": modes,
        "items": service_items,
        "practitioners": practitioners,
        "customers": customers,
        "patient": pat_obj,
        "appointment": appt_id,
        "encounter": enc_id,
        "encounters": encounters_list,
        "is_admin": is_admin,
        "today": str(frappe.utils.today()),
        "csrf": token
    }
