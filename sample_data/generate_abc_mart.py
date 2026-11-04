"""Generate the exact ABC MART reference receipt from the presentation slides.

Receipt Details from PPT Slide 1 & Slide 7:
- Shop: ABC MART
- PIN: 580001
- Date: 03/11/2026
- Phone: 9876543210
- Email: abcmart@gmail.com
- Total: ₹1,250
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def get_font(size: int = 16, bold: bool = False) -> ImageFont.ImageFont:
    try:
        font_name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(font_name, size)
    except IOError:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except IOError:
            return ImageFont.load_default()

def generate_abc_mart_receipt(output_path: Path) -> Path:
    width, height = 520, 720
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_store = get_font(28, bold=True)
    f_sub = get_font(14)
    f_body = get_font(16)
    f_body_b = get_font(16, bold=True)
    f_total = get_font(24, bold=True)

    # Outer border/paper edge
    draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(220, 220, 215), width=2)

    # Store Header
    draw.text((180, 30), "ABC MART", fill=(17, 17, 17), font=f_store)
    draw.text((170, 72), "General & Grocery Retail", fill=(80, 80, 80), font=f_sub)
    draw.text((195, 95), "PIN: 580001", fill=(30, 30, 30), font=f_body_b)

    # Separator
    draw.line([(30, 130), (width - 30, 130)], fill=(180, 180, 180), width=1)

    # Receipt Metadata
    draw.text((35, 145), "Date: 03/11/2026", fill=(20, 20, 20), font=f_body_b)
    draw.text((300, 145), "Bill #: AB-9421", fill=(30, 30, 30), font=f_body)
    draw.text((35, 175), "Ph: 9876543210", fill=(20, 20, 20), font=f_body_b)
    draw.text((35, 205), "Email: abcmart@gmail.com", fill=(20, 20, 20), font=f_body_b)

    # Table Header
    draw.line([(30, 240), (width - 30, 240)], fill=(180, 180, 180), width=1)
    draw.text((35, 250), "ITEM DESCRIPTION", fill=(20, 20, 20), font=f_body_b)
    draw.text((340, 250), "QTY", fill=(20, 20, 20), font=f_body_b)
    draw.text((420, 250), "AMOUNT", fill=(20, 20, 20), font=f_body_b)
    draw.line([(30, 275), (width - 30, 275)], fill=(200, 200, 200), width=1)

    # Line Items
    items = [
        ("Sunflower Cooking Oil 1L", "1", "180.00"),
        ("Basmati Premium Rice 5kg", "1", "450.00"),
        ("Wheat Flour Atta 5kg", "1", "240.00"),
        ("Toor Dal 1kg", "2", "260.00"),
        ("Dairy Butter 200g", "1", "120.00"),
    ]

    y = 290
    for desc, qty, amt in items:
        draw.text((35, y), desc, fill=(40, 40, 40), font=f_body)
        draw.text((350, y), qty, fill=(50, 50, 50), font=f_body)
        draw.text((425, y), f"{amt}", fill=(30, 30, 30), font=f_body)
        y += 34

    # Subtotals & Taxes
    draw.line([(30, y + 10), (width - 30, y + 10)], fill=(180, 180, 180), width=1)
    y += 25
    draw.text((280, y), "Subtotal:", fill=(70, 70, 70), font=f_body)
    draw.text((425, y), "1250.00", fill=(30, 30, 30), font=f_body)
    y += 30
    draw.text((280, y), "GST (Included):", fill=(70, 70, 70), font=f_body)
    draw.text((425, y), "0.00", fill=(30, 30, 30), font=f_body)

    # TOTAL from PPT: TOTAL ₹1,250
    draw.line([(30, y + 15), (width - 30, y + 15)], fill=(17, 17, 17), width=2)
    y += 32
    draw.text((180, y), "TOTAL", fill=(17, 17, 17), font=f_total)
    draw.text((360, y), "INR 1,250", fill=(198, 40, 40), font=f_total)
    draw.line([(30, y + 38), (width - 30, y + 38)], fill=(17, 17, 17), width=2)

    # Footer
    y += 60
    draw.text((160, y), "THANK YOU FOR VISITING!", fill=(100, 100, 100), font=f_sub)
    draw.text((185, y + 22), "Please visit us again.", fill=(120, 120, 120), font=f_sub)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Generated ABC MART receipt at {output_path}")
    return output_path

if __name__ == "__main__":
    out_dir = Path("sample_data")
    generate_abc_mart_receipt(out_dir / "abc_mart_receipt.png")
    generate_abc_mart_receipt(out_dir / "receipt_1.png")
