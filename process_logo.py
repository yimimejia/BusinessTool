from PIL import Image
import os

def process_logo():
    # Asegurar que el directorio de iconos existe
    os.makedirs('app/static/icons', exist_ok=True)
    
    try:
        # Abrir el archivo .ico
        with Image.open('attached_assets/logo.ico') as img:
            # Convertir a RGBA si no lo está ya
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Tamaños requeridos para PWA
            sizes = [(192, 192), (512, 512)]
            
            # Generar cada tamaño
            for width, height in sizes:
                resized = img.resize((width, height), Image.Resampling.LANCZOS)
                output_path = f'app/static/icons/logo-{width}x{width}.png'
                resized.save(output_path, 'PNG')
                print(f'Generated: {output_path}')
                
        return True
    except Exception as e:
        print(f'Error processing logo: {str(e)}')
        return False

if __name__ == '__main__':
    process_logo()
