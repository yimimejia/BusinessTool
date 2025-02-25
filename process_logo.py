from PIL import Image
import os

def process_logo():
    """
    Procesa el logo de la cámara y genera los diferentes tamaños de iconos necesarios
    para la PWA y favicon.
    """
    # Asegurar que los directorios existen
    os.makedirs('app/static/icons', exist_ok=True)
    os.makedirs('app/static', exist_ok=True)

    try:
        # Abrir la imagen del logo
        with Image.open('attached_assets/123_1740442189049.png') as img:
            # Convertir a RGBA si no lo está ya
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Tamaños requeridos para PWA
            sizes = [
                (72, 72),
                (96, 96),
                (128, 128),
                (144, 144),
                (152, 152),
                (192, 192),
                (384, 384),
                (512, 512)
            ]

            # Generar cada tamaño para PWA
            for width, height in sizes:
                resized = img.resize((width, height), Image.Resampling.LANCZOS)
                output_path = f'app/static/icons/camera-{width}x{width}.png'
                resized.save(output_path, 'PNG')
                print(f'Generated: {output_path}')

            # Generar favicons
            favicon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
            favicon_images = []

            # Crear diferentes tamaños de favicon
            for size in favicon_sizes:
                favicon = img.resize(size, Image.Resampling.LANCZOS)
                if favicon.mode != 'RGBA':
                    favicon = favicon.convert('RGBA')
                favicon_images.append(favicon)

                # Guardar versión PNG del favicon
                if size == (32, 32):  # Tamaño estándar para favicon.png
                    favicon.save('app/static/favicon.png', 'PNG')
                    print('Generated: app/static/favicon.png')

            # Guardar el favicon.ico con múltiples tamaños
            favicon_images[0].save(
                'app/static/favicon.ico',
                format='ICO',
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
                append_images=favicon_images[1:]
            )
            print('Generated: app/static/favicon.ico')

            # Generar apple-touch-icon
            apple_touch = img.resize((180, 180), Image.Resampling.LANCZOS)
            apple_touch.save('app/static/apple-touch-icon.png', 'PNG')
            print('Generated: app/static/apple-touch-icon.png')

        return True
    except Exception as e:
        print(f'Error processing logo: {str(e)}')
        return False

if __name__ == '__main__':
    process_logo()