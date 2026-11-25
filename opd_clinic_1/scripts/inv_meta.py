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
        out = []
        for r in rows:
            age = None
            if r.dob:
                d = frappe.utils.getdate(r.dob)
                age = today_d.year - d.year - (1 if (today_d.month, today_d.day) < (d.month, d.day) else 0)
            out.append({
                "id": r.name,
                "uid": r.uid or "",
                "name": r.patient_name or r.name,
                "age": age,
                "mobile": r.mobile or "",
                "customer": r.get("customer") or ""
            })
        frappe.response["message"] = {"patients": out}

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
            "rate": float(it.standard_rate or 0),
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
            "rate": float(it.standard_rate or 0),
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
        "is_admin": is_admin,
        "today": str(frappe.utils.today()),
        "csrf": token
    }
