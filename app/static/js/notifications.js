// Solicitar permisos para notificaciones
function requestNotificationPermission() {
    if ('Notification' in window) {
        Notification.requestPermission();
    }
}

// Reproducir sonido de alerta
function playAlertSound() {
    const audio = new Audio('/static/notification.mp3');
    audio.play().catch(error => console.log('Error al reproducir sonido:', error));
}

// Configurar EventSource para notificaciones en tiempo real
const evtSource = new EventSource("/stream");

evtSource.onmessage = function(event) {
    const data = JSON.parse(event.data);

    // Mostrar notificación del navegador
    if (Notification.permission === "granted") {
        new Notification("FOTO VIDEO MOJICA", {
            body: data.message,
            icon: "/static/img/logo.png"
        });
    }

    // Reproducir sonido si el mensaje es sobre un trabajo pendiente
    if (data.type === "pending_job") {
        playAlertSound();
    }
};

// Solicitar permisos al cargar la página
document.addEventListener('DOMContentLoaded', requestNotificationPermission);
// Inicializar notificaciones
function initNotifications(userId) {
    const evtSource = new EventSource('/stream');
    
    evtSource.addEventListener('notification', function(event) {
        const notification = JSON.parse(event.data);
        if (notification.user_id === userId) {
            showNotification(notification);
        }
    });

    evtSource.onerror = function(err) {
        console.error("Error en EventSource:", err);
    };
}

function showNotification(notification) {
    const container = document.createElement('div');
    container.className = `alert alert-${notification.type} alert-dismissible fade show`;
    container.innerHTML = `
        <strong>${notification.title}</strong>
        <p>${notification.message}</p>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.getElementById('notifications-container').appendChild(container);
    
    // Auto-eliminar después de 5 segundos
    setTimeout(() => {
        container.remove();
    }, 5000);
}

// Registrar service worker para notificaciones
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/js/sw.js')
        .then(registration => {
            console.log('ServiceWorker registrado exitosamente:', registration.scope);
        })
        .catch(error => {
            console.log('Error registrando ServiceWorker:', error);
        });
}
