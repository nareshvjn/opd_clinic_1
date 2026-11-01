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
    items = []
    for it in pi.items:
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
        "invoice": pi.name,
        "is_return": 1,
        "return_against": pi.return_against or "",
        "date": str(pi.posting_date),
        "supplier": pi.supplier,
        "bill_no": pi.bill_no or "",
        "total": abs(pi.rounded_total or pi.grand_total),
        "items": items
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
