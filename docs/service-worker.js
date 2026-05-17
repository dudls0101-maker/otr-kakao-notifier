// 매우 가벼운 service worker. 정적 자원은 네트워크 우선, 실패 시 캐시.
// auditions.json 은 항상 네트워크에서 가져옴.

const CACHE_NAME = 'musical-audition-board-v1';
const STATIC_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon-180.png',
  './icon-192.png',
  './icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // auditions.json 은 절대 캐시 사용 X — 항상 fresh
  if (url.pathname.endsWith('/auditions.json')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // 정적 자원: 네트워크 우선, 실패 시 캐시 폴백
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        // 응답 캐시 갱신
        const cloned = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
        return res;
      })
      .catch(() => caches.match(event.request))
  );
});
