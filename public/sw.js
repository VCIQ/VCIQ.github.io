const CACHE_PREFIX = "vciq-pwa-";
const CACHE_NAME = `${CACHE_PREFIX}v1`;
const APP_SHELL = ["/", "/favicon.svg", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(request, fallbackToHome = false) {
  const cache = await caches.open(CACHE_NAME);

  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (fallbackToHome) {
      const home = await cache.match("/");
      if (home) return home;
    }
    return Response.error();
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response.ok) await cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, true));
    return;
  }

  if (url.pathname.startsWith("/data/") || url.pathname.endsWith(".json")) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (/\.(?:css|js|mjs|svg|png|jpe?g|webp|woff2?)$/i.test(url.pathname)) {
    event.respondWith(cacheFirst(request));
  }
});
