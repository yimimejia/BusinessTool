const CACHE_NAME = 'fv-mojica-v1';
const urlsToCache = [
  '/',
  '/static/styles.css',
  '/static/js/notifications.js',
  '/static/notification.mp3'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
