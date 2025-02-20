// Función para verificar si el navegador soporta WebAuthn
function isWebAuthnSupported() {
    return window.PublicKeyCredential !== undefined &&
           typeof window.PublicKeyCredential === 'function';
}

// Función para convertir ArrayBuffer a Base64
function arrayBufferToBase64(buffer) {
    return btoa(String.fromCharCode(...new Uint8Array(buffer)));
}

// Función para convertir Base64 a ArrayBuffer
function base64ToArrayBuffer(base64) {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

// Función para registrar credenciales biométricas
async function registerBiometric(deviceName) {
    try {
        if (!isWebAuthnSupported()) {
            throw new Error('WebAuthn no es compatible con este navegador');
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
        const options = await response.json();

        // Convertir las opciones del formato base64 a ArrayBuffer
        options.publicKey.challenge = base64ToArrayBuffer(options.publicKey.challenge);
        options.publicKey.user.id = base64ToArrayBuffer(options.publicKey.user.id);

        // Crear credenciales
        const credential = await navigator.credentials.create({
            publicKey: options.publicKey
        });

        // Enviar la respuesta al servidor
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

        const result = await finalResponse.json();
        if (!finalResponse.ok) {
            throw new Error(result.message || 'Error al registrar credenciales biométricas');
        }

        return result;

    } catch (error) {
        console.error('Error durante el registro biométrico:', error);
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
            options.publicKey.allowCredentials = options.publicKey.allowCredentials.map(credential => {
                return {
                    ...credential,
                    id: base64ToArrayBuffer(credential.id)
                };
            });
        }

        // Obtener credenciales
        const assertion = await navigator.credentials.get({
            publicKey: options.publicKey
        });

        // Enviar la respuesta al servidor
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

        const result = await finalResponse.json();
        if (!finalResponse.ok) {
            throw new Error(result.message || 'Error en la autenticación biométrica');
        }

        window.location.href = '/dashboard';
        return result;

    } catch (error) {
        console.error('Error durante la autenticación biométrica:', error);
        throw error;
    }
}

// Función para configurar biometría desde la interfaz de usuario
async function setupBiometricAuth() {
    try {
        const deviceName = prompt('Por favor, ingrese un nombre para este dispositivo:');
        if (!deviceName) {
            throw new Error('Se requiere un nombre para el dispositivo');
        }

        await registerBiometric(deviceName);
        alert('¡Registro biométrico exitoso! Ahora puede usar Face ID o Touch ID para iniciar sesión.');
        location.reload();
    } catch (error) {
        alert('Error al configurar el acceso biométrico: ' + error.message);
    }
}

// Función para iniciar sesión con biometría
async function loginWithBiometric(username) {
    try {
        await authenticateBiometric(username);
    } catch (error) {
        alert('Error al iniciar sesión con biometría: ' + error.message);
    }
}

// Verificar estado de biometría al cargar la página
document.addEventListener('DOMContentLoaded', async () => {
    const biometricSetupButton = document.getElementById('setup-biometric');
    const biometricLoginButton = document.getElementById('biometric-login');

    if (biometricSetupButton) {
        biometricSetupButton.addEventListener('click', setupBiometricAuth);
    }

    if (biometricLoginButton) {
        const username = biometricLoginButton.dataset.username;
        biometricLoginButton.addEventListener('click', () => loginWithBiometric(username));
    }
});