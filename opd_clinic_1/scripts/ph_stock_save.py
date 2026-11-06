# Server Script: ph_stock_save
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_stock_save
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the pharmacy.")

def num(v):
    try:
        return float(v or 0)
    except:
        return 0.0

def batchify(code):
    # items made from a Medication may not be batch items yet; switch them on (only possible before any stock movement)
    if not frappe.db.get_value("Item", code, "has_batch_no"):
        it = frappe.get_doc("Item", code)
        it.has_batch_no = 1
        it.has_expiry_date = 1
        it.create_new_batch = 0
        it.save(ignore_permissions=True)
    return code

def ensure_dosage_form(form_name):
    if not form_name or not frappe.db.exists("DocType", "Dosage Form"):
        return form_name or "Tablet"
    fn = form_name.strip()
    if not fn:
        return "Tablet"
    if not frappe.db.exists("Dosage Form", fn):
        try:
            df = frappe.new_doc("Dosage Form")
            df.name = fn
            df.flags.name_set = True
            df.dosage_form = fn
            df.insert(ignore_permissions=True, ignore_mandatory=True)
        except:
            pass
    return fn

def ensure_medication_class(cls_name):
    if not cls_name or not frappe.db.exists("DocType", "Medication Class"):
        return cls_name or "Drug"
    cn = cls_name.strip()
    if not cn:
        return "Drug"
    if not frappe.db.exists("Medication Class", cn):
        try:
            mc = frappe.new_doc("Medication Class")
            mc.name = cn
            mc.flags.name_set = True
            mc.medication_class = cn
            mc.insert(ignore_permissions=True, ignore_mandatory=True)
        except:
            pass
    return cn

def ensure_medication(item_code, item_name, form=None, generic=None, mclass=None, strength=None, unit=None):
    if not frappe.db.exists("DocType", "Medication"):
        return None

    nm = (item_name or item_code or "").strip()
    existing = None
    if frappe.db.exists("Medication", nm):
        existing = nm
    elif frappe.db.exists("Medication", {"item": item_code}):
        existing = frappe.db.get_value("Medication", {"item": item_code}, "name")
    elif frappe.db.exists("Medication", {"item_code": item_code}):
        existing = frappe.db.get_value("Medication", {"item_code": item_code}, "name")

    meta_med = frappe.get_meta("Medication")

    # Resolve dosage form
    df_name = ""
    if form:
        df_name = ensure_dosage_form(form)
    elif existing and meta_med.has_field("dosage_form"):
        df_name = frappe.db.get_value("Medication", existing, "dosage_form") or ""
    if not df_name:
        first_form = frappe.get_all("Dosage Form", fields=["name"], limit=1)
        df_name = first_form[0].name if first_form else "Tablet"
        ensure_dosage_form(df_name)

    # Resolve medication class
    cls_name = ""
    if mclass:
        cls_name = ensure_medication_class(mclass)
    elif existing and meta_med.has_field("medication_class"):
        cls_name = frappe.db.get_value("Medication", existing, "medication_class") or ""
    if not cls_name:
        if frappe.db.exists("Medication Class", "Drug"):
            cls_name = "Drug"
        else:
            first_cls = frappe.get_all("Medication Class", fields=["name"], limit=1)
            cls_name = first_cls[0].name if first_cls else "Drug"
            ensure_medication_class(cls_name)

    st_val = num(strength) if strength else 1.0
    uom_val = (unit or "").strip() or "Nos"
    if not frappe.db.exists("UOM", uom_val):
        try:
            frappe.get_doc({"doctype": "UOM", "uom_name": uom_val}).insert(ignore_permissions=True)
        except:
            pass

    gen_val = (generic or "").strip() or nm

    if existing:
        try:
            med = frappe.get_doc("Medication", existing)
            changed = False
            if df_name and meta_med.has_field("dosage_form") and (not med.dosage_form or form):
                med.dosage_form = df_name
                changed = True
            if cls_name and meta_med.has_field("medication_class") and (not med.medication_class or mclass):
                med.medication_class = cls_name
                changed = True
            if generic and meta_med.has_field("generic_name") and (not med.generic_name or med.generic_name == nm):
                med.generic_name = gen_val
                changed = True
            if strength and meta_med.has_field("strength"):
                med.strength = st_val
                changed = True
            if unit and meta_med.has_field("strength_uom"):
                med.strength_uom = uom_val
                changed = True
            if changed:
                med.save(ignore_permissions=True)
            return med.name
        except:
            return existing
    else:
        try:
            med = frappe.new_doc("Medication")
            med.name = nm
            med.flags.name_set = True
            if meta_med.has_field("medication_name"):
                med.medication_name = nm
            if meta_med.has_field("generic_name"):
                med.generic_name = gen_val
            if meta_med.has_field("item"):
                med.item = item_code
            if meta_med.has_field("item_code"):
                med.item_code = item_code
            if df_name and meta_med.has_field("dosage_form"):
                med.dosage_form = df_name
            if cls_name and meta_med.has_field("medication_class"):
                med.medication_class = cls_name
            if meta_med.has_field("strength"):
                med.strength = st_val
            if meta_med.has_field("strength_uom"):
                med.strength_uom = uom_val
            med.flags.ignore_mandatory = True
            med.insert(ignore_permissions=True, ignore_mandatory=True)
            return med.name
        except:
            pass
    return nm

