# Server Script: ph_stock_delete
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_stock_delete
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock Manager", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("Only a Stock Manager can delete stock.")

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

def stock_map(b, w):
    m = {}
    try:
        r = frappe.call("erpnext.stock.doctype.batch.batch.get_batch_qty", batch_no=b)
        for x in r:
            if x.get("warehouse") and (x.get("qty") or 0) > 0:
                m[x.get("warehouse")] = x.get("qty")
    except:
        m = {}
    if not m and w:
        q = wh_qty(b, w)
        if q and q > 0:
            m[w] = q
    return m

f = frappe.form_dict
bname = (f.get("batch") or "").strip()
item = (f.get("item") or "").strip()
wh = f.get("warehouse")
if not bname and not item:
    frappe.throw("Choose a batch or a product to delete.")
rm = f.get("remove_item") == "1"
if rm:
    # remove a product that has no batches (delete it, or disable it if other records use it)
    if not item or not frappe.db.exists("Item", item):
        frappe.throw("That product was not found.")
    if frappe.db.exists("Batch", {"item": item, "disabled": 0}):
        frappe.throw("This product still has batches. Delete its stock first.")
    if frappe.db.get_value("Bin", {"item_code": item, "actual_qty": [">", 0]}, "name"):
        frappe.throw("This product still has stock in a store.")
    result = "deleted"
    try:
        frappe.delete_doc("Item", item, ignore_permissions=True)
    except:
        it = frappe.get_doc("Item", item)
        it.disabled = 1
        it.save(ignore_permissions=True)
        result = "disabled (other records use it)"
    frappe.response["message"] = {"batches": 0, "document": "", "item": result}
else:
    names = []
    if bname:
        if not frappe.db.exists("Batch", bname):
            frappe.throw("That batch was not found.")
        names = [bname]
    else:
        for x in frappe.get_all("Batch", filters={"item": item, "disabled": 0}, fields=["name"]):
            names.append(x.name)
    if not names:
        frappe.throw("No batches to delete.")

    company = frappe.db.get_single_value("Global Defaults", "default_company")
    co = frappe.db.get_value("Company", company, ["stock_adjustment_account", "cost_center"], as_dict=True)

    rows = []
    for n in names:
        b = frappe.db.get_value("Batch", n, ["item", "purchase_rate", "units_per_pack"], as_dict=True)
        val = (b.purchase_rate or 0) / (b.units_per_pack or 1)
        for w, q in stock_map(n, wh).items():
            rows.append({"item_code": b.item, "warehouse": w, "qty": 0, "valuation_rate": val,
                "batch_no": n, "use_serial_batch_fields": 1})

    doc_name = ""
    if rows:
        sr = frappe.new_doc("Stock Reconciliation")
        sr.purpose = "Stock Reconciliation"
        sr.company = company
        sr.expense_account = co.stock_adjustment_account
        sr.cost_center = co.cost_center
        for r in rows:
            sr.append("items", r)
        sr.insert(ignore_permissions=True)
        sr.submit()
        doc_name = sr.name

    for n in names:
        bd = frappe.get_doc("Batch", n)
        bd.disabled = 1
        bd.save(ignore_permissions=True)

    frappe.response["message"] = {"batches": len(names), "document": doc_name}
