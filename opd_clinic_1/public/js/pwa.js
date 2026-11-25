(function() {
  if (window._clinicPwaLoaded) return;
  window._clinicPwaLoaded = true;

  function ensureTag(rel, href, extra) {
    try {
      var sel = 'link[rel="' + rel + '"]';
      if (extra && extra.sizes) sel += '[sizes="' + extra.sizes + '"]';
      var el = document.querySelector(sel);
      if (!el) {
        el = document.createElement('link');
        el.rel = rel;
        if (extra) {
          for (var k in extra) el.setAttribute(k, extra[k]);
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

  // Inject PWA Manifest & App Icons (served reliably from /files/)
  ensureTag('manifest', '/files/manifest.json?v=2');
  ensureTag('apple-touch-icon', '/files/icon-192.png', { sizes: '192x192' });
  ensureTag('icon', '/files/icon-192.png', { type: 'image/png', sizes: '192x192' });
  ensureTag('icon', '/files/icon-512.png', { type: 'image/png', sizes: '512x512' });
  ensureTag('shortcut icon', '/files/icon-192.png', { type: 'image/png' });

  // Web App Meta Tags
  setMeta('theme-color', '#125c3a');
  setMeta('mobile-web-app-capable', 'yes');
  setMeta('apple-mobile-web-app-capable', 'yes');
  setMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
  setMeta('apple-mobile-web-app-title', 'Jeevan Health');

  // Register Service Worker at root scope (required by Samsung Internet & Android WebAPK)
  if ('serviceWorker' in navigator && (window.isSecureContext || location.hostname === 'localhost')) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function() {});
  }

  function isStandaloneMode() {
    try {
      return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || window.navigator.standalone === true;
    } catch (e) { return false; }
  }

  window._clinicInstallPrompt = null;
  window.addEventListener('beforeinstallprompt', function(e) {
    e.preventDefault();
    window._clinicInstallPrompt = e;
    document.querySelectorAll('.clinic-profile-slot').forEach(function(s) {
      s.removeAttribute('data-clinic-profile-user');
    });
    if (typeof ensureUserProfile === 'function') ensureUserProfile();
  });
  window.addEventListener('appinstalled', function() {
    window._clinicInstallPrompt = null;
    document.querySelectorAll('.clinic-profile-slot').forEach(function(s) {
      s.removeAttribute('data-clinic-profile-user');
    });
    if (typeof ensureUserProfile === 'function') ensureUserProfile();
  });

  window.clinicInstallApp = function(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (e && e.stopPropagation) e.stopPropagation();
    var p = window._clinicInstallPrompt;
    if (!p) return;
    p.prompt();
    p.userChoice.then(function() {
      window._clinicInstallPrompt = null;
      document.querySelectorAll('.clinic-profile-slot').forEach(function(s) {
        s.removeAttribute('data-clinic-profile-user');
      });
      var pop = document.getElementById('clinic-ham-dropdown-menu');
      if (pop) pop.remove();
      if (typeof ensureUserProfile === 'function') ensureUserProfile();
    }).catch(function() {});
  };

  // Helper: Cookie Reader
  function getCookie(name) {
    try {
      var match = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'));
      return match ? decodeURIComponent(match[1]) : null;
    } catch(e) { return null; }
  }

  // Global clinicLogout handler
  window.clinicLogout = function(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (e && e.stopPropagation) e.stopPropagation();

    try {
      sessionStorage.removeItem('clinic_user_profile');
    } catch(err) {}

    try {
      if (window.frappe && frappe.app && typeof frappe.app.logout === 'function') {
        frappe.app.logout();
        return;
      }
    } catch(err) {}

    var token = (window.frappe && frappe.csrf_token) || window.csrf_token || getCookie('csrf_token') || '';

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

  // Inject Profile Styles
  function ensureProfileStyles() {
    if (document.getElementById('clinic-profile-styles')) return;
    var style = document.createElement('style');
    style.id = 'clinic-profile-styles';
    style.textContent = '' +
      '.clinic-profile-slot{position:relative;display:inline-flex;align-items:center;vertical-align:middle;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}' +
      '.clinic-profile-slot *{box-sizing:border-box}' +
      '#clinic-floating-profile{position:fixed;top:10px;right:12px;z-index:99990}' +
      '#clinic-floating-profile .clinic-profile-btn{background:rgba(13,61,39,0.92);border-color:rgba(255,255,255,0.45);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);box-shadow:0 4px 14px rgba(0,0,0,0.22)}' +
      '.clinic-profile-btn{display:inline-flex;align-items:center;gap:7px;background:rgba(255,255,255,0.18);border:1.5px solid rgba(255,255,255,0.45);padding:3px 10px 3px 4px;border-radius:999px;cursor:pointer;color:#ffffff!important;font-size:13px;font-weight:700;line-height:1;transition:all .15s ease;text-decoration:none!important;box-shadow:0 2px 6px rgba(0,0,0,0.1);user-select:none}' +
      '.clinic-profile-btn:hover{background:rgba(255,255,255,0.28);border-color:#ffffff;transform:translateY(-1px)}' +
      '.clinic-avatar{width:28px;height:28px;border-radius:50%;object-fit:cover;background:linear-gradient(135deg,#f1c40f 0%,#d4ac0d 100%);color:#2b1d00;display:inline-flex;align-items:center;justify-content:center;font-size:13px;font-weight:900;border:1.5px solid #ffffff;box-shadow:0 1px 3px rgba(0,0,0,0.2);flex-shrink:0}' +
      '.clinic-uname{max-width:130px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2}' +
      '.clinic-chevron{width:12px;height:12px;transition:transform .18s ease;opacity:0.9;flex-shrink:0}' +
      '.clinic-profile-slot.open .clinic-chevron{transform:rotate(180deg)}' +
      '.clinic-profile-dropdown{display:none;position:absolute;top:calc(100% + 8px);right:0;width:270px;background:#ffffff;border:1.5px solid #cfe0d7;border-radius:14px;box-shadow:0 14px 40px rgba(18,92,58,0.2),0 2px 10px rgba(0,0,0,0.08);padding:8px;z-index:999999;text-align:left;animation:clinicDropIn .16s ease-out;color:#11281e}' +
      '.clinic-profile-slot.open .clinic-profile-dropdown{display:block}' +
      '@keyframes clinicDropIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:translateY(0)}}' +
      '.clinic-menu-header{padding:10px 12px 10px;border-bottom:1px solid #eef3f0;display:flex;align-items:center;gap:10px}' +
      '.clinic-menu-avatar-lg{width:40px;height:40px;border-radius:50%;object-fit:cover;background:linear-gradient(135deg,#125c3a 0%,#0d3d27 100%);color:#ffffff;display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:800;flex-shrink:0;border:2px solid #e2ece6}' +
      '.clinic-menu-info{flex:1;min-width:0}' +
      '.clinic-menu-name{font-size:14px;font-weight:800;color:#11281e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:0;line-height:1.25}' +
      '.clinic-menu-email{font-size:11.5px;color:#546a5f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:2px 0 0;line-height:1.2}' +
      '.clinic-menu-badge{display:inline-block;background:#eef7f2;color:#125c3a;border:1px solid #cfe0d7;font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:10px;margin-top:4px}' +
      '.clinic-menu-links{padding:6px 0;margin:0}' +
      '.clinic-menu-item{display:flex;align-items:center;gap:9px;padding:8px 12px;color:#11281e!important;text-decoration:none!important;font-size:13px;font-weight:600;border-radius:8px;transition:all .12s ease;cursor:pointer;border:none;background:none;width:100%;box-sizing:border-box;text-align:left;line-height:1.4}' +
      '.clinic-menu-item:hover{background:#f4f9f6;color:#125c3a!important}' +
      '.clinic-menu-divider{height:1px;background:#eef3f0;margin:4px 0}' +
      '.clinic-menu-item.danger{color:#c0392b!important;font-weight:700}' +
      '.clinic-menu-item.danger:hover{background:#fdf0ef;color:#962d22!important}' +
      '/* Hamburger menu button transformation */' +
      '.navbar-toggler.clinic-ham-btn, .navbar-toggle.clinic-ham-btn, button[data-toggle="collapse"].clinic-ham-btn, button[data-bs-toggle="collapse"].clinic-ham-btn {' +
      '  border: none !important;' +
      '  outline: none !important;' +
      '  box-shadow: none !important;' +
      '  background: transparent !important;' +
      '  padding: 0 !important;' +
      '  margin: 0 !important;' +
      '  width: 38px !important;' +
      '  height: 38px !important;' +
      '  display: inline-flex !important;' +
      '  align-items: center !important;' +
      '  justify-content: center !important;' +
      '  cursor: pointer !important;' +
      '}' +
      '/* Hide standard 3-line hamburger children */' +
      '.clinic-ham-btn > *:not(.clinic-ham-avatar-wrap), .clinic-ham-btn .navbar-toggler-icon, .clinic-ham-btn svg:not(.clinic-chevron), .clinic-ham-btn .menu-icon, .clinic-ham-btn .icon-bar {' +
      '  display: none !important;' +
      '}' +
      '.clinic-ham-avatar-wrap {' +
      '  width: 36px !important;' +
      '  height: 36px !important;' +
      '  border-radius: 50% !important;' +
      '  display: inline-flex !important;' +
      '  align-items: center !important;' +
      '  justify-content: center !important;' +
      '  transition: transform .15s ease !important;' +
      '  position: relative !important;' +
      '  overflow: hidden !important;' +
      '  box-sizing: border-box !important;' +
      '}' +
      '.clinic-ham-btn:hover .clinic-ham-avatar-wrap, .clinic-ham-btn:active .clinic-ham-avatar-wrap {' +
      '  transform: scale(1.08) !important;' +
      '}' +
      '.clinic-ham-avatar {' +
      '  width: 36px !important;' +
      '  height: 36px !important;' +
      '  border-radius: 50% !important;' +
      '  object-fit: cover !important;' +
      '  border: 2px solid #125c3a !important;' +
      '  box-shadow: 0 2px 8px rgba(18, 92, 58, 0.28) !important;' +
      '  display: block !important;' +
      '  box-sizing: border-box !important;' +
      '}' +
      '.clinic-ham-initial {' +
      '  width: 36px !important;' +
      '  height: 36px !important;' +
      '  border-radius: 50% !important;' +
      '  background: linear-gradient(135deg, #125c3a 0%, #0d3d27 100%) !important;' +
      '  color: #f1c40f !important;' +
      '  display: inline-flex !important;' +
      '  align-items: center !important;' +
      '  justify-content: center !important;' +
      '  font-size: 16px !important;' +
      '  font-weight: 800 !important;' +
      '  border: 2px solid #f1c40f !important;' +
      '  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2) !important;' +
      '  line-height: 1 !important;' +
      '  box-sizing: border-box !important;' +
      '}' +
      '@media(max-width:991px){' +
      '  #clinic-floating-profile{display:none!important}' +
      '}' +
      '@media(max-width:480px){' +
      '  .clinic-profile-btn .clinic-uname{display:none}' +
      '  .clinic-profile-dropdown{right:0;max-width:calc(100vw - 24px)}' +
      '}';
    document.head.appendChild(style);
  }

  // Build Profile Menu HTML
  function buildDropdownHTML(profile) {
    var userId = profile.user || '';
    var email = profile.email || userId;
    var name = profile.full_name || email.split('@')[0];
    var initial = (name ? name.charAt(0) : 'U').toUpperCase();
    var avatarLg = profile.user_image ? ('<img class="clinic-menu-avatar-lg" src="' + profile.user_image + '" alt="' + name + '">') : ('<span class="clinic-menu-avatar-lg">' + initial + '</span>');
    var badgeText = profile.practitioner || (profile.can_dashboard ? 'Clinic Staff' : 'User');

    return '' +
      '<div class="clinic-menu-header">' +
        avatarLg +
        '<div class="clinic-menu-info">' +
          '<div class="clinic-menu-name" title="' + name + '">' + name + '</div>' +
          '<div class="clinic-menu-email" title="' + email + '">' + email + '</div>' +
          '<div class="clinic-menu-badge">' + badgeText + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="clinic-menu-links">' +
        '<a href="/home" class="clinic-menu-item"><span>🏠</span> Clinic Home</a>' +
        (profile.can_dashboard !== false ? '<a href="/dashboard" class="clinic-menu-item"><span>📊</span> Dashboard</a>' : '') +
        '<a href="/registration" class="clinic-menu-item"><span>🏥</span> Registration</a>' +
        '<a href="/doctor-desk" class="clinic-menu-item"><span>🩺</span> Doctor Desk</a>' +
        '<a href="/pharmacy-home" class="clinic-menu-item"><span>💊</span> Pharmacy</a>' +
        '<a href="/app" class="clinic-menu-item"><span>⚙️</span> ERPNext Desk</a>' +
        ((window._clinicInstallPrompt && !isStandaloneMode()) ? '<button type="button" class="clinic-menu-item" onclick="window.clinicInstallApp(event)"><span>📲</span> Install App</button>' : '') +
        '<div class="clinic-menu-divider"></div>' +
        '<button type="button" class="clinic-menu-item danger" onclick="window.clinicLogout(event)"><span>🚪</span> Logout</button>' +
      '</div>';
  }

  // Build Profile Slot HTML
  function renderProfileSlot(slotEl, profile) {
    var appliedUser = slotEl.getAttribute('data-clinic-profile-user');
    if (appliedUser === profile.user) return;
    slotEl.setAttribute('data-clinic-profile-user', profile.user);

    var userId = profile.user || '';
    var email = profile.email || userId;
    var name = profile.full_name || email.split('@')[0];
    var initial = (name ? name.charAt(0) : 'U').toUpperCase();
    var avatarImg = profile.user_image ? ('<img class="clinic-avatar" src="' + profile.user_image + '" alt="' + name + '">') : ('<span class="clinic-avatar">' + initial + '</span>');

    slotEl.innerHTML = '' +
      '<button type="button" class="clinic-profile-btn" aria-label="User Profile">' +
        avatarImg +
        '<span class="clinic-uname">' + name + '</span>' +
        '<svg class="clinic-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>' +
      '</button>' +
      '<div class="clinic-profile-dropdown">' +
        buildDropdownHTML(profile) +
      '</div>';

    var btn = slotEl.querySelector('.clinic-profile-btn');
    if (btn) {
      btn.onclick = function(e) {
        e.stopPropagation();
        var wasOpen = slotEl.classList.contains('open');
        document.querySelectorAll('.clinic-profile-slot.open').forEach(function(s) { s.classList.remove('open'); });
        var hamPop = document.getElementById('clinic-ham-dropdown-menu');
        if (hamPop) hamPop.remove();
        if (!wasOpen) slotEl.classList.add('open');
      };
    }
  }

  // Update Hamburger Menu in navbar to show user profile pic
  function updateHamburgerProfile(profile) {
    var togglers = document.querySelectorAll('.navbar-toggler, button[data-toggle="collapse"], button[data-bs-toggle="collapse"], .navbar-toggle, .btn-navbar-toggle');
    if (!togglers.length) return;

    var userId = profile.user || '';
    var email = profile.email || userId;
    var name = profile.full_name || email.split('@')[0];
    var initial = (name ? name.charAt(0) : 'U').toUpperCase();

    for (var i = 0; i < togglers.length; i++) {
      var toggler = togglers[i];
      if (toggler.getAttribute('data-clinic-ham-applied') === userId) continue;
      toggler.setAttribute('data-clinic-ham-applied', userId);

      toggler.classList.add('clinic-ham-btn');
      toggler.setAttribute('title', name + ' (' + email + ')');

      var wrap = toggler.querySelector('.clinic-ham-avatar-wrap');
      if (!wrap) {
        wrap = document.createElement('span');
        wrap.className = 'clinic-ham-avatar-wrap';
        toggler.appendChild(wrap);
      }

      if (profile.user_image) {
        wrap.innerHTML = '<img class="clinic-ham-avatar" src="' + profile.user_image + '" alt="' + name + '" onerror="this.outerHTML=\'<span class=\\\'clinic-ham-avatar clinic-ham-initial\\\'>' + initial + '</span>\'">';
      } else {
        wrap.innerHTML = '<span class="clinic-ham-avatar clinic-ham-initial">' + initial + '</span>';
      }

      if (!toggler.getAttribute('data-clinic-ham-listener')) {
        toggler.setAttribute('data-clinic-ham-listener', 'true');

        toggler.onclick = function(e) {
          e.preventDefault();
          e.stopPropagation();

          var pop = document.getElementById('clinic-ham-dropdown-menu');
          if (pop && pop.getAttribute('data-open') === 'true') {
            pop.remove();
            return;
          }

          if (pop) pop.remove();
          document.querySelectorAll('.clinic-profile-slot.open').forEach(function(s) { s.classList.remove('open'); });

          pop = document.createElement('div');
          pop.id = 'clinic-ham-dropdown-menu';
          pop.className = 'clinic-profile-dropdown';
          pop.setAttribute('data-open', 'true');
          pop.style.display = 'block';
          pop.innerHTML = buildDropdownHTML(profile);

          var rect = this.getBoundingClientRect();
          pop.style.position = 'fixed';
          pop.style.top = (rect.bottom + 8) + 'px';
          pop.style.right = Math.max(10, window.innerWidth - rect.right) + 'px';
          pop.style.zIndex = '999999';

          document.body.appendChild(pop);
        };
      }
    }
  }

  // Setup Global Outside-Click & Escape Listeners (Attached Once)
  if (!window._clinicProfileListenersAttached) {
    window._clinicProfileListenersAttached = true;
    document.addEventListener('click', function(e) {
      var openSlots = document.querySelectorAll('.clinic-profile-slot.open');
      for (var i = 0; i < openSlots.length; i++) {
        if (!openSlots[i].contains(e.target)) openSlots[i].classList.remove('open');
      }
      var pop = document.getElementById('clinic-ham-dropdown-menu');
      if (pop && !pop.contains(e.target) && !e.target.closest('.clinic-ham-btn')) {
        pop.remove();
      }
    });
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' || e.keyCode === 27) {
        document.querySelectorAll('.clinic-profile-slot.open').forEach(function(s) { s.classList.remove('open'); });
        var pop = document.getElementById('clinic-ham-dropdown-menu');
        if (pop) pop.remove();
      }
    });
  }

  // Apply profile to UI
  function applyProfile(profile) {
    if (!profile || !profile.logged_in) return;

    // 1. Transform Hamburger Menu in navbar
    updateHamburgerProfile(profile);

    // 2. Custom header slot or floating slot
    var slot = document.getElementById('clinic-user-profile');
    if (slot) {
      var fl = document.getElementById('clinic-floating-profile');
      if (fl) fl.remove();
      renderProfileSlot(slot, profile);
    } else {
      var hasNavbarToggler = document.querySelector('.navbar-toggler, .navbar-toggle');
      if (!hasNavbarToggler) {
        var fl = document.getElementById('clinic-floating-profile');
        if (!fl && document.body) {
          fl = document.createElement('div');
          fl.id = 'clinic-floating-profile';
          fl.className = 'clinic-profile-slot';
          document.body.appendChild(fl);
        }
        if (fl) renderProfileSlot(fl, profile);
      }
    }

    var oldLogout = document.getElementById('clinic-float-logout');
    if (oldLogout) oldLogout.remove();
  }

  // Remove profile UI for guest
  function removeProfile() {
    var fl = document.getElementById('clinic-floating-profile');
    if (fl) fl.remove();
    var pop = document.getElementById('clinic-ham-dropdown-menu');
    if (pop) pop.remove();
  }

  // Mount or Update Profile
  function ensureUserProfile() {
    if (window.location.pathname === '/login') return;

    ensureProfileStyles();

    // 1. Check cached profile in sessionStorage (instant synchronous execution)
    var cached = null;
    try {
      var s = sessionStorage.getItem('clinic_user_profile');
      if (s) cached = JSON.parse(s);
    } catch(e) {}

    if (cached && cached.logged_in) {
      applyProfile(cached);
    }

    // 2. Fetch fresh profile from API in background
    if (!window._clinicProfileFetching) {
      window._clinicProfileFetching = true;
      fetch('/api/method/user_profile', {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
      })
      .then(function(res) { return res.json(); })
      .then(function(r) {
        if (r && r.message) {
          if (r.message.logged_in) {
            try { sessionStorage.setItem('clinic_user_profile', JSON.stringify(r.message)); } catch(e) {}
            applyProfile(r.message);
          } else {
            try { sessionStorage.removeItem('clinic_user_profile'); } catch(e) {}
            removeProfile();
          }
        }
      })
      .catch(function() {})
      .finally(function() {
        window._clinicProfileFetching = false;
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureUserProfile);
  } else {
    ensureUserProfile();
  }
  setTimeout(ensureUserProfile, 300);
})();
