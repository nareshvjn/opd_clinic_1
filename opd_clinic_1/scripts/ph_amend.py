# Server Script: ph_amend
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_amend
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
    frappe.throw("You don't have access to this action.")

doctype = (frappe.form_dict.get("doctype") or "").strip()
name    = (frappe.form_dict.get("name") or "").strip()

if not doctype or not name:
    frappe.throw("DocType and invoice name are required.")

if doctype not in ["Sales Invoice", "Purchase Invoice"]:
    frappe.throw("Invalid DocType.")

if not frappe.db.exists(doctype, name):
    frappe.throw(doctype + " not found: " + name)

doc = frappe.get_doc(doctype, name)

if doc.docstatus != 1:
    frappe.throw("Only submitted invoices can be edited.")

if doc.is_return:
    frappe.throw("Use the Return page to manage return notes.")

today_date = frappe.utils.getdate(frappe.utils.today())
doc_date = frappe.utils.getdate(doc.posting_date) if doc.posting_date else today_date
if doc_date < today_date and not is_admin:
    frappe.throw("Only admin accounts can edit past-dated invoices.")

# Note: The original invoice is NOT cancelled here!
# It will only be cancelled and amended when the replacement is saved.

if doctype == "Sales Invoice":
    mode = "Cash"
    if doc.payments:
        mode = doc.payments[0].mode_of_payment

    items = []
    for it in doc.items:
        batch_no = it.batch_no or ""
        upp = 1
        mrp = it.rate
        net_rate = it.rate
        gst = 0
        exp = ""
        if batch_no and frappe.db.exists("Batch", batch_no):
            b = frappe.get_doc("Batch", batch_no)
            upp = int(b.units_per_pack or 1)
            mrp = float(b.mrp or it.rate)
            net_rate = float(b.net_rate or it.rate)
            gst = float(b.gst_rate or 0)
            if b.expiry_date:
                exp = str(b.expiry_date)

        packs = int(it.qty // upp)
        units = int(round(it.qty % upp))
        items.append({
            "item": it.item_code,
            "name": it.item_name,
            "batch": batch_no,
            "packs": packs,
            "units": units,
            "qty": float(it.qty or 0),
            "rate": mrp,
            "net_rate": net_rate,
            "disc": float(it.discount_percentage or 0),
            "upp": upp,
            "expiry": exp
        })

    custom_charge = 0.0
    custom_charge_name = ""
    for tx in (doc.taxes or []):
        if tx.charge_type == "Actual" or (tx.tax_amount and not tx.rate):
            custom_charge = float(tx.tax_amount or 0)
            custom_charge_name = tx.description or ""
            break

    frappe.response["message"] = {
        "doctype": doctype,
        "name": name,
        "customer": doc.customer or "",
        "patient": doc.patient or "",
        "date": str(doc.posting_date),
        "warehouse": doc.set_warehouse or "",
        "mode": mode,
        "charge": custom_charge,
        "charge_name": custom_charge_name,
        "items": items
    }

elif doctype == "Purchase Invoice":
    items = []
    saved_lines = None
    if doc.remarks:
        try:
            rdata = json.loads(doc.remarks)
            if isinstance(rdata, dict) and "lines" in rdata and isinstance(rdata["lines"], list):
                saved_lines = rdata["lines"]
            elif isinstance(rdata, list):
                saved_lines = rdata
        except Exception:
            pass

    if saved_lines:
        items = saved_lines
    else:
        for it in doc.items:
            batch_no = it.batch_no or ""
            upp = 1
            mrp = it.rate
            gst = 0
            exp = ""
            hsn = "3004"
            pack_rate = float(it.rate)
            net_pack_rate = pack_rate
            if batch_no and frappe.db.exists("Batch", batch_no):
                b = frappe.get_doc("Batch", batch_no)
                upp = int(b.units_per_pack or 1)
                mrp = float(b.mrp or it.rate)
                gst = float(b.gst_rate or 5)
                hsn = b.hsn_code or "3004"
                if b.expiry_date:
                    exp = str(b.expiry_date)
                pack_rate = float(b.purchase_rate or (it.rate * upp))
                net_pack_rate = float(b.net_rate or pack_rate)
            else:
                pack_rate = float(it.rate * upp)
                net_pack_rate = pack_rate

            # Reconstruct billed vs free packs accurately
            if net_pack_rate > 0 and it.amount > 0:
                calc_billed = int(round(float(it.amount) / net_pack_rate))
                calc_billed_qty = calc_billed * upp
                if 0 < calc_billed_qty <= it.qty:
                    billed_packs = calc_billed
                    free_packs = int((it.qty - calc_billed_qty) // upp)
                    units = int(round((it.qty - calc_billed_qty) % upp))
                else:
                    billed_packs = int(it.qty // upp)
                    free_packs = 0
                    units = int(round(it.qty % upp))
            else:
                billed_packs = int(it.qty // upp)
                free_packs = 0
                units = int(round(it.qty % upp))

            line_amount = (billed_packs + (units / upp)) * net_pack_rate

            items.append({
                "product": it.item_name or it.item_code,
                "batch": batch_no,
                "expiry": exp,
                "hsn": hsn,
                "gst": str(gst),
                "mrp": mrp,
                "rate": pack_rate,
                "basis": "excl",
                "upp": upp,
                "packs": billed_packs,
                "billed_packs": billed_packs,
                "free_packs": free_packs,
                "units": units,
                "disc": 0,
                "disc_type": "percent",
                "amount": round(line_amount, 2),
                "net": net_pack_rate
            })

    pay_status = "Paid"
    due_date = str(doc.due_date or "")
    paid_date = str(doc.posting_date or "")
    pay_mode = "Cash"
    paid_amt = float(doc.rounded_total or doc.grand_total or 0)

    if doc.outstanding_amount and doc.outstanding_amount > 0:
        if doc.outstanding_amount >= (doc.rounded_total or doc.grand_total):
            pay_status = "Due"
            paid_amt = 0

    pes = frappe.db.sql("""
        select distinct parent from `tabPayment Entry Reference`
        where reference_doctype='Purchase Invoice' and reference_name=%s and docstatus=1
    """, name, as_dict=True)
    if pes:
        pe = frappe.get_doc("Payment Entry", pes[0].parent)
        pay_mode = pe.mode_of_payment
        paid_date = str(pe.posting_date)
        paid_amt = float(pe.paid_amount)

    courier = 0.0
    for tx in (doc.taxes or []):
        if "Courier" in (tx.description or "") or "Freight" in (tx.description or ""):
            courier += float(tx.tax_amount or 0)

    frappe.response["message"] = {
        "doctype": doctype,
        "name": name,
        "supplier": doc.supplier or "",
        "bill_no": doc.bill_no or "",
        "bill_date": str(doc.bill_date or doc.posting_date),
        "warehouse": doc.set_warehouse or "",
        "discount_percentage": float(doc.additional_discount_percentage or 0),
        "discount_amount": float(doc.discount_amount or 0),
        "courier_charges": courier,
        "payment_status": pay_status,
        "due_date": due_date,
        "paid_date": paid_date,
        "payment_mode": pay_mode,
        "paid_amount": paid_amt,
        "items": items
    }
