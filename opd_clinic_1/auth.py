from urllib.parse import quote

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect


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
                qs = getattr(req, "query_string", b"")
                if isinstance(qs, bytes):
                    qs = qs.decode("utf-8", errors="ignore")
                target = "/clinic" + (f"?{qs}" if qs else "")
                resp = redirect(f"/login?redirect-to={quote(target, safe='/')}", code=302)
                resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                raise HTTPException(response=resp)
    except HTTPException:
        raise
    except Exception:
        pass
