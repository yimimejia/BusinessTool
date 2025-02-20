// Función para verificar si el navegador soporta WebAuthn
function isWebAuthnSupported() {
    return window.PublicKeyCredential !== undefined &&
           typeof window.PublicKeyCredential === 'function' &&
           typeof window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable === 'function';
}

// Función para verificar si hay autenticador de plataforma disponible
async function isPlatformAuthenticatorAvailable() {
    if (!isWebAuthnSupported()) {
        return false;
    }
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
}

// Función para convertir ArrayBuffer a Base64
function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

// Función para convertir Base64 a ArrayBuffer
function base64ToArrayBuffer(base64) {
    const binary = atob(base64.replace(/-/g, '+').replace(/_/g, '/'));
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

// Función para mostrar mensajes de error amigables
function showUserFriendlyError(error) {
    let message = 'Error desconocido';

    if (error.message.includes('The operation either timed out')) {
        message = 'La operación ha expirado. Por favor, intente nuevamente y responda más rápido a la solicitud biométrica.';
    } else if (error.message.includes('did not match the expected pattern')) {
        message = 'Su dispositivo no es compatible con este método de autenticación. Por favor, use contraseña.';
    } else if (error.message.includes('The operation was cancelled')) {
        message = 'Operación cancelada por el usuario.';
    } else {
        message = error.message;
    }

    alert(message);
}

// Función para registrar credenciales biométricas
async function registerBiometric(deviceName) {
    try {
        const available = await isPlatformAuthenticatorAvailable();
        if (!available) {
            throw new Error('Su dispositivo no tiene un autenticador biométrico compatible');
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

        // Convertir las opciones del formato base64 a ArrayBuffer
        options.publicKey.challenge = base64ToArrayBuffer(options.publicKey.challenge);
        options.publicKey.user.id = base64ToArrayBuffer(options.publicKey.user.id);

        // Crear credenciales
        const credential = await navigator.credentials.create({
            publicKey: options.publicKey
        });

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

        // Convertir las opciones del formato base64 a ArrayBuffer
        options.publicKey.challenge = base64ToArrayBuffer(options.publicKey.challenge);
        if (options.publicKey.allowCredentials) {
            options.publicKey.allowCredentials = options.publicKey.allowCredentials.map(credential => ({
                ...credential,
                id: base64ToArrayBuffer(credential.id)
            }));
        }

        // Obtener credenciales
        const assertion = await navigator.credentials.get({
            publicKey: options.publicKey
        });

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
        const available = await isPlatformAuthenticatorAvailable();
        if (!available) {
            alert('Su dispositivo no tiene un autenticador biométrico compatible. Por favor, use contraseña.');
            return;
        }

        const deviceName = prompt('Por favor, ingrese un nombre para este dispositivo:');
        if (!deviceName) {
            throw new Error('Se requiere un nombre para el dispositivo');
        }

        await registerBiometric(deviceName);
        alert('¡Registro biométrico exitoso! Ahora puede usar Face ID o Touch ID para iniciar sesión.');
        location.reload();
    } catch (error) {
        showUserFriendlyError(error);
    }
}

// Función para iniciar sesión con biometría
async function loginWithBiometric(username) {
    try {
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
        biometricSetupButton.addEventListener('click', setupBiometricAuth);
    }

    if (biometricLoginButton) {
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
                    const response = await fetch('/webauthn/status', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ username })
                    });
                    const data = await response.json();

                    if (data.enabled) {
                        biometricLoginButton.style.display = 'block';
                        biometricSetupButton.style.display = 'none';
                    } else {
                        biometricLoginButton.style.display = 'none';
                        biometricSetupButton.style.display = 'block';
                    }
                } catch (error) {
                    console.error('Error verificando estado biométrico:', error);
                }
            }
        });
    }
});