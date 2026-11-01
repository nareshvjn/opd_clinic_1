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

def ensure_item(name):
    if frappe.db.exists("Item", name):
        return batchify(name)
    found = frappe.db.get_value("Item", {"item_name": name}, "name")
    if found:
        return batchify(found)
    grp = "Drug"
    if not frappe.db.exists("Item Group", "Drug"):
        grp = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    it = frappe.new_doc("Item")
    it.item_code = name
    it.item_name = name
    it.item_group = grp
    it.stock_uom = "Nos"
    it.is_stock_item = 1
    it.has_batch_no = 1
    it.has_expiry_date = 1
    it.create_new_batch = 0
    it.insert(ignore_permissions=True)
    return it.name

def ensure_batch(item, batch_in, expiry, hsn, gst, mrp, rate, net, upp):
    bname = batch_in
    n = 1
    while frappe.db.exists("Batch", bname) and frappe.db.get_value("Batch", bname, "item") != item:
        n += 1
        bname = batch_in + "-" + str(n)
    if frappe.db.exists("Batch", bname):
        b = frappe.get_doc("Batch", bname)
        fresh = False
    else:
        b = frappe.new_doc("Batch")
        b.batch_id = bname
        b.item = item
        fresh = True
    b.expiry_date = expiry
    b.hsn_code = hsn
    b.gst_rate = gst
    b.mrp = mrp
    b.purchase_rate = rate
    b.net_rate = net
    b.units_per_pack = upp
    if fresh:
        b.insert(ignore_permissions=True)
    else:
        b.save(ignore_permissions=True)
    return bname

f = frappe.form_dict
product = (f.get("product") or "").strip()
batch_in = (f.get("batch") or "").strip()
wh = f.get("warehouse")
if not product or not batch_in or not wh:
    frappe.throw("Enter the product, batch number and store.")
if not f.get("expiry"):
    frappe.throw("Enter the batch expiry.")

upp = int(num(f.get("upp")))
if upp < 1:
    upp = 1
gst = num(f.get("gst"))
rate = num(f.get("rate"))
if f.get("basis") == "incl":
    rate = rate / (1 + gst / 100)
qty = num(f.get("packs")) * upp + num(f.get("units"))

company = frappe.db.get_single_value("Global Defaults", "default_company")
co = frappe.db.get_value("Company", company, ["stock_adjustment_account", "cost_center"], as_dict=True)

item = ensure_item(product)
bname = ensure_batch(item, batch_in, f.get("expiry"), f.get("hsn") or "", gst,
    num(f.get("mrp")), rate, rate, upp)

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
            "expense_account": co.stock_adjustment_account, "cost_center": co.cost_center})
        se.insert(ignore_permissions=True)
        se.submit()
        doc_name = se.name
    else:
        sr = frappe.new_doc("Stock Reconciliation")
        sr.purpose = "Stock Reconciliation"
        sr.company = company
        sr.expense_account = co.stock_adjustment_account
        sr.cost_center = co.cost_center
        sr.append("items", {"item_code": item, "warehouse": wh, "qty": qty, "valuation_rate": val,
            "batch_no": bname, "use_serial_batch_fields": 1})
        sr.insert(ignore_permissions=True)
        sr.submit()
        doc_name = sr.name

frappe.response["message"] = {"item": item, "batch": bname, "units": qty, "document": doc_name}