def ensure_item(name, item_group=None, stock_uom=None, form=None, generic=None, mclass=None, strength=None, unit=None):
    grp = item_group or "Drug"
    if not frappe.db.exists("Item Group", grp):
        if frappe.db.exists("Item Group", "Drug"):
            grp = "Drug"
        else:
            grp = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"

    uom = stock_uom or "Nos"
    if not frappe.db.exists("UOM", uom):
        try:
            frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
        except:
            pass

    code = None
    if frappe.db.exists("Item", name):
        code = batchify(name)
    else:
        found = frappe.db.get_value("Item", {"item_name": name}, "name")
        if found:
            code = batchify(found)
        else:
            it = frappe.new_doc("Item")
            it.item_code = name
            it.item_name = name
            it.item_group = grp
            it.stock_uom = uom
            it.is_stock_item = 1
            it.has_batch_no = 1
            it.has_expiry_date = 1
            it.create_new_batch = 0
            it.insert(ignore_permissions=True)
            code = it.name

    ensure_medication(code, name, form=form, generic=generic, mclass=mclass, strength=strength, unit=unit)
    return code

def ensure_batch(item, batch_in, expiry, hsn, gst, mrp, rate, net, upp):
    bname = (batch_in or "").strip()
    existing = frappe.db.get_value("Batch", {"batch_id": bname, "item": item}, "name")
    if not existing and frappe.db.exists("Batch", bname):
        if frappe.db.get_value("Batch", bname, "item") == item:
            existing = bname

    meta = frappe.get_meta("Batch")
    def set_batch_fields(doc):
        if expiry:
            doc.expiry_date = expiry
        for fn, val in [("hsn_code", hsn), ("gst_rate", gst), ("mrp", mrp),
                        ("purchase_rate", rate), ("net_rate", net), ("units_per_pack", upp)]:
            if meta.has_field(fn):
                doc.set(fn, val)
            if meta.has_field("custom_" + fn):
                doc.set("custom_" + fn, val)

    if existing:
        b = frappe.get_doc("Batch", existing)
        set_batch_fields(b)
        b.save(ignore_permissions=True)
        return b.name
    else:
        target_name = bname
        if frappe.db.exists("Batch", target_name):
            target_name = bname + "-" + item
            n = 1
            while frappe.db.exists("Batch", target_name):
                target_name = bname + "-" + str(n)
                n += 1

        b = frappe.new_doc("Batch")
        b.name = target_name
        b.flags.name_set = True
        b.batch_id = bname
        b.item = item
        set_batch_fields(b)
        b.insert(ignore_permissions=True, ignore_mandatory=True)
        return b.name

