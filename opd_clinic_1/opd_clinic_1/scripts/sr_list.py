# Server Script: sr_list
# type: API
# doctype: -
# event: Before Insert
# api_method: sr_list
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to this page.")

date = (frappe.form_dict.get("date") or "").strip()
if not date:
    frappe.throw("Select a date.")

# Show submitted pharmacy sales & pharmacy return notes
rows = frappe.db.sql("""
    SELECT DISTINCT si.name, si.customer, si.rounded_total, si.grand_total, si.posting_time, si.is_return, si.return_against
    FROM `tabSales Invoice` si
    INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
    INNER JOIN `tabItem` i ON i.name = sii.item_code
    WHERE si.posting_date = %(date)s
      AND si.docstatus = 1
      AND i.item_group = 'Drug'
    ORDER BY si.posting_time DESC
    LIMIT 100
""", {"date": date}, as_dict=True)

invoices = []
for r in rows:
    invoices.append({
        "name": r.name,
        "customer": r.customer,
        "total": abs(r.rounded_total or r.grand_total),
        "time": str(r.posting_time or "")[:5],
        "is_return": int(r.is_return or 0),
        "return_against": r.return_against or ""
    })

frappe.response["message"] = {"invoices": invoices}
