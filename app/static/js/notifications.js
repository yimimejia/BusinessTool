// Solicitar permisos para notificaciones
function requestNotificationPermission() {
    if ('Notification' in window) {
        Notification.requestPermission();
    }
}

// Reproducir sonido de alerta
function playAlertSound() {
    const audio = new Audio('/static/sounds/notification.mp3');
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

    // Reproducir sonido si el mensaje es sobre un nuevo trabajo
    if (data.type === "nuevo_trabajo") {
        playAlertSound();
    }
};

// Solicitar permisos al cargar la página
document.addEventListener('DOMContentLoaded', requestNotificationPermission);