def wh_qty(b, w):
    try:
        r = frappe.call("erpnext.stock.doctype.batch.batch.get_batch_qty", batch_no=b, warehouse=w)
        if isinstance(r, (int, float)):
            return float(r)
        if isinstance(r, list):
            return sum(float(x.get("qty") or 0) for x in r)
    except:
        pass
    try:
        s = frappe.db.sql("""select sum(actual_qty) from `tabStock Ledger Entry`
            where batch_no = %s and warehouse = %s and is_cancelled = 0""", (b, w))
        if s and s[0] and s[0][0] is not None:
            return float(s[0][0])
    except:
        pass
    return None

f = frappe.form_dict
product = (f.get("product") or "").strip()
batch_in = (f.get("batch") or "").strip()
wh = f.get("warehouse")
if not product or not batch_in or not wh:
    frappe.throw("Enter the product, batch number and store.")
if not f.get("expiry"):
    frappe.throw("Enter the batch expiry.")

form = (f.get("form") or f.get("dosage_form") or "").strip()
generic = (f.get("generic") or f.get("generic_name") or "").strip()
mclass = (f.get("mclass") or f.get("medication_class") or "").strip()
strength = f.get("strength")
unit = (f.get("unit") or f.get("strength_uom") or "").strip()
item_group = (f.get("item_group") or "").strip()

upp = int(num(f.get("upp")))
if upp < 1:
    upp = 1
gst = num(f.get("gst"))
rate = num(f.get("rate"))
if f.get("basis") == "incl":
    rate = rate / (1 + gst / 100)
qty = num(f.get("packs")) * upp + num(f.get("units"))

company = frappe.db.get_single_value("Global Defaults", "default_company")
co = frappe.db.get_value("Company", company, ["stock_adjustment_account", "cost_center"], as_dict=True) or {}
adj_acc = co.get("stock_adjustment_account")
if not adj_acc:
    adj_acc = frappe.db.get_value("Account", {"account_type": "Stock Adjustment", "company": company, "is_group": 0}, "name")
if not adj_acc:
    adj_acc = frappe.db.get_value("Account", {"account_name": ["like", "%Stock Adjustment%"], "company": company, "is_group": 0}, "name")
if not adj_acc:
    adj_acc = frappe.db.get_value("Company", company, "default_inventory_account")

cost_center = co.get("cost_center")
if not cost_center:
    cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")

item = ensure_item(product, item_group=item_group, form=form, generic=generic, mclass=mclass, strength=strength, unit=unit)
bname = ensure_batch(item, batch_in, f.get("expiry"), f.get("hsn") or "", gst,
    num(f.get("mrp")), rate, rate, upp)

cur = wh_qty(bname, wh)
if cur is None:
    cur = frappe.db.get_value("Batch", bname, "batch_qty") or 0
val = rate / upp
doc_name = ""
if qty > 0 and qty != cur:
    if cur <= 0:
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Receipt"
        se.purpose = "Material Receipt"
        se.company = company
        se.to_warehouse = wh
        se.append("items", {"item_code": item, "qty": qty, "t_warehouse": wh, "basic_rate": val,
            "batch_no": bname, "use_serial_batch_fields": 1,
            "expense_account": adj_acc, "cost_center": cost_center})
        se.insert(ignore_permissions=True)
        se.submit()
        doc_name = se.name
    else:
        sr = frappe.new_doc("Stock Reconciliation")
        sr.purpose = "Stock Reconciliation"
        sr.company = company
        sr.expense_account = adj_acc
        sr.cost_center = cost_center
        sr.append("items", {"item_code": item, "warehouse": wh, "qty": qty, "valuation_rate": val,
            "batch_no": bname, "use_serial_batch_fields": 1})
        sr.insert(ignore_permissions=True)
        sr.submit()
        doc_name = sr.name

frappe.response["message"] = {"item": item, "batch": bname, "units": qty, "document": doc_name}
