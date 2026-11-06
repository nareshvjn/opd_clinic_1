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

out = []
try:
    item = (frappe.form_dict.get("item") or "").strip()
    if item:
        meta = frappe.get_meta("Batch")

        def find_f(fn):
            if meta.has_field(fn):
                return fn
            if meta.has_field("custom_" + fn):
                return "custom_" + fn
            return None

        f_exp = find_f("expiry_date")
        f_qty = find_f("batch_qty")
        f_mrp = find_f("mrp")
        f_pur = find_f("purchase_rate")
        f_net = find_f("net_rate")
        f_gst = find_f("gst_rate")
        f_hsn = find_f("hsn_code")
        f_upp = find_f("units_per_pack")

        fields = ["name"]
        for f in [f_exp, f_qty, f_mrp, f_pur, f_net, f_gst, f_hsn, f_upp]:
            if f and f not in fields:
                fields.append(f)

        item_field = "item" if meta.has_field("item") else ("item_code" if meta.has_field("item_code") else None)
        filters = {}
        if item_field:
            filters[item_field] = item
        if meta.has_field("disabled"):
            filters["disabled"] = 0

        order_by = (f_exp + " asc") if f_exp else "name asc"

        rows = frappe.get_all("Batch", filters=filters, fields=fields, order_by=order_by)
        for b in rows:
            qty = (b.get(f_qty) if f_qty else 0) or 0
            if not f_qty or qty == 0:
                try:
                    s = frappe.db.sql("""select sum(actual_qty) from `tabStock Ledger Entry`
                        where batch_no = %s and is_cancelled = 0""", (b.name,))
                    if s and s[0] and s[0][0] is not None:
                        qty = float(s[0][0])
                except:
                    pass

            mrp = (b.get(f_mrp) if f_mrp else 0) or 0
            pur = (b.get(f_pur) if f_pur else 0) or 0
            net = (b.get(f_net) if f_net else pur) or pur or 0
            gst = (b.get(f_gst) if f_gst else 0) or 0
            hsn = (b.get(f_hsn) if f_hsn else "") or ""
            upp = (b.get(f_upp) if f_upp else 1) or 1
            exp = str((b.get(f_exp) if f_exp else "") or "")

            out.append({
                "batch": b.name,
                "expiry": exp,
                "qty": qty,
                "mrp": mrp,
                "purchase_rate": pur,
                "net_rate": net,
                "gst": gst,
                "hsn": hsn,
                "upp": upp
            })
except Exception as e:
    frappe.log_error(title="ph_batches error", message=frappe.get_traceback())

frappe.response["message"] = {"batches": out}
