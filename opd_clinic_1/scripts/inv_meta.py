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

    prac_id = doc.get("practitioner") or ""
    clean_remarks = (doc.remarks or "").strip()
    if clean_remarks.startswith("Doctor: "):
        parts = clean_remarks.split(" | ", 1)
        clean_remarks = parts[1].strip() if len(parts) > 1 else ""

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
    if not appt_id:
        for it in (doc.items or []):
            if it.get("reference_dt") == "Patient Appointment" and it.get("reference_dn"):
                appt_id = it.get("reference_dn")
                break

    frappe.response["message"] = {
        "invoice": {
            "name": doc.name,
            "docstatus": doc.docstatus,
            "customer": doc.customer or "",
            "patient": pat_obj,
            "appointment": appt_id,
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
    if patient_id and frappe.db.exists("Patient", patient_id):
        pv = frappe.db.get_value("Patient", patient_id, ["name", "patient_name", "mobile", "dob", "uid", "customer"], as_dict=True)
        pat_obj = build_patient_obj(pv, frappe.utils.getdate(frappe.utils.today()))

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
        "is_admin": is_admin,
        "today": str(frappe.utils.today()),
        "csrf": token
    }
