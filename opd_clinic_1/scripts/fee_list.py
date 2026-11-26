# Server Script: fee_list
# type: API
# doctype: -
# event: Before Insert
# api_method: fee_list
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
    frappe.throw("You don't have permission to view fee invoices.")

today_str = str(frappe.utils.today())
date = (frappe.form_dict.get("date") or "").strip() or today_str
try:
    frappe.utils.getdate(date)
except Exception:
    frappe.throw("Invalid invoice date.")

status_filter = (frappe.form_dict.get("status") or "all").strip().lower()
if status_filter not in ("all", "submitted", "draft"):
    status_filter = "all"

docstatus_cond = "si.docstatus = 1" if status_filter == "submitted" else ("si.docstatus = 0" if status_filter == "draft" else "si.docstatus < 2")

si_meta = None
try:
    si_meta = frappe.get_meta("Sales Invoice")
except Exception:
    si_meta = None

opt_si_cols = []
for c in ("patient", "patient_name", "ref_practitioner", "practitioner", "set_warehouse", "posting_time", "outstanding_amount"):
    if si_meta and si_meta.has_field(c):
        opt_si_cols.append("si.`" + c + "`")

extra_select = (", " + ", ".join(opt_si_cols)) if opt_si_cols else ""
rows = frappe.db.sql("""
    SELECT si.name, si.customer, si.customer_name, si.rounded_total, si.grand_total,
           si.docstatus, si.is_return, si.return_against, si.update_stock, si.remarks""" + extra_select + """
    FROM `tabSales Invoice` si
    WHERE si.posting_date = %(date)s
      AND """ + docstatus_cond + """
      AND ifnull(si.update_stock, 0) = 0
    ORDER BY si.docstatus DESC, si.modified DESC
    LIMIT 200
""", {"date": date}, as_dict=True)

drug_codes = set()
try:
    if frappe.db.exists("DocType", "Medication"):
        med_meta = frappe.get_meta("Medication")
        for mf in ("item", "item_code"):
            if med_meta.has_field(mf):
                for mr in frappe.get_all("Medication", fields=[mf], limit=2000):
                    if mr.get(mf):
                        drug_codes.add(mr.get(mf))
    if frappe.db.exists("DocType", "Medication Linked Item"):
        mli_meta = frappe.get_meta("Medication Linked Item")
        if mli_meta.has_field("item"):
            for mr in frappe.get_all("Medication Linked Item", fields=["item"], limit=2000):
                if mr.get("item"):
                    drug_codes.add(mr.get("item"))
except Exception:
    pass

inv_names = [r.name for r in rows if r.get("name")]
items_by_parent = {}
item_codes = []
seen_item_codes = set()
if inv_names:
    sii_fields = ["parent", "item_code", "item_name", "description"]
    try:
        sii_meta = frappe.get_meta("Sales Invoice Item")
        for opt_f in ("batch_no", "item_group", "is_stock_item", "reference_dt"):
            if sii_meta.has_field(opt_f):
                sii_fields.append(opt_f)
    except Exception:
        pass
    for it in frappe.get_all("Sales Invoice Item", filters={"parent": ["in", inv_names]}, fields=sii_fields, order_by="idx asc", limit=1500):
        items_by_parent.setdefault(it.parent, []).append(it)
        ic = str(it.get("item_code") or "").strip()
        if ic and ic not in seen_item_codes:
            seen_item_codes.add(ic)
            item_codes.append(ic)

item_meta_map = {}
if item_codes:
    it_fields = ["name", "item_name"]
    try:
        it_meta = frappe.get_meta("Item")
        for opt_f in ("item_group", "is_stock_item"):
            if it_meta.has_field(opt_f):
                it_fields.append(opt_f)
    except Exception:
        pass
    try:
        for im in frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=it_fields, limit=1500):
            item_meta_map[im.name] = im
    except Exception:
        pass

prac_ids = []
seen_pracs = set()
pat_ids = []
seen_pats = set()
for r in rows:
    pr = str(r.get("ref_practitioner") or r.get("practitioner") or "").strip()
    if pr and pr not in seen_pracs:
        seen_pracs.add(pr)
        prac_ids.append(pr)
    pt = str(r.get("patient") or "").strip()
    if pt and pt not in seen_pats:
        seen_pats.add(pt)
        pat_ids.append(pt)

