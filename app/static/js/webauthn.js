// Función para verificar si el navegador soporta WebAuthn
function isWebAuthnSupported() {
    return window.PublicKeyCredential !== undefined &&
           typeof window.PublicKeyCredential === 'function';
}

// Variable para prevenir múltiples intentos de configuración
let isConfiguring = false;

// Función para verificar si hay autenticador de plataforma disponible
async function isPlatformAuthenticatorAvailable() {
    if (!isWebAuthnSupported()) {
        return false;
    }

    try {
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

        if (isIOS) {
            // En iOS con Safari, asumimos que Face ID está disponible
            return true;
        }

        // Para otros navegadores, verificamos normalmente
        return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch (error) {
        console.error('Error verificando autenticador:', error);
        // En caso de error en iOS, asumimos que está disponible
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        return isIOS;
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

// Función para mostrar mensajes de error amigables
function showUserFriendlyError(error) {
    console.error('Error detallado:', error);
    let message = 'Error desconocido';
    const errorMsg = error.message.toLowerCase();

    if (errorMsg.includes('timeout')) {
        message = 'La operación ha expirado. Por favor, intente nuevamente.';
    } else if (errorMsg.includes('pattern') || errorMsg.includes('not supported')) {
        message = 'Este dispositivo no tiene Face ID o Touch ID configurado o no es compatible.';
    } else if (errorMsg.includes('cancelled')) {
        message = 'La operación fue cancelada. Por favor, intente nuevamente.';
    } else if (errorMsg.includes('already registered')) {
        message = 'Este dispositivo ya está registrado.';
    } else if (errorMsg.includes('user verification')) {
        message = 'La verificación biométrica falló. Por favor, intente nuevamente.';
    } else {
        message = 'Ocurrió un error. Por favor, intente nuevamente.';
    }

    alert(message);
}

// Función para registrar credenciales biométricas
async function registerBiometric(deviceName) {
    if (isConfiguring) {
        console.log('Ya hay un proceso de configuración en curso');
        return;
    }

    try {
        isConfiguring = true;
        console.log('Iniciando registro biométrico...');

        const available = await isPlatformAuthenticatorAvailable();
        if (!available) {
            throw new Error('Este dispositivo no tiene Face ID disponible');
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
        console.log('Opciones de registro recibidas');

        // Convertir las opciones del formato base64 a ArrayBuffer
        options.publicKey.challenge = base64ToArrayBuffer(options.publicKey.challenge);
        options.publicKey.user.id = base64ToArrayBuffer(options.publicKey.user.id);

        // Para iOS, forzamos algunas opciones específicas
        if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
            options.publicKey.authenticatorSelection = {
                authenticatorAttachment: "platform",
                requireResidentKey: false,
                userVerification: "preferred"
            };
        }

        console.log('Solicitando verificación Face ID...');
        const credential = await navigator.credentials.create({
            publicKey: options.publicKey
        });

        console.log('Verificación Face ID completada');

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
        alert('¡Registro de Face ID exitoso! Ahora puede usar Face ID para iniciar sesión.');
        location.reload();
        return await finalResponse.json();

    } catch (error) {
        console.error('Error durante el registro biométrico:', error);
        showUserFriendlyError(error);
        throw error;
    } finally {
        isConfiguring = false;
    }
}

// Función para autenticar con biometría
async function authenticateBiometric(username) {
    try {
        console.log('Iniciando autenticación biométrica...');

        const available = await isPlatformAuthenticatorAvailable();
        if (!available) {
            throw new Error('Este dispositivo no tiene Face ID o Touch ID disponible');
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
        console.log('Opciones de autenticación recibidas');

        // Convertir las opciones del formato base64 a ArrayBuffer
        options.publicKey.challenge = base64ToArrayBuffer(options.publicKey.challenge);
        if (options.publicKey.allowCredentials) {
            options.publicKey.allowCredentials = options.publicKey.allowCredentials.map(credential => ({
                ...credential,
                id: base64ToArrayBuffer(credential.id)
            }));
        }

        console.log('Solicitando verificación biométrica...');
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
    if (isConfiguring) {
        console.log('Ya hay un proceso de configuración en curso');
        return;
    }

    try {
        console.log('Iniciando configuración biométrica...');
        const deviceName = prompt('Por favor, ingrese un nombre para este dispositivo:');
        if (!deviceName) {
            throw new Error('Se requiere un nombre para el dispositivo');
        }

        await registerBiometric(deviceName);
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

    if (biometricLoginButton && usernameInput) {
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
                        if (biometricLoginButton) biometricLoginButton.style.display = 'block';
                        if (biometricSetupButton) biometricSetupButton.style.display = 'none';
                    } else {
                        console.log('No se encontraron credenciales biométricas');
                        if (biometricLoginButton) biometricLoginButton.style.display = 'none';
                        if (biometricSetupButton) biometricSetupButton.style.display = 'block';
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