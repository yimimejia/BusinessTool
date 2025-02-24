from PIL import Image
import os
import shutil

def process_logo():
    # Asegurar que el directorio de iconos existe
    os.makedirs('app/static/icons', exist_ok=True)

    try:
        # Copiar la imagen original a static/icons
        source_image = 'attached_assets/IMG_4828.png'
        if not os.path.exists(source_image):
            print(f'Error: No se encuentra el archivo {source_image}')
            return False

        # Abrir la imagen
        with Image.open(source_image) as img:
            # Convertir a RGBA si no lo está ya
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Tamaños requeridos para PWA
            sizes = [
                (72, 72), (96, 96), (128, 128), (144, 144),
                (152, 152), (192, 192), (384, 384), (512, 512)
            ]

            # Generar cada tamaño
            for width, height in sizes:
                resized = img.resize((width, height), Image.Resampling.LANCZOS)
                output_path = f'app/static/icons/logo-{width}x{width}.png'
                resized.save(output_path, 'PNG', quality=95)
                print(f'Generated: {output_path}')

            # También guardar una copia como logo.png en static
            img.save('app/static/logo.png', 'PNG', quality=95)
            print('Generated: app/static/logo.png')

        return True
    except Exception as e:
        print(f'Error processing logo: {str(e)}')
        return False

if __name__ == '__main__':
    process_logo()