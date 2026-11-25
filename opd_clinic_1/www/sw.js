// Minimal network-first Service Worker for Jeevan Healthcare PWA installability.
// Does not cache authenticated HTML or API responses to avoid stale CSRF or billing state.
self.addEventListener('install', function() {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function(event) {
  var req = event.request;
  if (req.method !== 'GET') return;

  var url;
  try {
    url = new URL(req.url);
  } catch (e) {
    return;
  }
  if (url.origin !== self.location.origin) return;

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(function() {
        return new Response(
          '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline - Jeevan Healthcare</title><style>body{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f4f9f6;color:#11281e;text-align:center;padding:24px}.box{max-width:360px;background:#fff;border:1.5px solid #cfe0d7;border-radius:14px;padding:28px 22px}h1{font-size:1.2rem;color:#125c3a;margin:0 0 8px}p{font-size:.95rem;color:#546a5f;margin:0 0 18px}button{background:#125c3a;color:#fff;border:0;border-radius:8px;padding:10px 20px;font:700 15px inherit;cursor:pointer}</style></head><body><div class="box"><h1>You are offline</h1><p>Check your internet connection and try again to open Jeevan Healthcare.</p><button onclick="location.reload()">Retry</button></div></body></html>',
          { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        );
      })
    );
  }
});
