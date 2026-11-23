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
})();
