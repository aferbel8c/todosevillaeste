const CACHE_NAME = "tse-frontend-v10";
const CORE_ASSETS = [
  "/frontend.html",
  "/ui_public.css",
  "/ui_public.js",
  "/icono/tsev2.png",
  "/icono/qr.png",
  "/icono/perfil_iniciar.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  const path = url.pathname || "";
  const isSameOrigin = url.origin === self.location.origin;

  if (!isSameOrigin) {
    event.respondWith(
      fetch(req).catch(() => new Response(null, { status: 204 }))
    );
    return;
  }
  const isApiPath = (
    path.startsWith("/auth/") ||
    path.startsWith("/users/me") ||
    path.startsWith("/business/me") ||
    path.startsWith("/messages/") ||
    path.startsWith("/support/") ||
    path.startsWith("/public/visibility") ||
    path.startsWith("/web/versions/public")
  );
  const isCodeAsset = (
    path.endsWith(".html") ||
    path.endsWith(".js") ||
    path.endsWith(".css") ||
    path.endsWith(".webmanifest")
  );

  if (path === "/") {
    event.respondWith(Response.redirect("/frontend.html", 302));
    return;
  }

  if (isApiPath) {
    event.respondWith(fetch(req));
    return;
  }

  if ((req.mode === "navigate") || (isSameOrigin && isCodeAsset)) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone)).catch(() => {});
          return res;
        })
        .catch(() =>
          caches.match(req).then((cached) => cached || caches.match("/frontend.html").then((fallback) => fallback || new Response(null, { status: 204 })))
        )
    );
    return;
  }

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone)).catch(() => {});
          return res;
        })
        .catch(() => caches.match("/frontend.html").then((fallback) => fallback || new Response(null, { status: 204 })));
    })
  );
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data && data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification && event.notification.data && event.notification.data.url) || "/frontend.html";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url && "focus" in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
      return undefined;
    })
  );
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_e) {
    payload = {};
  }
  const title = payload.title || "Nuevo mensaje";
  const body = payload.body || "Tienes un mensaje nuevo.";
  const url = payload.url || "/frontend.html";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/icono/tsev2.png",
      badge: "/icono/tsev2.png",
      tag: `push-${Date.now()}`,
      renotify: false,
      data: { url },
    })
  );
});
