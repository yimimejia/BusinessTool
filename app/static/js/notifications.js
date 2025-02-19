// Solicitar permisos para notificaciones
function requestNotificationPermission() {
    if ('Notification' in window) {
        Notification.requestPermission().then(function(permission) {
            if (permission === 'granted') {
                console.log('Permisos de notificación concedidos');
            }
        });
    }
}

// Reproducir sonido de alerta
function playAlertSound() {
    const audio = new Audio('/static/notification.mp3');
    audio.play().catch(error => {
        console.error('Error al reproducir sonido:', error);
    });
}

// Configurar EventSource para notificaciones en tiempo real
let evtSource;

function setupEventSource() {
    evtSource = new EventSource("/stream");

    evtSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);

            // Mostrar notificación del navegador
            if (Notification.permission === "granted") {
                new Notification("FOTO VIDEO MOJICA", {
                    body: data.message,
                    icon: '/static/icon.png'
                });
            }

            // Reproducir sonido para todos los tipos de notificaciones
            playAlertSound();

            // Mostrar alerta en la página
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${data.type} alert-dismissible fade show`;
            alertDiv.innerHTML = `
                ${data.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            document.querySelector('main').insertAdjacentElement('afterbegin', alertDiv);
        } catch (error) {
            console.error('Error al procesar notificación:', error);
        }
    };

    evtSource.onerror = function(error) {
        console.error('Error en EventSource:', error);
        evtSource.close();
        // Reintentar conexión después de 5 segundos
        setTimeout(setupEventSource, 5000);
    };
}

// Inicializar cuando el DOM esté cargado
document.addEventListener('DOMContentLoaded', function() {
    requestNotificationPermission();
    setupEventSource();
});