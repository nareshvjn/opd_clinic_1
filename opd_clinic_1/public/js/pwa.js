(function() {
  function ensureTag(rel, href, extra) {
    try {
      var sel = 'link[rel="' + rel + '"]';
      if (extra && extra.sizes) sel += '[sizes="' + extra.sizes + '"]';
      var el = document.querySelector(sel);
      if (!el) {
        el = document.createElement('link');
        el.rel = rel;
        if (extra) {
          for (var k in extra) {
            el.setAttribute(k, extra[k]);
          }
        }
        document.head.appendChild(el);
      }
      el.href = href;
    } catch(e) {}
  }

  function setMeta(name, content) {
    try {
      var el = document.querySelector('meta[name="' + name + '"]');
      if (!el) {
        el = document.createElement('meta');
        el.name = name;
        document.head.appendChild(el);
      }
      el.content = content;
    } catch(e) {}
  }

  // Inject PWA Manifest & App Icons
  ensureTag('manifest', '/assets/opd_clinic_1/manifest.json');
  ensureTag('apple-touch-icon', '/files/logo.png');
  ensureTag('icon', '/files/logo.png', { type: 'image/png' });
  ensureTag('shortcut icon', '/files/logo.png', { type: 'image/png' });

  // Web App Meta Tags
  setMeta('theme-color', '#125c3a');
  setMeta('mobile-web-app-capable', 'yes');
  setMeta('apple-mobile-web-app-capable', 'yes');
  setMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
  setMeta('apple-mobile-web-app-title', 'Jeevan Health');

  // Global clinicLogout handler
  window.clinicLogout = function(e) {
    if (e && e.preventDefault) e.preventDefault();
    try {
      if (window.frappe && frappe.app && typeof frappe.app.logout === 'function') {
        frappe.app.logout();
        return;
      }
    } catch(err) {}

    var token = (window.frappe && frappe.csrf_token) || window.csrf_token || '';
    if (!token) {
      var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
      if (match) token = decodeURIComponent(match[1]);
    }

    fetch('/api/method/logout', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'X-Frappe-CSRF-Token': token
      }
    }).finally(function() {
      window.location.href = '/login';
    });
  };

  // Check if user is logged in
  function isUserLoggedIn() {
    try {
      if (window.frappe && frappe.session_user && frappe.session_user !== 'Guest') return true;
      if (window.frappe && frappe.session && frappe.session.user && frappe.session.user !== 'Guest') return true;
      var match = document.cookie.match(/(?:^|;\s*)user_id=([^;]*)/);
      if (match) {
        var u = decodeURIComponent(match[1]);
        if (u && u !== 'Guest') return true;
      }
    } catch(e) {}
    return false;
  }

  // Ensure Logout button exists on all pages when logged in
  function ensureLogoutBtn() {
    if (!isUserLoggedIn()) return;
    if (window.location.pathname === '/login') return;

    if (document.querySelector('a[onclick*="clinicLogout"], button[onclick*="clinicLogout"], a[href*="logout"], a#btn-logout:not([hidden])')) {
      return;
    }

    var btn = document.getElementById('clinic-float-logout');
    if (!btn && document.body) {
      btn = document.createElement('a');
      btn.id = 'clinic-float-logout';
      btn.href = 'javascript:void(0)';
      btn.onclick = window.clinicLogout;
      btn.innerHTML = '&#128682; Logout';
      btn.setAttribute('style', 'position:fixed;top:10px;right:12px;z-index:99999;background:rgba(220,53,69,0.92);color:#fff;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,0.2);display:inline-flex;align-items:center;gap:4px;backdrop-filter:blur(4px);border:1px solid rgba(255,255,255,0.4);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;');
      document.body.appendChild(btn);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureLogoutBtn);
  } else {
    ensureLogoutBtn();
  }
  setTimeout(ensureLogoutBtn, 600);
})();
