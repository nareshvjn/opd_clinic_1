# Server Script: sr_load
# type: API
# doctype: -
# event: Before Insert
# api_method: sr_load
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to this page.")

invoice = (frappe.form_dict.get("invoice") or "").strip()
if not invoice:
    frappe.throw("Enter an invoice number.")

if not frappe.db.exists("Sales Invoice", invoice):
    frappe.throw("Invoice not found: " + invoice)

si = frappe.get_doc("Sales Invoice", invoice)

if si.docstatus != 1:
    frappe.throw("Invoice is not submitted.")

# If this is a return invoice itself:
if si.is_return:
    orig_name = si.return_against or ""
    orig_si = frappe.get_doc("Sales Invoice", orig_name) if (orig_name and frappe.db.exists("Sales Invoice", orig_name)) else None

    this_ret_map = {}
    reason = "Wrong Medicine"
    items = []
    for it in si.items:
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

    mode = "Cash"
    if si.is_pos and si.payments:
        mode = si.payments[0].mode_of_payment or "Cash"

    edit_items = []
    if orig_si:
        other_returns = frappe.get_all(
            "Sales Invoice",
            filters={"return_against": orig_name, "docstatus": 1, "name": ["!=", si.name]},
            fields=["name"]
        )
        other_ret_map = {}
        for ret in other_returns:
            rdoc = frappe.get_doc("Sales Invoice", ret.name)
            for ri in rdoc.items:
                k = (ri.item_code, ri.batch_no or "")
                other_ret_map[k] = other_ret_map.get(k, 0.0) + abs(ri.qty)

        for it in orig_si.items:
            k = (it.item_code, it.batch_no or "")
            sold_qty = abs(it.qty)
            other_returned = other_ret_map.get(k, 0.0)
            max_qty = max(0.0, sold_qty - other_returned)
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
                "sold_qty": sold_qty,
                "max_qty": max_qty,
                "return_qty": cur_ret_qty,
                "rate": it.rate,
                "warehouse": it.warehouse or orig_si.set_warehouse or ""
            })

    frappe.response["message"] = {
        "invoice": si.name,
        "is_return": 1,
        "return_against": orig_name,
        "date": str(si.posting_date),
        "customer": si.customer,
        "total": abs(si.rounded_total or si.grand_total),
        "reason": reason,
        "mode": mode,
        "items": items,
        "edit_items": edit_items
    }
else:
    # Original sales invoice
    existing = frappe.get_all("Sales Invoice", filters={"return_against": invoice, "docstatus": 1}, fields=["name"])

    items = []
    for it in si.items:
        already = 0.0
        for ret in existing:
            rdoc = frappe.get_doc("Sales Invoice", ret.name)
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
            "sold_qty": sold_qty,
            "max_qty": max_qty,
            "rate": it.rate,
            "warehouse": it.warehouse or ""
        })

    frappe.response["message"] = {
        "invoice": si.name,
        "is_return": 0,
        "date": str(si.posting_date),
        "customer": si.customer,
        "total": si.rounded_total or si.grand_total,
        "already_returned": len(existing) > 0,
        "items": items
    }
