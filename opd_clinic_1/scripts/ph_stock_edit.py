# Server Script: ph_stock_edit
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_stock_edit
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

def wh_qty(b, w):
    try:
        r = frappe.call("erpnext.stock.doctype.batch.batch.get_batch_qty", batch_no=b, warehouse=w)
    except:
        return None
    try:
        return float(r)
    except:
        pass
    try:
        t = 0
        for x in r:
            t += x.get("qty") or 0
        return t
    except:
        return None

f = frappe.form_dict
bname = (f.get("batch") or "").strip()
wh = f.get("warehouse")
if not bname or not frappe.db.exists("Batch", bname):
    frappe.throw("That batch was not found.")
if not wh:
    frappe.throw("Choose a store.")
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
if qty < 0:
    frappe.throw("Quantity cannot be negative.")

company = frappe.db.get_single_value("Global Defaults", "default_company")
co = frappe.db.get_value("Company", company, ["stock_adjustment_account", "cost_center"], as_dict=True)

b = frappe.get_doc("Batch", bname)
item = b.item
old_rate = b.purchase_rate or 0
b.expiry_date = f.get("expiry")
b.hsn_code = f.get("hsn") or ""
b.gst_rate = gst
b.mrp = num(f.get("mrp"))
b.purchase_rate = rate
if (not b.net_rate) or abs(rate - old_rate) > 0.0001:
    b.net_rate = rate
b.units_per_pack = upp
b.save(ignore_permissions=True)

cur = wh_qty(bname, wh)
if cur is None:
    cur = frappe.db.get_value("Batch", bname, "batch_qty") or 0
val = rate / upp
doc_name = ""
if qty != cur:
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

frappe.response["message"] = {"batch": bname, "units": qty, "upp": upp, "document": doc_name}
