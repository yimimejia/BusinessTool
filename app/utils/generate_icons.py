from PIL import Image, ImageDraw
import os

def generate_pwa_icons():
    # Asegurarnos de que el directorio de íconos exista
    icons_dir = os.path.join('app', 'static', 'icons')
    os.makedirs(icons_dir, exist_ok=True)

    sizes = [(192, 192), (512, 512)]
    
    for size in sizes:
        # Crear una imagen con fondo negro
        img = Image.new('RGB', size, color='black')
        draw = ImageDraw.Draw(img)
        
        # Calcular el tamaño del círculo (80% del tamaño más pequeño)
        circle_size = int(min(size) * 0.8)
        
        # Calcular las coordenadas para centrar el círculo
        x = (size[0] - circle_size) // 2
        y = (size[1] - circle_size) // 2
        
        # Dibujar un círculo blanco
        draw.ellipse([x, y, x + circle_size, y + circle_size], fill='white')
        
        # Guardar el ícono
        filename = f'icon-{size[0]}x{size[1]}.png'
        filepath = os.path.join(icons_dir, filename)
        img.save(filepath)

if __name__ == '__main__':
    generate_pwa_icons()
