
// Manejar notificaciones
document.addEventListener('DOMContentLoaded', function() {
    const toastContainer = document.querySelector('.toast-container');
    
    // Verificar si los elementos existen antes de usarlos
    const pendingCount = document.getElementById('pendingCount');
    const pendingPhotosCount = document.getElementById('pendingPhotosCount');
    const messageCount = document.querySelector('.message-count');

    // Función para actualizar la insignia de mensajes
    function updateMessageBadge() {
        fetch('/messages/unread')
            .then(response => response.json())
            .then(data => {
                if (messageCount) {
                    if (data.count > 0) {
                        messageCount.textContent = data.count;
                        messageCount.classList.remove('d-none');
                    } else {
                        messageCount.classList.add('d-none');
                    }
                }
            });
    }

    // Actualizar contadores si existen
    if (pendingCount || pendingPhotosCount) {
        fetch('/jobs/pending')
            .then(response => response.json())
            .then(data => {
                if (pendingCount && data.pending_jobs > 0) {
                    pendingCount.textContent = data.pending_jobs;
                    pendingCount.classList.remove('d-none');
                }
                if (pendingPhotosCount && data.pending_photos > 0) {
                    pendingPhotosCount.textContent = data.pending_photos;
                    pendingPhotosCount.classList.remove('d-none');
                }
            });
    }

    // Actualizar mensajes cada minuto
    if (messageCount) {
        updateMessageBadge();
        setInterval(updateMessageBadge, 60000);
    }
});
