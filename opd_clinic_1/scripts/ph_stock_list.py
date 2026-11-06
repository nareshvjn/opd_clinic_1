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
        res = frappe.db.sql("""select sum(actual_qty) from `tabStock Ledger Entry`
            where batch_no = %s and warehouse = %s and is_cancelled = 0""", (b, w))
        if res and res[0] and res[0][0] is not None:
            return float(res[0][0])
    except:
        pass
    return None

def parse_upp_from_name(name):
    if not name:
        return 1
    clean = str(name).lower().replace("'", " ").replace("(", " ").replace(")", " ").replace("/", " ")
    words = clean.split()
    for w in words:
        if w.endswith("s") and len(w) > 1 and w[:-1].isdigit():
            val = int(w[:-1])
            if 1 < val <= 500:
                return val
    for i in range(len(words) - 1):
        if words[i].isdigit() and words[i + 1] in ("tab", "tabs", "tablet", "tablets", "cap", "caps", "capsule", "capsules", "strip", "strips") and int(words[i]) <= 500:
            return int(words[i])
    return 1

out = []
try:
    f = frappe.form_dict
    q = (f.get("q") or "").strip()
    wh = f.get("warehouse")
    show_zero = f.get("zero") not in ("0", "false")

    meta = frappe.get_meta("Batch")

    def find_f(fn):
        if meta.has_field(fn):
            return fn
        if meta.has_field("custom_" + fn):
            return "custom_" + fn
        return None

    f_exp = find_f("expiry_date")
    f_qty = find_f("batch_qty")
    f_item = "item" if meta.has_field("item") else ("item_code" if meta.has_field("item_code") else None)
    f_iname = find_f("item_name")
    f_mrp = find_f("mrp")
    f_pur = find_f("purchase_rate")
    f_net = find_f("net_rate")
    f_gst = find_f("gst_rate")
    f_hsn = find_f("hsn_code")
    f_upp = find_f("units_per_pack")

    fields = ["name"]
    for field_name in [f_item, f_iname, f_exp, f_qty, f_mrp, f_pur, f_net, f_gst, f_hsn, f_upp]:
        if field_name and field_name not in fields:
            fields.append(field_name)

    filters = {}
    if meta.has_field("disabled"):
        filters["disabled"] = 0

    if not show_zero and f_qty:
        filters[f_qty] = [">", 0]

    or_filters = []
    if q:
        if f_item:
            or_filters.append(["Batch", f_item, "like", "%" + q + "%"])
        if f_iname:
            or_filters.append(["Batch", f_iname, "like", "%" + q + "%"])
        or_filters.append(["Batch", "name", "like", "%" + q + "%"])

    order_parts = []
    if f_iname:
        order_parts.append(f_iname + " asc")
    if f_exp:
        order_parts.append(f_exp + " asc")
    order_parts.append("name asc")
    order_by = ", ".join(order_parts)

    rows = frappe.get_all("Batch", filters=filters, or_filters=or_filters if or_filters else None,
        fields=fields, order_by=order_by, limit=500)

    for b in rows:
        item_code = b.get(f_item) if f_item else ""
        item_name = b.get(f_iname) if f_iname else ""
        if not item_name and item_code:
            item_name = frappe.db.get_value("Item", item_code, "item_name") or item_code

        qty = (b.get(f_qty) if f_qty else 0) or 0
        if wh:
            w = wh_qty(b.name, wh)
            if w is not None:
                qty = w
        elif not f_qty or qty == 0:
            try:
                s = frappe.db.sql("""select sum(actual_qty) from `tabStock Ledger Entry`
                    where batch_no = %s and is_cancelled = 0""", (b.name,))
                if s and s[0] and s[0][0] is not None:
                    qty = float(s[0][0])
            except:
                pass

        if qty <= 0 and not show_zero:
            continue

        mrp = (b.get(f_mrp) if f_mrp else 0) or 0
        pur = (b.get(f_pur) if f_pur else 0) or 0
        net = (b.get(f_net) if f_net else pur) or pur or 0
        gst = (b.get(f_gst) if f_gst else 0) or 0
        hsn = (b.get(f_hsn) if f_hsn else "") or ""
        upp = (b.get(f_upp) if f_upp else 1) or 1
        exp = str((b.get(f_exp) if f_exp else "") or "")

        if upp <= 1:
            name_upp = parse_upp_from_name(item_name or item_code)
            if name_upp > 1:
                upp = name_upp
        if upp < 1:
            upp = 1

        if mrp <= 0 and pur > 0:
            mrp = pur

        out.append({
            "batch": b.name,
            "item": item_code,
            "name": item_name or item_code or b.name,
            "expiry": exp,
            "qty": qty if qty > 0 else 0,
            "mrp": mrp,
            "purchase_rate": pur,
            "net_rate": net,
            "gst": gst,
            "hsn": hsn,
            "upp": upp
        })

    if show_zero:
        seen_items = set()
        for x in out:
            if x.get("item"):
                seen_items.add(x["item"])

        iq = []
        if q:
            iq = [["Item", "item_name", "like", "%" + q + "%"], ["Item", "item_code", "like", "%" + q + "%"]]
        items = frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1}, or_filters=iq if iq else None,
            fields=["name", "item_name", "item_group", "has_batch_no"], order_by="item_name asc", limit=500)
        for it in items:
            if it.name in seen_items:
                continue
            grp = (it.item_group or "").lower()
            if it.item_group != "Drug" and not it.has_batch_no and "drug" not in grp and "med" not in grp:
                continue
            seen_items.add(it.name)
            out.append({
                "batch": "",
                "item": it.name,
                "name": it.item_name or it.name,
                "expiry": "",
                "qty": 0,
                "mrp": 0,
                "purchase_rate": 0,
                "net_rate": 0,
                "gst": 0,
                "hsn": "",
                "upp": 1
            })
except Exception as e:
    frappe.log_error(title="ph_stock_list error", message=frappe.get_traceback())

frappe.response["message"] = {"batches": out}
