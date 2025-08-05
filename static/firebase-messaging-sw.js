// Import Firebase scripts for service worker
importScripts('https://www.gstatic.com/firebasejs/9.19.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.19.1/firebase-messaging-compat.js');

// Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyBYyFqKrVvqNKqN5t8qg8k8jKlJkMnOpqw",
    authDomain: "foto-video-mojica.firebaseapp.com",
    projectId: "foto-video-mojica",
    storageBucket: "foto-video-mojica.firebasestorage.app",
    messagingSenderId: "586490455948",
    appId: "1:586490455948:web:d316d77a683186ce3dd8a9",
    measurementId: "G-GK7CD8H7EB"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// Retrieve firebase messaging
const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage(function(payload) {
    console.log('[firebase-messaging-sw.js] Received background message ', payload);
    
    const notificationTitle = payload.notification?.title || 'FOTO VIDEO MOJICA';
    const notificationOptions = {
        body: payload.notification?.body || payload.data?.message,
        icon: '/static/icons/logo-192x192.png',
        badge: '/static/icons/logo-192x192.png',
        tag: payload.data?.type || 'foto-video-mojica',
        requireInteraction: true,
        actions: [
            {
                action: 'open',
                title: 'Ver'
            },
            {
                action: 'close',
                title: 'Cerrar'
            }
        ]
    };

    return self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click
self.addEventListener('notificationclick', function(event) {
    console.log('[firebase-messaging-sw.js] Notification click received.');

    event.notification.close();

    if (event.action === 'open') {
        // Open the app
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});