# Server Script: ph_batches
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_batches
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the pharmacy.")

item = frappe.form_dict.get("item")
rows = frappe.get_all("Batch", filters={"item": item, "disabled": 0},
    fields=["name", "expiry_date", "batch_qty", "mrp", "purchase_rate", "net_rate",
            "gst_rate", "hsn_code", "units_per_pack"],
    order_by="expiry_date asc")
out = []
for b in rows:
    out.append({"batch": b.name, "expiry": str(b.expiry_date or ""), "qty": b.batch_qty or 0,
        "mrp": b.mrp or 0, "purchase_rate": b.purchase_rate or 0,
        "net_rate": b.net_rate or b.purchase_rate or 0, "gst": b.gst_rate or 0,
        "hsn": b.hsn_code or "", "upp": b.units_per_pack or 1})
frappe.response["message"] = {"batches": out}
