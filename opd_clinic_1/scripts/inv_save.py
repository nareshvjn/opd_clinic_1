# Server Script: inv_save
# type: API
# doctype: -
# event: Before Insert
# api_method: inv_save
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
    for r in ["Physician", "Accounts Manager", "Accounts User", "Sales User", "Stock Manager", "Stock User"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            ok = True
            break
if not ok:
    frappe.throw("You do not have permission to create invoices.")

def num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0

f = frappe.form_dict
action = (f.get("action") or "").strip()
today_str = str(frappe.utils.today())
today_date = frappe.utils.getdate(today_str)

if action == "cancel":
    inv_name = (f.get("invoice") or "").strip()
    if not inv_name or not frappe.db.exists("Sales Invoice", inv_name):
        frappe.throw("Invoice not found.")
    doc = frappe.get_doc("Sales Invoice", inv_name)
    if doc.docstatus == 2:
        frappe.throw("Invoice is already cancelled.")
    if doc.posting_date and frappe.utils.getdate(doc.posting_date) < today_date and not is_admin:
        frappe.throw("Only admin accounts can cancel past-dated invoices.")

    if doc.docstatus == 0:
        frappe.delete_doc("Sales Invoice", inv_name, ignore_permissions=True)
        frappe.response["message"] = {"status": "deleted", "invoice": inv_name}
    else:
        pes = frappe.db.sql("""
            select distinct parent from `tabPayment Entry Reference`
            where reference_doctype='Sales Invoice' and reference_name=%s and docstatus=1
        """, inv_name, as_dict=True)
        for p in pes:
            pe_doc = frappe.get_doc("Payment Entry", p.parent)
            if pe_doc.docstatus == 1:
                pe_doc.cancel()
        doc.cancel()
        frappe.response["message"] = {"status": "cancelled", "invoice": inv_name}

else:
    lines = json.loads(f.get("lines") or "[]")
    customer_input = (f.get("customer") or "").strip()
    patient = (f.get("patient") or "").strip()
    practitioner = (f.get("practitioner") or "").strip()
    mode = (f.get("mode") or "").strip()
    remarks = (f.get("remarks") or "").strip()
    charge_name = (f.get("charge_name") or "").strip()
    charge_amt = num(f.get("charge"))
    save_draft = str(f.get("save_draft") or "0").strip() in ["1", "true", "True"]
    amend_invoice = (f.get("amend_invoice") or "").strip()

    posting_date = (f.get("posting_date") or "").strip() or today_str

    try:
        p_date = frappe.utils.getdate(posting_date)
    except Exception:
        frappe.throw("Invalid invoice date.")

    if p_date < today_date and not is_admin:
        frappe.throw("Only admin accounts can create backdated invoices. Use today's date.")

    if not lines:
        frappe.throw("Add at least one line item to the invoice.")

    updating_draft = False
    amend_from = ""
    if amend_invoice:
        if not frappe.db.exists("Sales Invoice", amend_invoice):
            frappe.throw("Original invoice not found: " + amend_invoice)
        old_si = frappe.get_doc("Sales Invoice", amend_invoice)
        if old_si.docstatus == 2:
            frappe.throw("Cannot edit a cancelled invoice.")
        if old_si.posting_date and frappe.utils.getdate(old_si.posting_date) < today_date and not is_admin:
            frappe.throw("Only admin accounts can edit past-dated invoices.")
        if old_si.docstatus == 0:
            updating_draft = True
        else:
            pes = frappe.db.sql("""
                select distinct parent from `tabPayment Entry Reference`
                where reference_doctype='Sales Invoice' and reference_name=%s and docstatus=1
            """, amend_invoice, as_dict=True)
            for p in pes:
                pe_doc = frappe.get_doc("Payment Entry", p.parent)
                if pe_doc.docstatus == 1:
                    pe_doc.cancel()
            old_si.cancel()
            amend_from = amend_invoice

    company = frappe.db.get_single_value("Global Defaults", "default_company")
    co = frappe.db.get_value("Company", company,
        ["default_receivable_account", "default_income_account", "cost_center", "default_currency"], as_dict=True)

    # Resolve Customer (prefer Patient's linked Customer if Patient was chosen cleanly)
    customer = ""
    if patient and frappe.db.exists("Patient", patient):
        pat_vals = frappe.db.get_value("Patient", patient, ["patient_name", "customer"], as_dict=True)
        if pat_vals and pat_vals.get("customer") and frappe.db.exists("Customer", pat_vals.get("customer")):
            if not customer_input or customer_input == pat_vals.get("patient_name") or customer_input == pat_vals.get("customer"):
                customer = pat_vals.get("customer")

    if not customer and customer_input:
        if frappe.db.exists("Customer", customer_input):
            customer = customer_input
        else:
            matched = frappe.db.get_value("Customer", {"customer_name": customer_input, "disabled": 0}, "name")
            if matched:
                customer = matched
            else:
                c = frappe.new_doc("Customer")
                c.customer_name = customer_input
                c.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
                c.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
                c.customer_type = "Individual"
                c.insert(ignore_permissions=True)
                customer = c.name

    if not customer:
        for fallback_name in ["Walk-in Customer", "Walk-in"]:
            if frappe.db.exists("Customer", fallback_name):
                customer = fallback_name
                break
        if not customer:
            c = frappe.new_doc("Customer")
            c.customer_name = "Walk-in Customer"
            c.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
            c.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
            c.customer_type = "Individual"
            c.insert(ignore_permissions=True)
            customer = c.name

    # Resolve or create generic fallback Service Item for custom ad-hoc service lines
    def resolve_misc_service_item(cached):
        if cached:
            return cached
        for candidate in ["MISC-SERVICE", "CLINIC-SERVICE"]:
            if frappe.db.exists("Item", candidate):
                return candidate
        svc_group = "Services"
        if not frappe.db.exists("Item Group", svc_group):
            svc_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
        uom = "Nos"
        if not frappe.db.exists("UOM", uom):
            uom = frappe.db.get_value("UOM", {}, "name") or "Unit"
        it = frappe.new_doc("Item")
        it.item_code = "MISC-SERVICE"
        it.item_name = "Clinic Service / Procedure"
        it.item_group = svc_group
        it.stock_uom = uom
        it.is_stock_item = 0
        it.is_sales_item = 1
        it.insert(ignore_permissions=True)
        return it.name

    if updating_draft:
        si = frappe.get_doc("Sales Invoice", amend_invoice)
        si.items = []
        si.taxes = []
        si.payments = []
        si.is_pos = 0
        si.remarks = ""
    else:
        si = frappe.new_doc("Sales Invoice")
        if amend_from:
            si.amended_from = amend_from

    si.customer = customer
    si.company = company
    si.posting_date = posting_date
    si.set_posting_time = 1
    # General / miscellaneous invoice does not deduct pharmacy batch stock
    si.update_stock = 0
    si.ignore_pricing_rule = 1

    if si.meta.has_field("patient"):
        si.patient = patient if (patient and frappe.db.exists("Patient", patient)) else None

    if si.meta.has_field("practitioner"):
        si.practitioner = practitioner or None

    remark_parts = []
    if practitioner:
        prac_name = frappe.db.get_value("Healthcare Practitioner", practitioner, "practitioner_name") or practitioner
        remark_parts.append("Doctor: " + prac_name)
    if remarks:
        remark_parts.append(remarks)
    if remark_parts:
        si.remarks = " | ".join(remark_parts)

    misc_item_code = ""
    line_pricing = []
    for ln in lines:
        item_code = (ln.get("item_code") or "").strip()
        custom_name = (ln.get("item_name") or "").strip()
        desc = (ln.get("description") or "").strip()
        qty = num(ln.get("qty"))
        rate = num(ln.get("rate"))
        disc = num(ln.get("disc"))

        if qty <= 0:
            frappe.throw("Every line item must have quantity greater than zero.")
        if rate < 0:
            frappe.throw("Rate cannot be negative.")
        if disc < 0:
            disc = 0.0
        elif disc > 100:
            disc = 100.0

        resolved_code = ""
        if item_code and frappe.db.exists("Item", item_code):
            resolved_code = item_code
        elif custom_name:
            matched_item = frappe.db.get_value("Item", {"item_name": custom_name, "is_stock_item": 0, "disabled": 0}, "name")
            if matched_item:
                resolved_code = matched_item
            else:
                misc_item_code = resolve_misc_service_item(misc_item_code)
                resolved_code = misc_item_code
        else:
            frappe.throw("Each line item must specify an item or service name.")

        item_meta_vals = frappe.db.get_value("Item", resolved_code, ["item_name", "stock_uom"], as_dict=True) or {}
        final_name = custom_name or item_meta_vals.get("item_name") or resolved_code
        final_desc = desc or final_name
        uom = item_meta_vals.get("stock_uom") or "Nos"

        disc_unit = rate * (disc / 100.0)
        net_unit = rate - disc_unit

        line_pricing.append({
            "item_name": final_name,
            "description": final_desc,
            "price_list_rate": rate,
            "discount_percentage": disc,
            "discount_amount": disc_unit,
            "rate": net_unit
        })

        si.append("items", {
            "item_code": resolved_code,
            "item_name": final_name,
            "description": final_desc,
            "qty": qty,
            "uom": uom,
            "stock_uom": uom,
            "conversion_factor": 1,
            "price_list_rate": rate,
            "margin_type": "",
            "margin_rate_or_amount": 0,
            "discount_percentage": disc,
            "discount_amount": disc_unit,
            "rate": net_unit,
            "income_account": co.default_income_account if co else None,
            "cost_center": co.cost_center if co else None
        })

    si.run_method("set_missing_values")
    # Re-apply explicit item names, descriptions, and discounted rates after set_missing_values().
    si.ignore_pricing_rule = 1
    for idx in range(len(line_pricing)):
        row = si.items[idx]
        lp = line_pricing[idx]
        row.item_name = lp["item_name"]
        row.description = lp["description"]
        row.price_list_rate = lp["price_list_rate"]
        row.margin_type = ""
        row.margin_rate_or_amount = 0
        row.discount_percentage = lp["discount_percentage"]
        row.discount_amount = lp["discount_amount"]
        row.rate = lp["rate"]

    if not si.debit_to and co:
        si.debit_to = co.default_receivable_account

    if charge_amt > 0:
        charge_acc = co.default_income_account if co else None
        if not charge_acc:
            charge_acc = frappe.db.get_value("Account", {"account_type": "Income Account", "company": company, "is_group": 0}, "name")
        if not charge_acc:
            charge_acc = frappe.db.get_value("Account", {"account_name": ["like", "%Income%"], "company": company, "is_group": 0}, "name")
        si.append("taxes", {
            "charge_type": "Actual",
            "account_head": charge_acc,
            "description": charge_name or "Additional Charge",
            "tax_amount": charge_amt,
            "cost_center": co.cost_center if co else None
        })

    si.run_method("calculate_taxes_and_totals")

    pay_amt = si.rounded_total if (si.rounded_total is not None and not si.disable_rounded_total) else si.grand_total
    paid = False
    note = ""

    if not save_draft and mode and mode != "Credit":
        pos_acc = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company}, "default_account")
        if pos_acc:
            si.is_pos = 1
            si.append("payments", {
                "mode_of_payment": mode,
                "account": pos_acc,
                "amount": pay_amt
            })
            paid = True

    if updating_draft:
        si.save(ignore_permissions=True)
    else:
        si.insert(ignore_permissions=True)

    if not save_draft:
        si.submit()
        if not paid and mode and mode != "Credit" and (pay_amt or 0) > 0:
            try:
                pe = frappe.call("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
                    dt="Sales Invoice", dn=si.name)
                pe.mode_of_payment = mode
                pe.posting_date = posting_date
                pe.reference_no = si.name
                pe.reference_date = posting_date
                pe.insert(ignore_permissions=True)
                pe.submit()
                paid = True
            except Exception:
                note = "Invoice submitted, but payment entry was not created automatically."

    frappe.response["message"] = {
        "invoice": si.name,
        "customer": si.customer,
        "total": pay_amt,
        "docstatus": si.docstatus,
        "paid": paid,
        "mode": mode,
        "note": note
    }
