"""Gera o ícone do Nico (orbe estilo HUD) como .ico multi-resolução.
Script utilitário - não faz parte do programa em si, só gera o arquivo
nico_icon.ico usado pelo atalho da área de trabalho.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

BASE_SIZE = 256
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "nico_icon.ico")

BG_COLOR = (8, 9, 16, 255)
CORE_COLOR = (79, 214, 255)       # ciano, mesma cor do status "Listening" no HUD
GLOW_COLOR = (157, 107, 255)      # roxo, mesma cor do "Thinking"


def make_base_image(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = cy = size / 2

    # Fundo circular escuro (igual ao tema dark do HUD)
    draw.ellipse([0, 0, size, size], fill=BG_COLOR)

    # Anéis finos, como os da interface
    for ring_radius, width, alpha in (
        (size * 0.46, max(1, size // 64), 90),
        (size * 0.40, max(1, size // 80), 60),
    ):
        bbox = [cx - ring_radius, cy - ring_radius, cx + ring_radius, cy + ring_radius]
        draw.ellipse(bbox, outline=(*CORE_COLOR, alpha), width=max(1, int(width)))

    # Núcleo com glow (desenhado em camada separada e borrado)
    glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    core_radius = size * 0.24
    glow_draw.ellipse(
        [cx - core_radius * 1.8, cy - core_radius * 1.8, cx + core_radius * 1.8, cy + core_radius * 1.8],
        fill=(*GLOW_COLOR, 160),
    )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=size * 0.06))
    img = Image.alpha_composite(img, glow_layer)

    draw = ImageDraw.Draw(img)
    draw.ellipse(
        [cx - core_radius, cy - core_radius, cx + core_radius, cy + core_radius],
        fill=(*CORE_COLOR, 255),
    )

    # Brilho especular (pequeno destaque claro no núcleo)
    highlight_radius = core_radius * 0.35
    hx, hy = cx - core_radius * 0.3, cy - core_radius * 0.35
    draw.ellipse(
        [hx - highlight_radius, hy - highlight_radius, hx + highlight_radius, hy + highlight_radius],
        fill=(255, 255, 255, 110),
    )

    return img


def main():
    base = make_base_image(BASE_SIZE)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [base.resize((s, s), Image.LANCZOS) for s in sizes]
    base.save(OUTPUT_PATH, format="ICO", sizes=[(s, s) for s in sizes])
    print("Icon saved to:", os.path.abspath(OUTPUT_PATH))


if __name__ == "__main__":
    main()
