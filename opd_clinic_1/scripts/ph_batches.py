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

def ensure_batch_fields():
    meta = frappe.get_meta("Batch")
    needed = [
        ("mrp", "MRP", "Currency", "batch_qty"),
        ("units_per_pack", "Units Per Pack", "Int", "mrp"),
        ("purchase_rate", "Purchase Rate", "Currency", "units_per_pack"),
        ("net_rate", "Net Rate", "Currency", "purchase_rate"),
        ("gst_rate", "GST Rate", "Percent", "net_rate"),
        ("hsn_code", "HSN Code", "Data", "gst_rate")
    ]
    created = False
    for fn, label, ftype, after in needed:
        if not (meta.has_field(fn) or meta.has_field("custom_" + fn)):
            try:
                cf = frappe.new_doc("Custom Field")
                cf.dt = "Batch"
                cf.fieldname = fn
                cf.label = label
                cf.fieldtype = ftype
                if after:
                    cf.insert_after = after
                cf.insert(ignore_permissions=True)
                created = True
            except Exception:
                pass
    if created:
        try:
            frappe.clear_cache(doctype="Batch")
        except Exception:
            pass

try:
    ensure_batch_fields()
except Exception:
    pass

try:
    item = (frappe.form_dict.get("item") or "").strip()
    if item:
        item_name = frappe.db.get_value("Item", item, "item_name") or item
        item_upp = parse_upp_from_name(item_name)
        if item_upp <= 1 and item != item_name:
            item_upp = parse_upp_from_name(item)

        item_mrp = 0
        try:
            p = frappe.db.get_value("Item Price", {"item_code": item, "selling": 1, "price_list_rate": [">", 0]}, "price_list_rate")
            if p:
                item_mrp = float(p)
        except Exception:
            pass
        if not item_mrp:
            try:
                sr = frappe.db.get_value("Item", item, "standard_rate")
                if sr:
                    item_mrp = float(sr)
            except Exception:
                pass

        batches = frappe.db.sql("""
            SELECT * FROM `tabBatch`
            WHERE (item = %s OR name IN (SELECT parent FROM `tabStock Ledger Entry` WHERE item_code = %s))
              AND (disabled = 0 OR disabled IS NULL)
            ORDER BY ifnull(expiry_date, '9999-12-31') asc, name asc
        """, (item, item), as_dict=True)

        for b in batches:
            bname = b.get("name")
            qty = b.get("batch_qty") or 0
            try:
                s = frappe.db.sql("""select sum(actual_qty) from `tabStock Ledger Entry`
                    where batch_no = %s and is_cancelled = 0""", (bname,))
                if s and s[0] and s[0][0] is not None:
                    qty = float(s[0][0])
            except Exception:
                pass

            mrp = float(b.get("mrp") or b.get("custom_mrp") or 0)
            pur = float(b.get("purchase_rate") or b.get("custom_purchase_rate") or 0)
            net = float(b.get("net_rate") or b.get("custom_net_rate") or pur or 0)
            gst = float(b.get("gst_rate") or b.get("custom_gst_rate") or 0)
            hsn = str(b.get("hsn_code") or b.get("custom_hsn_code") or "")
            upp = int(b.get("units_per_pack") or b.get("custom_units_per_pack") or 0)
            exp = str(b.get("expiry_date") or "")

            if upp <= 1 and item_upp > 1:
                upp = item_upp
            if upp < 1:
                upp = 1

            if pur <= 0 or net <= 0:
                try:
                    se_rate = frappe.db.sql("""
                        SELECT basic_rate FROM `tabStock Entry Detail`
                        WHERE batch_no = %s AND docstatus = 1 AND basic_rate > 0
                        ORDER BY creation desc LIMIT 1
                    """, (bname,))
                    if se_rate and se_rate[0] and se_rate[0][0]:
                        val = float(se_rate[0][0])
                        pur = round(val * upp, 2)
                        net = pur
                except Exception:
                    pass

            if mrp <= 0:
                if item_mrp > 0:
                    mrp = item_mrp
                elif pur > 0:
                    mrp = pur

            heal_dict = {}
            if mrp > 0 and not (b.get("mrp") or b.get("custom_mrp")):
                heal_dict["mrp"] = mrp
                heal_dict["custom_mrp"] = mrp
            if upp > 1 and not (b.get("units_per_pack") or b.get("custom_units_per_pack")):
                heal_dict["units_per_pack"] = upp
                heal_dict["custom_units_per_pack"] = upp
            if pur > 0 and not (b.get("purchase_rate") or b.get("custom_purchase_rate")):
                heal_dict["purchase_rate"] = pur
                heal_dict["custom_purchase_rate"] = pur

            for k, v in heal_dict.items():
                try:
                    frappe.db.set_value("Batch", bname, k, v, update_modified=False)
                except Exception:
                    pass

            out.append({
                "batch": bname,
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
