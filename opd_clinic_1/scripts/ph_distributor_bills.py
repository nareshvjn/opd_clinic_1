# Server Script: ph_distributor_bills
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_distributor_bills
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = (user == "Administrator")
if not is_admin:
    for r in ["Healthcare Administrator", "System Manager"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            is_admin = True
            break
ok = is_admin
if not ok:
    for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            ok = True
            break
if not ok:
    frappe.throw("You don't have access to this page.")

supplier = (frappe.form_dict.get("supplier") or frappe.form_dict.get("distributor") or "").strip()
if not supplier:
    frappe.throw("Distributor name is required.")

# Fetch supplier info
supplier_name = supplier
if frappe.db.exists("Supplier", supplier):
    supplier_name = frappe.db.get_value("Supplier", supplier, "supplier_name") or supplier

# Fetch all submitted purchase invoices for this distributor
invoices_raw = frappe.get_all(
    "Purchase Invoice",
    filters={"supplier": supplier, "docstatus": 1},
    fields=["name", "bill_no", "bill_date", "posting_date", "posting_time", "due_date",
            "rounded_total", "grand_total", "outstanding_amount", "is_return", "return_against"],
    order_by="posting_date desc, posting_time desc, name desc",
    limit=200
)

invoices = []
total_pending = 0.0
total_purchased = 0.0

for iv in invoices_raw:
    tot = float(iv.rounded_total if (iv.rounded_total and iv.rounded_total > 0) else (iv.grand_total or 0))
    if iv.is_return:
        tot = -abs(tot)
    
    out = float(iv.outstanding_amount or 0)
    paid = max(0.0, tot - out) if not iv.is_return else 0.0

    if not iv.is_return:
        total_pending += out
        total_purchased += tot

    status = "Paid"
    if iv.is_return:
        status = "Return"
    elif out >= (tot - 0.01) and tot > 0:
        status = "Unpaid"
    elif out > 0.01:
        status = "Partially Paid"

    invoices.append({
        "name": iv.name,
        "bill_no": iv.bill_no or "",
        "bill_date": str(iv.bill_date or iv.posting_date or ""),
        "posting_date": str(iv.posting_date or ""),
        "due_date": str(iv.due_date or ""),
        "total": tot,
        "outstanding": out,
        "paid": paid,
        "status": status,
        "is_return": int(iv.is_return or 0),
        "return_against": iv.return_against or ""
    })

frappe.response["message"] = {
    "distributor": {
        "id": supplier,
        "name": supplier_name
    },
    "summary": {
        "total_purchased": total_purchased,
        "total_pending": total_pending,
        "bill_count": len([x for x in invoices if not x["is_return"]]),
        "return_count": len([x for x in invoices if x["is_return"]]),
        "last_bill_date": invoices[0]["bill_date"] if invoices else ""
    },
    "invoices": invoices,
    "is_admin": is_admin,
    "today": str(frappe.utils.today())
}