prac_map = {}
if prac_ids:
    try:
        for pr in frappe.get_all("Healthcare Practitioner", filters={"name": ["in", prac_ids]}, fields=["name", "practitioner_name"], limit=200):
            prac_map[pr.name] = pr.get("practitioner_name") or pr.name
    except Exception:
        pass

pat_map = {}
if pat_ids:
    try:
        for p in frappe.get_all("Patient", filters={"name": ["in", pat_ids]}, fields=["name", "patient_name", "mobile"], limit=500):
            pat_map[p.name] = p
    except Exception:
        pass

invoices = []
for r in rows:
    if int(r.get("update_stock") or 0) == 1:
        continue
    inv_items = items_by_parent.get(r.name, [])
    has_drug = False
    all_drug = bool(inv_items)
    has_consult = False
    item_labels = []
    for it in inv_items:
        ic = str(it.get("item_code") or "").strip()
        im = item_meta_map.get(ic) or {}
        ig = str(it.get("item_group") or im.get("item_group") or "").strip().lower()
        is_stock = int(im.get("is_stock_item") or it.get("is_stock_item") or 0)
        has_batch = bool(str(it.get("batch_no") or "").strip())
        rdt = str(it.get("reference_dt") or "").strip()
        disp_name = str(it.get("item_name") or im.get("item_name") or ic or "").strip()
        row_txt = (" ".join([ic, disp_name, str(it.get("description") or ""), ig])).lower()

        is_drug_row = (
            rdt == "Drug Prescription"
            or has_batch
            or is_stock == 1
            or (bool(ic) and ic in drug_codes)
            or ("drug" in ig)
            or ("medic" in ig)
            or ("pharm" in ig)
            or ("consult" not in row_txt and ("drug" in row_txt or "medic" in row_txt or "pharm" in row_txt or "tablet" in row_txt or "capsule" in row_txt or "syrup" in row_txt))
        )
        is_consult_row = (not is_drug_row) and (
            ("consult" in row_txt)
            or ("opd" in row_txt)
            or ("fee" in row_txt)
            or ("doctor" in row_txt)
        )
        if is_drug_row:
            has_drug = True
        else:
            all_drug = False
            if disp_name and disp_name not in item_labels:
                item_labels.append(disp_name)
        if is_consult_row:
            has_consult = True

    has_wh = bool(str(r.get("set_warehouse") or "").strip())
    if all_drug:
        continue
    if (has_drug or has_wh) and not has_consult:
        continue

    pt_id = str(r.get("patient") or "").strip()
    p_obj = pat_map.get(pt_id) or {}
    disp_cust = (
        str(r.get("patient_name") or "").strip()
        or str(p_obj.get("patient_name") or "").strip()
        or str(r.get("customer_name") or "").strip()
        or str(r.get("customer") or "").strip()
    )
    pr_id = str(r.get("ref_practitioner") or r.get("practitioner") or "").strip()
    pr_name = prac_map.get(pr_id, "")
    if not pr_name and r.get("remarks"):
        for rpart in str(r.get("remarks") or "").split(" | "):
            rs = rpart.strip()
            if rs.startswith("Doctor: "):
                pr_name = rs[len("Doctor: "):].strip()
                break

    raw_tot = r.get("rounded_total") if r.get("rounded_total") not in (None, 0) else r.get("grand_total")
    tot = abs(float(raw_tot or 0))
    invoices.append({
        "name": r.name,
        "customer": disp_cust,
        "patient": pt_id,
        "mobile": str(p_obj.get("mobile") or ""),
        "practitioner_name": pr_name,
        "items_summary": ", ".join(item_labels[:4]) + ("…" if len(item_labels) > 4 else ""),
        "total": round(tot, 2),
        "outstanding": round(float(r.get("outstanding_amount") or 0), 2),
        "time": str(r.get("posting_time") or "")[:5],
        "docstatus": int(r.get("docstatus") or 0),
        "is_return": int(r.get("is_return") or 0),
        "return_against": r.get("return_against") or "",
    })

frappe.response["message"] = {
    "invoices": invoices,
    "today": today_str,
    "is_admin": is_admin,
}
