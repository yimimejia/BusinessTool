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
async function registerBiometric() {
    try {
        if (!isWebAuthnSupported()) {
            throw new Error('WebAuthn no es compatible con este navegador');
        }

        // Obtener opciones de creación del servidor
        const response = await fetch('/webauthn/register/begin', {
            method: 'POST',
            credentials: 'same-origin'
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

        if (finalResponse.ok) {
            return true;
        }
        throw new Error('Error al registrar credenciales biométricas');

    } catch (error) {
        console.error('Error durante el registro biométrico:', error);
        throw error;
    }
}

// Función para autenticar con biometría
async function authenticateBiometric() {
    try {
        if (!isWebAuthnSupported()) {
            throw new Error('WebAuthn no es compatible con este navegador');
        }

        // Obtener opciones de autenticación del servidor
        const response = await fetch('/webauthn/authenticate/begin', {
            method: 'POST',
            credentials: 'same-origin'
        });
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

        if (finalResponse.ok) {
            window.location.href = '/dashboard';
            return true;
        }
        throw new Error('Error en la autenticación biométrica');

    } catch (error) {
        console.error('Error durante la autenticación biométrica:', error);
        throw error;
    }
}
