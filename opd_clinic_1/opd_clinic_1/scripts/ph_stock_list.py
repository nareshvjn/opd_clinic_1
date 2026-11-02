# Server Script: ph_stock_list
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_stock_list
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the pharmacy.")

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
q = (f.get("q") or "").strip()
wh = f.get("warehouse")
show_zero = f.get("zero") in ("1", "true")

filters = {"disabled": 0}
if not show_zero:
    filters["batch_qty"] = [">", 0]
or_filters = []
if q:
    or_filters = [["Batch", "item", "like", "%" + q + "%"],
                  ["Batch", "item_name", "like", "%" + q + "%"],
                  ["Batch", "name", "like", "%" + q + "%"]]

rows = frappe.get_all("Batch", filters=filters, or_filters=or_filters,
    fields=["name", "item", "item_name", "expiry_date", "batch_qty", "mrp", "purchase_rate",
            "net_rate", "gst_rate", "hsn_code", "units_per_pack"],
    order_by="item_name asc, expiry_date asc", limit=300)

out = []
for b in rows:
    qty = b.batch_qty or 0
    if wh and qty > 0:
        w = wh_qty(b.name, wh)
        if w is not None:
            qty = w
    if qty <= 0 and not show_zero:
        continue
    out.append({"batch": b.name, "item": b.item, "name": b.item_name or b.item,
        "expiry": str(b.expiry_date or ""), "qty": qty if qty > 0 else 0,
        "mrp": b.mrp or 0, "purchase_rate": b.purchase_rate or 0,
        "net_rate": b.net_rate or b.purchase_rate or 0, "gst": b.gst_rate or 0,
        "hsn": b.hsn_code or "", "upp": b.units_per_pack or 1})
if show_zero:
    # products that have no batch at all yet (for example a new medicine added from the consultation page)
    iq = []
    if q:
        iq = [["Item", "item_name", "like", "%" + q + "%"], ["Item", "item_code", "like", "%" + q + "%"]]
    for it in frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1}, or_filters=iq,
            fields=["name", "item_name", "item_group", "has_batch_no"], order_by="item_name asc", limit=300):
        if it.item_group != "Drug" and not it.has_batch_no:
            continue
        if frappe.db.exists("Batch", {"item": it.name, "disabled": 0}):
            continue
        out.append({"batch": "", "item": it.name, "name": it.item_name or it.name, "expiry": "", "qty": 0,
            "mrp": 0, "purchase_rate": 0, "net_rate": 0, "gst": 0, "hsn": "", "upp": 1})
frappe.response["message"] = {"batches": out}
