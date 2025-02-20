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