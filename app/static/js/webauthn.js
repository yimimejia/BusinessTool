// Función para verificar si el navegador soporta WebAuthn
function isWebAuthnSupported() {
    return window.PublicKeyCredential !== undefined &&
           typeof window.PublicKeyCredential === 'function';
}

// Función para verificar si hay autenticador de plataforma disponible
async function isPlatformAuthenticatorAvailable() {
    if (!isWebAuthnSupported()) {
        return false;
    }

    try {
        // En iOS, esto puede fallar pero aún así el dispositivo puede soportar Face ID/Touch ID
        const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();

        // En iOS, podríamos tener soporte incluso si la verificación falla
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        return available || isIOS;
    } catch (error) {
        console.error('Error verificando autenticador:', error);
        // En iOS, asumimos que está disponible si el navegador soporta WebAuthn
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        return isIOS && isWebAuthnSupported();
    }
}

// Función para convertir ArrayBuffer a Base64 de manera segura
function arrayBufferToBase64(buffer) {
    if (!buffer || !(buffer instanceof ArrayBuffer)) {
        throw new Error("Buffer inválido");
    }
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

// Función para convertir Base64 a ArrayBuffer de manera segura
function base64ToArrayBuffer(base64) {
    if (!base64 || typeof base64 !== 'string') {
        throw new Error("Cadena base64 inválida");
    }
    const binary = atob(base64.replace(/-/g, '+').replace(/_/g, '/'));
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

// Función para mostrar mensajes de error amigables y descriptivos
function showUserFriendlyError(error) {
    console.error('Error detallado:', error);

    let message = 'Error desconocido';
    const errorMsg = error.message.toLowerCase();

    if (errorMsg.includes('operation either timed out') || errorMsg.includes('timeout')) {
        message = 'La operación ha expirado. Por favor, intente nuevamente y responda más rápido a la solicitud biométrica.';
    } else if (errorMsg.includes('pattern')) {
        message = 'El dispositivo no pudo procesar la solicitud. Por favor, asegúrese de que Face ID/Touch ID esté configurado en su dispositivo.';
    } else if (errorMsg.includes('cancelled')) {
        message = 'Operación cancelada. Por favor, complete la verificación biométrica cuando se le solicite.';
    } else if (errorMsg.includes('not supported')) {
        message = 'Su dispositivo no tiene Face ID o Touch ID configurado. Por favor, configure la autenticación biométrica en su dispositivo.';
    } else if (errorMsg.includes('already registered')) {
        message = 'Este dispositivo ya está registrado. Por favor, use otro dispositivo o elimine el registro existente.';
    } else if (errorMsg.includes('user verification')) {
        message = 'La verificación biométrica falló. Por favor, asegúrese de usar el mismo dedo o rostro registrado.';
    } else {
        message = 'Error de autenticación biométrica. Por favor, intente nuevamente o contacte a soporte si el problema persiste.';
    }

    alert(message);
}

// Función para registrar credenciales biométricas
async function registerBiometric(deviceName) {
    try {
        console.log('Iniciando registro biométrico...');
        const available = await isPlatformAuthenticatorAvailable();
        if (!available) {
            throw new Error('Su dispositivo no tiene Face ID o Touch ID disponible');
        }

        // Obtener opciones de creación del servidor
        const response = await fetch('/webauthn/register/begin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ device_name: deviceName })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Error al iniciar registro biométrico');
        }

        const options = await response.json();
        console.log('Opciones de registro recibidas:', options);

        // Convertir las opciones del formato base64 a ArrayBuffer
        options.publicKey.challenge = base64ToArrayBuffer(options.publicKey.challenge);
        options.publicKey.user.id = base64ToArrayBuffer(options.publicKey.user.id);

        console.log('Solicitando credenciales al navegador...');
        // Crear credenciales
        const credential = await navigator.credentials.create({
            publicKey: options.publicKey
        });

        console.log('Credenciales creadas exitosamente');

        // Preparar datos para enviar al servidor
        const credentialResponse = {
            id: credential.id,
            rawId: arrayBufferToBase64(credential.rawId),
            response: {
                clientDataJSON: arrayBufferToBase64(credential.response.clientDataJSON),
                attestationObject: arrayBufferToBase64(credential.response.attestationObject)
            },
            type: credential.type
        };

        // Completar el registro
        const finalResponse = await fetch('/webauthn/register/complete', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(credentialResponse)
        });

        if (!finalResponse.ok) {
            const error = await finalResponse.json();
            throw new Error(error.message || 'Error al completar registro biométrico');
        }

        console.log('Registro biométrico completado exitosamente');
        return await finalResponse.json();

    } catch (error) {
        console.error('Error durante el registro biométrico:', error);
        showUserFriendlyError(error);
        throw error;
    }
}

