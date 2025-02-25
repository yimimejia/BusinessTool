from PIL import Image
import os

def process_logo():
    """
    Procesa el logo de la cámara y genera los diferentes tamaños de iconos necesarios
    para la PWA.
    """
    # Asegurar que el directorio de iconos existe
    os.makedirs('app/static/icons', exist_ok=True)

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

            # Generar cada tamaño
            for width, height in sizes:
                resized = img.resize((width, height), Image.Resampling.LANCZOS)
                output_path = f'app/static/icons/camera-{width}x{width}.png'
                resized.save(output_path, 'PNG')
                print(f'Generated: {output_path}')

        return True
    except Exception as e:
        print(f'Error processing logo: {str(e)}')
        return False

if __name__ == '__main__':
    process_logo()