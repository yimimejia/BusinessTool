const CACHE_NAME = 'fv-mojica-v1';
const urlsToCache = [
  '/',
  '/static/styles.css',
  '/static/js/notifications.js',
  '/static/notification.mp3',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/manifest.json'
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
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request).then(response => {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
          return response;
        });
      })
  );
});

self.addEventListener('push', event => {
  const options = {
    body: event.data.text(),
    icon: '/static/icons/notification-icon.png',
    badge: '/static/icons/badge-icon.png',
    sound: '/static/notification.mp3',
    vibrate: [200, 100, 200]
  };

  event.waitUntil(
    self.registration.showNotification('Foto Video Mojica', options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow('/')
  );
});
