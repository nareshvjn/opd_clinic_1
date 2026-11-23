# Server Script: appt_search
# type: API
# doctype: -
# event: Before Insert
# api_method: appt_search
# allow_guest: 1
# frequency: All
# disabled: 0

is_guest = (frappe.session.user == "Guest")

if is_guest:
    # Privacy protection for public guest sessions:
    # Fuzzy search is completely DISABLED. Requires 2 exact matching fields:
    # 1. Patient ID (UID) or Full Name
    # 2. Registered Mobile Number
    ident = (frappe.form_dict.get("identifier") or frappe.form_dict.get("uid") or frappe.form_dict.get("name") or "").strip()
    raw_mobile = (frappe.form_dict.get("mobile") or "").strip()

    if not ident or not raw_mobile:
        frappe.throw("To protect patient privacy, please enter both your Patient ID (or Full Name) AND your registered mobile number.")

    clean_digits = "".join([c for c in raw_mobile if c.isdigit()])
    if len(clean_digits) != 10:
        frappe.throw("Please enter a valid 10-digit mobile number.")
    phone_match = clean_digits

    # Exact 2-field match SQL query (no fuzzy % wildcards across all patients)
    rows = frappe.db.sql("""
        select name, patient_name, mobile, dob, uid, status
        from `tabPatient`
        where (status is null or status = '' or status != 'Disabled')
          and (
              lower(trim(ifnull(uid, ''))) = lower(%(ident)s)
              or lower(trim(name)) = lower(%(ident)s)
              or lower(trim(patient_name)) = lower(%(ident)s)
          )
          and (
              replace(replace(replace(ifnull(mobile, ''), ' ', ''), '-', ''), '+', '') like concat('%%', %(phone_match)s)
          )
        limit 2
    """, {"ident": ident, "phone_match": phone_match}, as_dict=True)

    today = frappe.utils.getdate(frappe.utils.today())
    out = []
    for r in rows:
        age = None
        if r.get("dob"):
            try:
                d = frappe.utils.getdate(r.get("dob"))
                age = today.year - d.year - (1 if (today.month, today.day) < (d.month, d.day) else 0)
            except:
                age = None
        # Mask mobile number in response for privacy
        m = (r.get("mobile") or "").strip()
        if len(m) > 4:
            m_masked = "******" + m[-4:]
        else:
            m_masked = m
        out.append({
            "id": r.get("name"),
            "uid": r.get("uid") or "",
            "name": r.get("patient_name") or r.get("name"),
            "age": age,
            "mobile": m_masked
        })
    frappe.response["message"] = {"patients": out}

else:
    # Staff / Logged-in clinic users: fast live search across name, mobile or ID
    q = (frappe.form_dict.get("query") or frappe.form_dict.get("q") or frappe.form_dict.get("identifier") or "").strip()
    if not q:
        q = (frappe.form_dict.get("name") or frappe.form_dict.get("mobile") or "").strip()

    if len(q) < 2:
        frappe.throw("Enter at least 2 characters to search by name, mobile, or ID.")

    q_wild = "%" + q + "%"
    rows = frappe.db.sql("""
        select name, patient_name, mobile, dob, uid, status
        from `tabPatient`
        where (status is null or status = '' or status != 'Disabled')
          and (
              patient_name like %(q_wild)s
              or mobile like %(q_wild)s
              or ifnull(uid, '') like %(q_wild)s
              or name like %(q_wild)s
          )
        order by patient_name asc
        limit 15
    """, {"q_wild": q_wild}, as_dict=True)

    today = frappe.utils.getdate(frappe.utils.today())
    out = []
    for r in rows:
        age = None
        if r.get("dob"):
            try:
                d = frappe.utils.getdate(r.get("dob"))
                age = today.year - d.year - (1 if (today.month, today.day) < (d.month, d.day) else 0)
            except:
                age = None
        m = r.get("mobile") or ""
        out.append({
            "id": r.get("name"),
            "uid": r.get("uid") or "",
            "name": r.get("patient_name") or r.get("name"),
            "age": age,
            "mobile": m
        })
    frappe.response["message"] = {"patients": out}
