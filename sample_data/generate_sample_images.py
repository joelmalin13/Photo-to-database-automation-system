"""Generates 12 varied synthetic photographic test scenes for PixelMind sample dataset.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SAMPLE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def draw_car(draw: ImageDraw.ImageDraw, x: int, y: int, color=(200, 30, 30)) -> None:
    """Draw a car profile with wheels."""
    # Body
    draw.rectangle([x, y + 25, x + 160, y + 65], fill=color, outline=(20, 20, 20), width=2)
    # Cabin
    draw.polygon([(x + 35, y + 25), (x + 55, y), (x + 115, y), (x + 135, y + 25)], fill=(120, 160, 200), outline=(20, 20, 20), width=2)
    # Wheels
    draw.ellipse([x + 25, y + 50, x + 55, y + 80], fill=(30, 30, 30), outline=(100, 100, 100), width=3)
    draw.ellipse([x + 105, y + 50, x + 135, y + 80], fill=(30, 30, 30), outline=(100, 100, 100), width=3)


def draw_person(draw: ImageDraw.ImageDraw, x: int, y: int, color=(40, 80, 180)) -> None:
    """Draw a stylized human silhouette."""
    # Head
    draw.ellipse([x + 10, y, x + 35, y + 25], fill=(235, 195, 165), outline=(50, 50, 50), width=2)
    # Torso
    draw.rectangle([x + 5, y + 26, x + 40, y + 75], fill=color, outline=(20, 20, 20), width=2)
    # Legs
    draw.rectangle([x + 7, y + 76, x + 20, y + 120], fill=(40, 40, 50), outline=(20, 20, 20), width=2)
    draw.rectangle([x + 25, y + 76, x + 38, y + 120], fill=(40, 40, 50), outline=(20, 20, 20), width=2)


def draw_dog(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """Draw a dog silhouette."""
    # Body
    draw.ellipse([x, y + 20, x + 80, y + 60], fill=(160, 100, 50), outline=(30, 30, 30), width=2)
    # Head
    draw.ellipse([x + 65, y + 5, x + 95, y + 35], fill=(160, 100, 50), outline=(30, 30, 30), width=2)
    # Snout
    draw.ellipse([x + 85, y + 15, x + 105, y + 32], fill=(130, 80, 40))
    # Legs
    draw.rectangle([x + 10, y + 55, x + 20, y + 90], fill=(140, 90, 40))
    draw.rectangle([x + 65, y + 55, x + 75, y + 90], fill=(140, 90, 40))


def draw_laptop(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """Draw a modern laptop on a desk."""
    # Screen
    draw.rectangle([x + 10, y, x + 110, y + 65], fill=(30, 30, 40), outline=(180, 180, 180), width=3)
    draw.rectangle([x + 15, y + 5, x + 105, y + 60], fill=(80, 130, 200))
    # Base
    draw.polygon([(x, y + 70), (x + 120, y + 70), (x + 130, y + 80), (x - 10, y + 80)], fill=(160, 160, 170), outline=(80, 80, 80), width=2)


def generate_all_samples() -> None:
    """Generate 12 diverse sample images across canonical categories."""
    scenes = [
        ("street_cars.png", "Vehicles", "outdoor", "street", lambda d: (d.rectangle([0, 250, 600, 400], fill=(80, 80, 85)), draw_car(d, 50, 220, (220, 30, 30)), draw_car(d, 280, 210, (30, 80, 200)), draw_person(d, 480, 180))),
        ("city_pedestrians.png", "Human activities", "outdoor", "street", lambda d: (d.rectangle([0, 280, 600, 400], fill=(180, 180, 185)), draw_person(d, 80, 170, (180, 40, 40)), draw_person(d, 160, 165, (40, 120, 60)), draw_person(d, 240, 175, (40, 40, 180)), draw_person(d, 350, 170, (200, 120, 20)))),
        ("park_dog.png", "Animals", "outdoor", "park", lambda d: (d.rectangle([0, 200, 600, 400], fill=(60, 140, 60)), draw_dog(d, 150, 220), draw_dog(d, 320, 230), draw_person(d, 460, 160))),
        ("office_workspace.png", "Electronics", "indoor", "office", lambda d: (d.rectangle([0, 180, 600, 400], fill=(180, 150, 110)), draw_laptop(d, 180, 140), draw_laptop(d, 360, 150))),
        ("living_room.png", "Architecture", "indoor", "living room", lambda d: (d.rectangle([0, 240, 600, 400], fill=(160, 120, 80)), d.rectangle([100, 180, 380, 270], fill=(60, 80, 140), outline=(20, 20, 20), width=3), d.rectangle([420, 190, 520, 270], fill=(140, 60, 60), outline=(20, 20, 20), width=3))),
        ("kitchen_appliances.png", "Food", "indoor", "kitchen", lambda d: (d.rectangle([0, 220, 600, 400], fill=(220, 220, 225)), d.rectangle([80, 60, 220, 320], fill=(200, 205, 215), outline=(50, 50, 50), width=3), d.rectangle([280, 120, 420, 220], fill=(50, 50, 60), outline=(100, 100, 100), width=3))),
        ("sports_cyclist.png", "Sports", "outdoor", "park", lambda d: (d.rectangle([0, 260, 600, 400], fill=(100, 100, 105)), d.ellipse([120, 230, 200, 310], outline=(30, 30, 30), width=5), d.ellipse([270, 230, 350, 310], outline=(30, 30, 30), width=5), draw_person(d, 200, 140, (210, 40, 40)))),
        ("nature_wildlife.png", "Animals", "outdoor", "forest", lambda d: (d.rectangle([0, 220, 600, 400], fill=(50, 120, 50)), draw_dog(d, 120, 220), draw_dog(d, 280, 210), d.ellipse([420, 80, 480, 110], fill=(80, 80, 90)))),
        ("motorcycle_street.png", "Vehicles", "outdoor", "street", lambda d: (d.rectangle([0, 250, 600, 400], fill=(70, 70, 75)), d.ellipse([100, 230, 170, 300], outline=(20, 20, 20), width=6), d.ellipse([250, 230, 320, 300], outline=(20, 20, 20), width=6), draw_person(d, 180, 130, (20, 20, 20)), draw_person(d, 420, 160, (200, 50, 50)))),
        ("dining_pizza.png", "Food", "indoor", "restaurant", lambda d: (d.rectangle([0, 160, 600, 400], fill=(160, 110, 70)), d.ellipse([180, 150, 420, 350], fill=(230, 170, 80), outline=(160, 60, 20), width=6), d.ellipse([220, 180, 250, 210], fill=(180, 20, 20)), d.ellipse([320, 240, 350, 270], fill=(180, 20, 20)), d.ellipse([280, 200, 310, 230], fill=(180, 20, 20)))),
        ("electronics_multimedia.png", "Electronics", "indoor", "living room", lambda d: (d.rectangle([0, 250, 600, 400], fill=(140, 130, 120)), d.rectangle([120, 50, 460, 230], fill=(20, 20, 25), outline=(80, 80, 80), width=5), draw_laptop(d, 180, 220))),
        ("crowded_transit.png", "Vehicles", "outdoor", "street", lambda d: (d.rectangle([0, 240, 600, 400], fill=(75, 75, 80)), d.rectangle([80, 120, 360, 260], fill=(220, 180, 30), outline=(20, 20, 20), width=4), draw_person(d, 390, 180), draw_person(d, 450, 175), draw_person(d, 510, 185))),
    ]

    for fname, category, env, scene, painter in scenes:
        bg_color = (200, 220, 240) if env == "outdoor" else (240, 235, 225)
        img = Image.new("RGB", (600, 400), color=bg_color)
        draw = ImageDraw.ImageDraw(img)
        painter(draw)
        # Add small caption watermark
        draw.text((15, 15), f"PixelMind Sample: {category} ({scene})", fill=(60, 60, 60))
        target_path = SAMPLE_DIR / fname
        img.save(target_path, "PNG")
        print(f"Generated {fname} ({category}, {scene})")


if __name__ == "__main__":
    generate_all_samples()
