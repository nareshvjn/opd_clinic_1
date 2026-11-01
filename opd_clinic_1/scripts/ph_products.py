# Server Script: ph_products
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_products
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the pharmacy.")

q = (frappe.form_dict.get("q") or "").strip()
or_filters = []
if q:
    or_filters = [["Item", "item_name", "like", "%" + q + "%"], ["Item", "item_code", "like", "%" + q + "%"]]
items = frappe.get_all("Item", filters={"has_batch_no": 1, "disabled": 0}, or_filters=or_filters,
    fields=["name", "item_name"], order_by="item_name", limit=20)
if len(items) < 20 and frappe.db.exists("Item Group", "Drug"):
    seen = []
    for x in items:
        seen.append(x.name)
    more = frappe.get_all("Item", filters={"item_group": "Drug", "has_batch_no": 0, "disabled": 0}, or_filters=or_filters,
        fields=["name", "item_name"], order_by="item_name", limit=20)
    for x in more:
        if x.name not in seen and len(items) < 20:
            items.append(x)
out = []
for it in items:
    units = 0
    expiry = None
    for b in frappe.get_all("Batch", filters={"item": it.name, "disabled": 0, "batch_qty": [">", 0]},
            fields=["batch_qty", "expiry_date"], order_by="expiry_date asc"):
        units += b.batch_qty or 0
        if not expiry and b.expiry_date:
            expiry = str(b.expiry_date)
    out.append({"code": it.name, "name": it.item_name, "units": units, "expiry": expiry})
frappe.response["message"] = {"products": out}
