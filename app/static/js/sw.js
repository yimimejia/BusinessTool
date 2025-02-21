
self.addEventListener('push', function(event) {
    const notification = event.data.json();
    
    event.waitUntil(
        self.registration.showNotification(notification.title, {
            body: notification.message,
            icon: '/static/img/logo.png',
            badge: '/static/img/badge.png',
            vibrate: [200, 100, 200]
        })
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
});
