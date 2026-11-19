# Server Script: pr_load
# type: API
# doctype: -
# event: Before Insert
# api_method: pr_load
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to this page.")

invoice = (frappe.form_dict.get("invoice") or "").strip()
if not invoice:
    frappe.throw("Enter an invoice number.")

if not frappe.db.exists("Purchase Invoice", invoice):
    frappe.throw("Purchase invoice not found: " + invoice)

pi = frappe.get_doc("Purchase Invoice", invoice)
if pi.docstatus != 1:
    frappe.throw("Invoice is not submitted.")

# If this is a return invoice itself:
if pi.is_return:
    orig_name = pi.return_against or ""
    orig_pi = frappe.get_doc("Purchase Invoice", orig_name) if (orig_name and frappe.db.exists("Purchase Invoice", orig_name)) else None

    this_ret_map = {}
    reason = "Wrong Item"
    items = []
    for it in pi.items:
        expiry = ""
        if it.batch_no:
            expiry = frappe.db.get_value("Batch", it.batch_no, "expiry_date") or ""
            if expiry:
                expiry = str(expiry)
        qty = abs(it.qty)
        rate = it.rate
        key = (it.item_code, it.batch_no or "")
        this_ret_map[key] = this_ret_map.get(key, 0.0) + qty
        if it.description:
            reason = it.description
        items.append({
            "item_code": it.item_code,
            "item_name": it.item_name,
            "batch_no": it.batch_no or "",
            "expiry": expiry,
            "qty": qty,
            "rate": rate
        })

    edit_items = []
    if orig_pi:
        other_returns = frappe.get_all(
            "Purchase Invoice",
            filters={"return_against": orig_name, "docstatus": 1, "name": ["!=", pi.name]},
            fields=["name"]
        )
        other_ret_map = {}
        for ret in other_returns:
            rdoc = frappe.get_doc("Purchase Invoice", ret.name)
            for ri in rdoc.items:
                k = (ri.item_code, ri.batch_no or "")
                other_ret_map[k] = other_ret_map.get(k, 0.0) + abs(ri.qty)

        for it in orig_pi.items:
            k = (it.item_code, it.batch_no or "")
            bought_qty = abs(it.qty)
            other_returned = other_ret_map.get(k, 0.0)
            max_qty = max(0.0, bought_qty - other_returned)
            cur_ret_qty = this_ret_map.get(k, 0.0)

            expiry = ""
            if it.batch_no:
                expiry = frappe.db.get_value("Batch", it.batch_no, "expiry_date") or ""
                if expiry:
                    expiry = str(expiry)

            edit_items.append({
                "item_code": it.item_code,
                "item_name": it.item_name,
                "batch_no": it.batch_no or "",
                "expiry": expiry,
                "bought_qty": bought_qty,
                "max_qty": max_qty,
                "return_qty": cur_ret_qty,
                "rate": it.rate,
                "warehouse": it.warehouse or orig_pi.set_warehouse or ""
            })

    frappe.response["message"] = {
        "invoice": pi.name,
        "is_return": 1,
        "return_against": orig_name,
        "date": str(pi.posting_date),
        "supplier": pi.supplier,
        "bill_no": pi.bill_no or (orig_pi.bill_no if orig_pi else "") or "",
        "total": abs(pi.rounded_total or pi.grand_total),
        "reason": reason,
        "items": items,
        "edit_items": edit_items
    }
else:
    # Original purchase invoice
    existing = frappe.get_all("Purchase Invoice", filters={"return_against": invoice, "docstatus": 1}, fields=["name"])
    items = []
    for it in pi.items:
        already = 0.0
        for ret in existing:
            rdoc = frappe.get_doc("Purchase Invoice", ret.name)
            for ri in rdoc.items:
                if ri.item_code == it.item_code and (ri.batch_no or "") == (it.batch_no or ""):
                    already += abs(ri.qty)

        sold_qty = abs(it.qty)
        max_qty = max(0.0, sold_qty - already)

        expiry = ""
        if it.batch_no:
            expiry = frappe.db.get_value("Batch", it.batch_no, "expiry_date") or ""
            if expiry:
                expiry = str(expiry)

        items.append({
            "item_code": it.item_code,
            "item_name": it.item_name,
            "batch_no": it.batch_no or "",
            "expiry": expiry,
            "bought_qty": sold_qty,
            "max_qty": max_qty,
            "rate": it.rate,
            "warehouse": it.warehouse or ""
        })

    frappe.response["message"] = {
        "invoice": pi.name,
        "is_return": 0,
        "date": str(pi.posting_date),
        "supplier": pi.supplier,
        "bill_no": pi.bill_no or "",
        "total": pi.rounded_total or pi.grand_total,
        "already_returned": len(existing) > 0,
        "items": items
    }
