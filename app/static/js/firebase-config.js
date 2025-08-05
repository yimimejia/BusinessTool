// Import the functions you need from the SDKs you need
import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

// Your web app's Firebase configuration
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
const app = initializeApp(firebaseConfig);

// Initialize Firebase Cloud Messaging and get a reference to the service
const messaging = getMessaging(app);

// Get registration token for this device
export async function requestNotificationPermission() {
  try {
    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
      console.log('Notification permission granted.');
      
      // Get the token
      const token = await getToken(messaging, {
        vapidKey: 'BLN9_vqrwJHq8kHtFJ9qL9Nq9qJGqG_qQ9qr1qr1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1q1'
      });
      
      if (token) {
        console.log('Registration token:', token);
        
        // Send token to server
        await fetch('/api/save-fcm-token', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ token: token })
        });
        
        return token;
      } else {
        console.log('No registration token available.');
      }
    } else {
      console.log('Unable to get permission to notify.');
    }
  } catch (err) {
    console.log('An error occurred while retrieving token. ', err);
  }
}

// Handle incoming messages when app is in foreground
onMessage(messaging, (payload) => {
  console.log('Message received. ', payload);
  
  // Show notification
  if (payload.notification) {
    showNotification(payload.notification.title, payload.notification.body);
  }
  
  // Show modal if it's a completion notification
  if (payload.data && payload.data.type === 'job_completed') {
    showCompletionModal(payload.data);
  }
});

function showNotification(title, body) {
  if ('serviceWorker' in navigator && 'PushManager' in window) {
    navigator.serviceWorker.ready.then(registration => {
      registration.showNotification(title, {
        body: body,
        icon: '/static/icons/logo-192x192.png',
        badge: '/static/icons/logo-192x192.png',
        tag: 'foto-video-mojica'
      });
    });
  }
}

function showCompletionModal(data) {
  // Create modal for job completion celebration
  const modal = document.createElement('div');
  modal.className = 'modal fade';
  modal.id = 'completionModal';
  modal.innerHTML = `
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content bg-success text-white">
        <div class="modal-header border-0">
          <h5 class="modal-title">¡Felicitaciones! 🎉</h5>
          <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body text-center">
          <h4>Tu trabajo ha sido verificado</h4>
          <p><strong>Cliente:</strong> ${data.client_name}</p>
          <p><strong>Descripción:</strong> ${data.description}</p>
          <p class="mt-3">¡Excelente trabajo! El trabajo ha pasado la verificación y ahora está en trabajos completados.</p>
        </div>
        <div class="modal-footer border-0 justify-content-center">
          <button type="button" class="btn btn-light" data-bs-dismiss="modal">¡Gracias!</button>
        </div>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  const bootstrapModal = new bootstrap.Modal(modal);
  bootstrapModal.show();
  
  // Remove modal after hiding
  modal.addEventListener('hidden.bs.modal', () => {
    document.body.removeChild(modal);
  });
}

export { messaging };