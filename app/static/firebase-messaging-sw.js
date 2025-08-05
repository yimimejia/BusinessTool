// Give the service worker access to Firebase Messaging
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

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
  console.log('Received background message ', payload);
  
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/static/icons/logo-192x192.png',
    badge: '/static/icons/logo-192x192.png',
    tag: 'foto-video-mojica',
    data: payload.data
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click
self.addEventListener('notificationclick', function(event) {
  console.log('Notification click received.');
  
  event.notification.close();
  
  // Open the app
  event.waitUntil(
    clients.openWindow('/')
  );
});