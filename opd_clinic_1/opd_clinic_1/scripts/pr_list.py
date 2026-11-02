# Server Script: pr_list
# type: API
# doctype: -
# event: Before Insert
# api_method: pr_list
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to this page.")

date     = (frappe.form_dict.get("date")     or "").strip()
supplier = (frappe.form_dict.get("supplier") or "").strip()
invoice  = (frappe.form_dict.get("invoice")  or "").strip()

if not date and not supplier and not invoice:
    frappe.throw("Enter at least one filter — date, supplier, or invoice number.")

# Allow docstatus 1 (submitted) and both regular and return invoices
filters = {"docstatus": 1}
if date:
    filters["posting_date"] = date
if supplier:
    filters["supplier"] = ["like", "%" + supplier + "%"]
if invoice:
    filters["name"] = ["like", "%" + invoice + "%"]

rows = frappe.get_all(
    "Purchase Invoice",
    filters=filters,
    fields=["name", "supplier", "bill_no", "rounded_total", "grand_total", "posting_date", "posting_time", "is_return", "return_against"],
    order_by="posting_date desc, posting_time desc",
    limit=100
)

invoices = []
for r in rows:
    invoices.append({
        "name": r.name,
        "supplier": r.supplier,
        "bill_no": r.bill_no or "",
        "total": abs(r.rounded_total or r.grand_total),
        "date": str(r.posting_date or ""),
        "time": str(r.posting_time or "")[:5],
        "is_return": int(r.is_return or 0),
        "return_against": r.return_against or ""
    })

frappe.response["message"] = {"invoices": invoices}
