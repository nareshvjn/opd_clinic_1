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

b = frappe.get_doc("Batch", bname)
item = b.item
old_rate = b.purchase_rate or 0
meta = frappe.get_meta("Batch")
if f.get("expiry"):
    b.expiry_date = f.get("expiry")
hsn = f.get("hsn") or ""
mrp = num(f.get("mrp"))
net = rate if ((not b.net_rate) or abs(rate - old_rate) > 0.0001) else (b.net_rate or rate)

for fn, val in [("hsn_code", hsn), ("gst_rate", gst), ("mrp", mrp),
                ("purchase_rate", rate), ("net_rate", net), ("units_per_pack", upp)]:
    if meta.has_field(fn):
        b.set(fn, val)
    if meta.has_field("custom_" + fn):
        b.set("custom_" + fn, val)
b.save(ignore_permissions=True)

cur = wh_qty(bname, wh)
if cur is None:
    try:
        s = frappe.db.sql("""select sum(actual_qty) from `tabStock Ledger Entry`
            where batch_no = %s and warehouse = %s and is_cancelled = 0""", (bname, wh))
        if s and s[0] and s[0][0] is not None:
            cur = float(s[0][0])
    except:
        pass
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

frappe.response["message"] = {"batch": bname, "units": qty, "upp": upp, "document": doc_name}
