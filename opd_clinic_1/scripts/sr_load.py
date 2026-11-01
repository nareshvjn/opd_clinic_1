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
    items = []
    for it in si.items:
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
            "qty": abs(it.qty),
            "rate": it.rate
        })
    frappe.response["message"] = {
        "invoice": si.name,
        "is_return": 1,
        "return_against": si.return_against or "",
        "date": str(si.posting_date),
        "customer": si.customer,
        "total": abs(si.rounded_total or si.grand_total),
        "items": items
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
