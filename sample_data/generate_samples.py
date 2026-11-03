"""Generate synthetic document photographs for end-to-end testing and demonstration.

Creates realistic receipts, student identification cards, and generic tables
using PIL image rendering.
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SAMPLE_DIR = Path(__file__).resolve().parent


def _get_font(size: int = 16) -> ImageFont.ImageFont:
    """Attempt to load standard TrueType font with fallback to default."""
    try:
        # Standard fonts available across Windows platforms
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        return ImageFont.load_default()


def generate_receipt_1(output_path: Path) -> None:
    """Generate sample grocery receipt image."""
    img = Image.new("RGB", (500, 700), color=(252, 252, 250))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(22)
    f_body = _get_font(15)
    f_bold = _get_font(17)

    draw.text((120, 30), "ACME SUPERMARKET", fill=(17, 17, 17), font=f_title)
    draw.text((150, 65), "123 Market Street, City", fill=(80, 80, 80), font=f_body)
    draw.text((170, 90), "Tel: 555-0199", fill=(80, 80, 80), font=f_body)

    draw.line([(30, 125), (470, 125)], fill=(180, 180, 180), width=1)
    draw.text((35, 140), "Invoice #: INV-2024-8841", fill=(20, 20, 20), font=f_body)
    draw.text((35, 165), "Date: 2024-10-15", fill=(20, 20, 20), font=f_body)
    draw.text((35, 190), "Payment: Credit Card", fill=(20, 20, 20), font=f_body)

    draw.line([(30, 220), (470, 220)], fill=(180, 180, 180), width=1)
    draw.text((35, 230), "ITEMS", fill=(20, 20, 20), font=f_bold)
    draw.text((400, 230), "PRICE", fill=(20, 20, 20), font=f_bold)

    items = [
        ("Organic Whole Milk 1 Gal", "4.50"),
        ("Sourdough Artisan Bread", "3.80"),
        ("Roasted Almonds 250g", "6.20"),
        ("Fair Trade Dark Chocolate", "2.90"),
    ]
    y = 265
    for name, price in items:
        draw.text((35, y), name, fill=(40, 40, 40), font=f_body)
        draw.text((410, y), f"${price}", fill=(40, 40, 40), font=f_body)
        y += 32

    draw.line([(30, y + 10), (470, y + 10)], fill=(180, 180, 180), width=1)
    y += 25
    draw.text((250, y), "Tax (8.25%):", fill=(50, 50, 50), font=f_body)
    draw.text((410, y), "$1.44", fill=(50, 50, 50), font=f_body)

    y += 30
    draw.text((250, y), "Grand Total:", fill=(198, 40, 40), font=f_bold)
    draw.text((405, y), "$18.84", fill=(198, 40, 40), font=f_bold)

    draw.line([(30, y + 40), (470, y + 40)], fill=(180, 180, 180), width=1)
    draw.text((150, y + 60), "THANK YOU FOR SHOPPING!", fill=(100, 100, 100), font=f_body)

    img.save(output_path)


def generate_receipt_2(output_path: Path) -> None:
    """Generate sample coffee shop receipt."""
    img = Image.new("RGB", (450, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(20)
    f_body = _get_font(14)
    f_bold = _get_font(16)

    draw.text((110, 30), "STAR CAFE & BAKERY", fill=(20, 20, 20), font=f_title)
    draw.text((140, 60), "Receipt: RCP-90214", fill=(90, 90, 90), font=f_body)
    draw.text((155, 85), "Date: 2024-11-01", fill=(90, 90, 90), font=f_body)

    draw.line([(30, 115), (420, 115)], fill=(200, 200, 200), width=1)
    draw.text((35, 130), "Caramel Macchiato", fill=(30, 30, 30), font=f_body)
    draw.text((360, 130), "$5.50", fill=(30, 30, 30), font=f_body)

    draw.text((35, 160), "Blueberry Muffin", fill=(30, 30, 30), font=f_body)
    draw.text((360, 160), "$3.75", fill=(30, 30, 30), font=f_body)

    draw.line([(30, 200), (420, 200)], fill=(200, 200, 200), width=1)
    draw.text((220, 220), "Sales Tax:", fill=(60, 60, 60), font=f_body)
    draw.text((360, 220), "$0.74", fill=(60, 60, 60), font=f_body)

    draw.text((220, 250), "Total Amount:", fill=(198, 40, 40), font=f_bold)
    draw.text((355, 250), "$9.99", fill=(198, 40, 40), font=f_bold)
    draw.text((35, 290), "Payment Method: Cash", fill=(60, 60, 60), font=f_body)

    img.save(output_path)


def generate_invoice_1(output_path: Path) -> None:
    """Generate corporate consulting service invoice."""
    img = Image.new("RGB", (650, 750), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(24)
    f_body = _get_font(15)
    f_bold = _get_font(17)

    # Top header banner
    draw.rectangle([(0, 0), (650, 80)], fill=(17, 17, 17))
    draw.text((30, 25), "APEX CONSULTING GROUP", fill=(255, 255, 255), font=f_title)

    draw.text((30, 110), "Vendor: Apex Consulting LLC", fill=(30, 30, 30), font=f_bold)
    draw.text((30, 140), "Invoice Number: INV-77210", fill=(50, 50, 50), font=f_body)
    draw.text((30, 165), "Date: 2024-09-20", fill=(50, 50, 50), font=f_body)
    draw.text((30, 190), "Payment Method: Bank Transfer", fill=(50, 50, 50), font=f_body)

    draw.rectangle([(30, 230), (620, 265)], fill=(245, 245, 245))
    draw.text((45, 240), "Service Description", fill=(20, 20, 20), font=f_bold)
    draw.text((500, 240), "Amount", fill=(20, 20, 20), font=f_bold)

    draw.text((45, 280), "Cloud Architecture Assessment", fill=(40, 40, 40), font=f_body)
    draw.text((500, 280), "$1200.00", fill=(40, 40, 40), font=f_body)

    draw.text((45, 315), "Security & Compliance Review", fill=(40, 40, 40), font=f_body)
    draw.text((500, 315), "$850.00", fill=(40, 40, 40), font=f_body)

    draw.line([(30, 370), (620, 370)], fill=(200, 200, 200), width=1)
    draw.text((380, 390), "Tax Amount:", fill=(50, 50, 50), font=f_body)
    draw.text((500, 390), "$164.00", fill=(50, 50, 50), font=f_body)

    draw.text((380, 425), "Total Amount:", fill=(198, 40, 40), font=f_bold)
    draw.text((495, 425), "$2214.00", fill=(198, 40, 40), font=f_bold)

    img.save(output_path)


def generate_student_id_1(output_path: Path) -> None:
    """Generate university student identification credential."""
    img = Image.new("RGB", (600, 380), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(20)
    f_body = _get_font(15)
    f_bold = _get_font(16)

    # University header
    draw.rectangle([(0, 0), (600, 65)], fill=(198, 40, 40))
    draw.text((120, 18), "METROPOLITAN UNIVERSITY", fill=(255, 255, 255), font=f_title)

    # Photo placeholder badge
    draw.rectangle([(30, 95), (170, 255)], fill=(230, 230, 230), outline=(180, 180, 180))
    draw.text((70, 165), "[PHOTO]", fill=(120, 120, 120), font=f_body)

    # Identity details
    draw.text((200, 95), "STUDENT IDENTITY CARD", fill=(100, 100, 100), font=f_bold)
    draw.text((200, 130), "Full Name: Sarah Jenkins", fill=(20, 20, 20), font=f_bold)
    draw.text((200, 160), "ID Number: STU-84920", fill=(30, 30, 30), font=f_body)
    draw.text((200, 190), "Date of Birth: 2002-05-14", fill=(30, 30, 30), font=f_body)
    draw.text((200, 220), "Institution: Metropolitan University", fill=(30, 30, 30), font=f_body)
    draw.text((200, 250), "Valid Until: 2026-06-30", fill=(30, 30, 30), font=f_body)
    draw.text((200, 280), "Blood Group: O+", fill=(198, 40, 40), font=f_bold)

    draw.rectangle([(0, 350), (600, 380)], fill=(17, 17, 17))
    img.save(output_path)


def generate_table_1(output_path: Path) -> None:
    """Generate generic tabular document sheet."""
    img = Image.new("RGB", (650, 500), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(21)
    f_body = _get_font(14)
    f_bold = _get_font(15)

    draw.text((30, 30), "QUARTERLY INVENTORY AUDIT", fill=(17, 17, 17), font=f_title)
    draw.text((30, 65), "Table Title: Hardware Asset Log", fill=(60, 60, 60), font=f_bold)
    draw.text((30, 90), "Record Date: 2024-11-02", fill=(60, 60, 60), font=f_body)
    draw.text((30, 115), "Total Rows: 4", fill=(60, 60, 60), font=f_body)
    draw.text((30, 140), "Summary: Routine laboratory inventory count", fill=(80, 80, 80), font=f_body)

    # Table grid
    draw.rectangle([(30, 180), (620, 215)], fill=(240, 240, 240))
    draw.text((45, 190), "Item Code", fill=(20, 20, 20), font=f_bold)
    draw.text((200, 190), "Description", fill=(20, 20, 20), font=f_bold)
    draw.text((400, 190), "Qty", fill=(20, 20, 20), font=f_bold)
    draw.text((500, 190), "Unit Price", fill=(20, 20, 20), font=f_bold)

    rows = [
        ("HW-01", "27-inch 4K Monitor", "12", "$299.00"),
        ("HW-02", "Ergonomic Keyboard", "25", "$79.00"),
        ("HW-03", "USB-C Multiport Dock", "18", "$89.50"),
        ("HW-04", "Wireless Mouse Gray", "30", "$34.00"),
    ]
    y = 230
    for code, desc, qty, price in rows:
        draw.text((45, y), code, fill=(40, 40, 40), font=f_body)
        draw.text((200, y), desc, fill=(40, 40, 40), font=f_body)
        draw.text((410, y), qty, fill=(40, 40, 40), font=f_body)
        draw.text((500, y), price, fill=(40, 40, 40), font=f_body)
        draw.line([(30, y + 25), (620, y + 25)], fill=(230, 230, 230), width=1)
        y += 35

    img.save(output_path)


def generate_all_samples() -> None:
    """Generate all 5 sample images into the sample_data directory."""
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    generate_receipt_1(SAMPLE_DIR / "receipt_1.png")
    generate_receipt_2(SAMPLE_DIR / "receipt_2.png")
    generate_invoice_1(SAMPLE_DIR / "invoice_1.png")
    generate_student_id_1(SAMPLE_DIR / "student_id_1.png")
    generate_table_1(SAMPLE_DIR / "table_1.png")
    print(f"Generated 5 sample images in {SAMPLE_DIR}")


if __name__ == "__main__":
    generate_all_samples()
