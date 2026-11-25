import frappe


def redirect_guest_clinic():
    """Redirect unauthenticated visitors of /clinic directly to /login before rendering."""
    try:
        req = getattr(frappe.local, "request", None)
        if not req:
            return
        path = (req.path or "").rstrip("/")
        if path == "/clinic":
            user = getattr(frappe.session, "user", None)
            if not user or user == "Guest":
                frappe.local.flags.redirect_location = "/login?redirect-to=/clinic"
                raise frappe.Redirect
    except frappe.Redirect:
        raise
    except Exception:
        pass
