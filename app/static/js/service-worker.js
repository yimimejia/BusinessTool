const CACHE_NAME = 'fv-mojica-v1';
const urlsToCache = [
  '/',
  '/static/styles.css',
  '/static/js/notifications.js',
  '/static/notification.mp3',
  '/static/icons/camera-72x72.png',
  '/static/icons/camera-96x96.png',
  '/static/icons/camera-128x128.png',
  '/static/icons/camera-144x144.png',
  '/static/icons/camera-152x152.png',
  '/static/icons/camera-192x192.png',
  '/static/icons/camera-384x384.png',
  '/static/icons/camera-512x512.png',
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
    icon: '/static/icons/camera-192x192.png',
    badge: '/static/icons/camera-72x72.png',
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