// Función para autenticar con biometría
async function authenticateBiometric(username) {
    try {
        console.log('Iniciando autenticación biométrica...');
        if (!isWebAuthnSupported()) {
            throw new Error('WebAuthn no es compatible con este navegador');
        }

        // Obtener opciones de autenticación del servidor
        const response = await fetch('/webauthn/authenticate/begin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ username })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Error al iniciar autenticación biométrica');
        }

        const options = await response.json();
        console.log('Opciones de autenticación recibidas:', options);

        // Convertir las opciones del formato base64 a ArrayBuffer
        options.publicKey.challenge = base64ToArrayBuffer(options.publicKey.challenge);
        if (options.publicKey.allowCredentials) {
            options.publicKey.allowCredentials = options.publicKey.allowCredentials.map(credential => ({
                ...credential,
                id: base64ToArrayBuffer(credential.id)
            }));
        }

        console.log('Solicitando verificación biométrica...');
        // Obtener credenciales
        const assertion = await navigator.credentials.get({
            publicKey: options.publicKey
        });

        console.log('Verificación biométrica completada');

        // Preparar respuesta para el servidor
        const assertionResponse = {
            id: assertion.id,
            rawId: arrayBufferToBase64(assertion.rawId),
            response: {
                clientDataJSON: arrayBufferToBase64(assertion.response.clientDataJSON),
                authenticatorData: arrayBufferToBase64(assertion.response.authenticatorData),
                signature: arrayBufferToBase64(assertion.response.signature),
                userHandle: assertion.response.userHandle ? arrayBufferToBase64(assertion.response.userHandle) : null
            },
            type: assertion.type
        };

        // Completar la autenticación
        const finalResponse = await fetch('/webauthn/authenticate/complete', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(assertionResponse)
        });

        if (!finalResponse.ok) {
            const error = await finalResponse.json();
            throw new Error(error.message || 'Error en la autenticación biométrica');
        }

        console.log('Autenticación biométrica exitosa');
        window.location.href = '/dashboard';
        return await finalResponse.json();

    } catch (error) {
        console.error('Error durante la autenticación biométrica:', error);
        showUserFriendlyError(error);
        throw error;
    }
}

// Función para configurar biometría desde la interfaz de usuario
async function setupBiometricAuth() {
    try {
        console.log('Iniciando configuración biométrica...');
        const deviceName = prompt('Por favor, ingrese un nombre para este dispositivo:');
        if (!deviceName) {
            throw new Error('Se requiere un nombre para el dispositivo');
        }

        await registerBiometric(deviceName);
        alert('¡Registro biométrico exitoso! Ahora puede usar Face ID o Touch ID para iniciar sesión.');
        location.reload();
    } catch (error) {
        console.error('Error en configuración biométrica:', error);
        showUserFriendlyError(error);
    }
}

// Función para iniciar sesión con biometría
async function loginWithBiometric(username) {
    try {
        console.log('Iniciando login biométrico...');
        await authenticateBiometric(username);
    } catch (error) {
        showUserFriendlyError(error);
    }
}

// Verificar estado de biometría al cargar la página
document.addEventListener('DOMContentLoaded', async () => {
    const biometricSetupButton = document.getElementById('setup-biometric');
    const biometricLoginButton = document.getElementById('biometric-login');
    const usernameInput = document.getElementById('username');

    if (biometricSetupButton) {
        console.log('Botón de configuración biométrica encontrado');
        biometricSetupButton.addEventListener('click', setupBiometricAuth);
    }

    if (biometricLoginButton) {
        console.log('Botón de login biométrico encontrado');
        biometricLoginButton.addEventListener('click', () => {
            const username = usernameInput.value;
            if (!username) {
                alert('Por favor, ingrese su nombre de usuario primero');
                return;
            }
            loginWithBiometric(username);
        });
    }

    // Verificar credenciales al cambiar el nombre de usuario
    if (usernameInput) {
        usernameInput.addEventListener('change', async () => {
            const username = usernameInput.value;
            if (username) {
                try {
                    console.log('Verificando credenciales biométricas para:', username);
                    const response = await fetch('/webauthn/status', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ username })
                    });
                    const data = await response.json();

                    if (data.enabled) {
                        console.log('Credenciales biométricas encontradas');
                        biometricLoginButton.style.display = 'block';
                        if (biometricSetupButton) {
                            biometricSetupButton.style.display = 'none';
                        }
                    } else {
                        console.log('No se encontraron credenciales biométricas');
                        biometricLoginButton.style.display = 'none';
                        if (biometricSetupButton) {
                            biometricSetupButton.style.display = 'block';
                        }
                    }
                } catch (error) {
                    console.error('Error verificando estado biométrico:', error);
                    showUserFriendlyError(error);
                }
            }
        });
    }

    // Verificar soporte inicial de WebAuthn
    try {
        const supported = await isPlatformAuthenticatorAvailable();
        console.log('Soporte de autenticación biométrica:', supported ? 'Disponible' : 'No disponible');

        if (!supported) {
            if (biometricSetupButton) biometricSetupButton.style.display = 'none';
            if (biometricLoginButton) biometricLoginButton.style.display = 'none';
        }
    } catch (error) {
        console.error('Error verificando soporte de WebAuthn:', error);
    }
});