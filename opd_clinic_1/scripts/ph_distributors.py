# Server Script: ph_distributors
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_distributors
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to this page.")

q = (frappe.form_dict.get("q") or "").strip()

# Query invoices grouped by supplier
sql = """
    select
        supplier,
        count(name) as bill_count,
        ifnull(sum(case when is_return = 0 then outstanding_amount else 0 end), 0) as pending_amount,
        ifnull(sum(if(ifnull(rounded_total, 0) = 0, grand_total, rounded_total)), 0) as total_amount,
        max(ifnull(bill_date, posting_date)) as last_bill_date
    from `tabPurchase Invoice`
    where docstatus = 1
    group by supplier
"""
invoice_stats = {r.supplier: r for r in frappe.db.sql(sql, as_dict=True)}

# Get all suppliers
suppliers = frappe.get_all("Supplier", fields=["name", "supplier_name"], order_by="name asc")
seen = set()
distributors = []

for s in suppliers:
    name = s.name
    seen.add(name)
    stat = invoice_stats.get(name) or {}
    distributors.append({
        "supplier": name,
        "supplier_name": s.supplier_name or name,
        "bill_count": int(stat.get("bill_count") or 0),
        "pending_amount": float(stat.get("pending_amount") or 0),
        "total_amount": float(stat.get("total_amount") or 0),
        "last_bill_date": str(stat.get("last_bill_date") or "")
    })

# If any invoices had a supplier name not in `tabSupplier`
for supp_name, stat in invoice_stats.items():
    if supp_name not in seen:
        distributors.append({
            "supplier": supp_name,
            "supplier_name": supp_name,
            "bill_count": int(stat.get("bill_count") or 0),
            "pending_amount": float(stat.get("pending_amount") or 0),
            "total_amount": float(stat.get("total_amount") or 0),
            "last_bill_date": str(stat.get("last_bill_date") or "")
        })

# Filter by search query if passed
if q:
    ql = q.lower()
    distributors = [d for d in distributors if ql in d["supplier"].lower() or ql in d["supplier_name"].lower()]

# Sort: highest pending amount first, then latest bill date
distributors.sort(key=lambda x: (x["pending_amount"], x["last_bill_date"] or ""), reverse=True)

total_pending = sum(d["pending_amount"] for d in distributors)
total_purchased = sum(d["total_amount"] for d in distributors)

frappe.response["message"] = {
    "distributors": distributors,
    "total_pending": total_pending,
    "total_purchased": total_purchased
}
