"""Synthetic labelled dataset generator for evaluation and benchmarking.

Produces 15 ground-truth labelled synthetic document photographs (5 receipts,
5 student marksheets, 5 business cards) and outputs ground_truth.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

LABELLED_DIR = Path(__file__).resolve().parent


def _get_font(size: int = 16) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        return ImageFont.load_default()


def build_receipt(path: Path, data: dict) -> None:
    img = Image.new("RGB", (480, 680), color=(252, 252, 250))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(20)
    f_body = _get_font(14)
    f_bold = _get_font(15)

    draw.text((40, 30), data["shop_name"].upper(), fill=(17, 17, 17), font=f_title)
    draw.text((40, 65), f"Phone: {data['phone']}", fill=(80, 80, 80), font=f_body)
    draw.line([(30, 95), (450, 95)], fill=(180, 180, 180), width=1)

    draw.text((35, 110), f"Receipt #: {data['receipt_number']}", fill=(30, 30, 30), font=f_body)
    draw.text((35, 135), f"Date: {data['date']}", fill=(30, 30, 30), font=f_body)

    draw.line([(30, 165), (450, 165)], fill=(180, 180, 180), width=1)
    draw.text((35, 175), "ITEMS / DETAILS", fill=(20, 20, 20), font=f_bold)

    y = 205
    items = data.get("items", [("Standard Purchase Item", "1", data["subtotal"])])
    for item_name, qty, pr in items:
        draw.text((35, y), str(item_name), fill=(40, 40, 40), font=f_body)
        draw.text((380, y), f"${pr:.2f}", fill=(40, 40, 40), font=f_body)
        y += 30

    draw.line([(30, y + 10), (450, y + 10)], fill=(180, 180, 180), width=1)
    y += 25
    draw.text((240, y), f"Subtotal: ${data['subtotal']:.2f}", fill=(50, 50, 50), font=f_body)
    y += 25
    draw.text((240, y), f"Tax: ${data['tax_amount']:.2f}", fill=(50, 50, 50), font=f_body)
    y += 30
    draw.text((240, y), f"TOTAL: ${data['total_amount']:.2f}", fill=(17, 17, 17), font=f_bold)

    img.save(path)


def build_student_marksheet(path: Path, data: dict) -> None:
    img = Image.new("RGB", (560, 680), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(18)
    f_body = _get_font(13)
    f_bold = _get_font(14)

    draw.rectangle([(20, 20), (540, 660)], outline=(17, 24, 39), width=2)
    draw.text((40, 35), data["college"].upper(), fill=(17, 24, 39), font=f_title)
    draw.text((40, 65), "STATEMENT OF MARKS / GRADE CARD", fill=(100, 100, 100), font=f_body)
    draw.line([(30, 95), (530, 95)], fill=(200, 200, 200), width=1)

    draw.text((40, 110), f"Student Name: {data['name']}", fill=(20, 20, 20), font=f_bold)
    draw.text((40, 135), f"USN: {data['usn']}", fill=(20, 20, 20), font=f_bold)
    draw.text((40, 160), f"Semester: {data['semester']}", fill=(40, 40, 40), font=f_body)

    draw.line([(30, 190), (530, 190)], fill=(200, 200, 200), width=1)
    draw.text((40, 200), "SUBJECT / CODE", fill=(20, 20, 20), font=f_bold)
    draw.text((420, 200), "MARKS / MAX", fill=(20, 20, 20), font=f_bold)

    y = 230
    subjects = [
        ("CS501 Software Architecture", "88 / 100"),
        ("CS502 Database Management", "92 / 100"),
        ("CS503 Operating Systems", "85 / 100"),
        ("CS504 Computer Networks", "89 / 100"),
    ]
    for s_name, s_m in subjects:
        draw.text((40, y), s_name, fill=(50, 50, 50), font=f_body)
        draw.text((430, y), s_m, fill=(50, 50, 50), font=f_body)
        y += 28

    draw.line([(30, y + 10), (530, y + 10)], fill=(200, 200, 200), width=1)
    y += 25
    draw.text((40, y), f"Total Marks: {data['total_marks']:.0f}", fill=(20, 20, 20), font=f_body)
    draw.text((220, y), f"Percentage: {data['percentage']:.1f}%", fill=(20, 20, 20), font=f_bold)
    draw.text((400, y), f"Result: {data['result']}", fill=(16, 185, 129), font=f_bold)

    img.save(path)


def build_business_card(path: Path, data: dict) -> None:
    img = Image.new("RGB", (600, 360), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(22)
    f_role = _get_font(14)
    f_company = _get_font(18)
    f_body = _get_font(12)

    draw.rectangle([(15, 15), (585, 345)], outline=(209, 213, 219), width=1)
    draw.rectangle([(15, 15), (28, 345)], fill=(198, 40, 40))

    draw.text((50, 45), data["person_name"], fill=(17, 24, 39), font=f_title)
    draw.text((50, 80), data["designation"], fill=(198, 40, 40), font=f_role)

    draw.line([(50, 115), (550, 115)], fill=(229, 231, 235), width=1)
    draw.text((50, 130), data["company_name"], fill=(17, 24, 39), font=f_company)

    draw.text((50, 180), f"Phone: {data['phone']}", fill=(75, 85, 99), font=f_body)
    draw.text((50, 210), f"Email: {data['email']}", fill=(75, 85, 99), font=f_body)
    draw.text((50, 240), f"Website: {data['website']}", fill=(75, 85, 99), font=f_body)
    draw.text((50, 270), f"Address: {data['address']}", fill=(107, 114, 128), font=f_body)

    img.save(path)


def main():
    ground_truth = {}

    receipts_data = [
        {"file": "receipt_01.png", "shop_name": "Apex Supermarket", "receipt_number": "RCP-101", "date": "2024-05-12", "phone": "555-0101", "subtotal": 25.00, "tax_amount": 2.06, "total_amount": 27.06},
        {"file": "receipt_02.png", "shop_name": "Metro Electronics", "receipt_number": "RCP-102", "date": "2024-06-20", "phone": "555-0102", "subtotal": 150.00, "tax_amount": 12.00, "total_amount": 162.00},
        {"file": "receipt_03.png", "shop_name": "City Cafe Bistro", "receipt_number": "RCP-103", "date": "2024-07-04", "phone": "555-0103", "subtotal": 18.50, "tax_amount": 1.50, "total_amount": 20.00},
        {"file": "receipt_04.png", "shop_name": "Green Grocery Mart", "receipt_number": "RCP-104", "date": "2024-08-15", "phone": "555-0104", "subtotal": 42.00, "tax_amount": 3.50, "total_amount": 45.50},
        {"file": "receipt_05.png", "shop_name": "Urban Bookstore", "receipt_number": "RCP-105", "date": "2024-09-01", "phone": "555-0105", "subtotal": 35.00, "tax_amount": 2.80, "total_amount": 37.80},
    ]

    for item in receipts_data:
        p = LABELLED_DIR / item["file"]
        build_receipt(p, item)
        ground_truth[item["file"]] = {
            "category": "receipts",
            "ground_truth": {
                "shop_name": item["shop_name"],
                "receipt_number": item["receipt_number"],
                "date": item["date"],
                "phone": item["phone"],
                "subtotal": item["subtotal"],
                "tax_amount": item["tax_amount"],
                "total_amount": item["total_amount"],
            }
        }

    students_data = [
        {"file": "student_01.png", "name": "Alex Johnson", "usn": "1MS21CS001", "college": "City Institute of Technology", "semester": "5th Sem", "total_marks": 450.0, "percentage": 90.0, "result": "DISTINCTION"},
        {"file": "student_02.png", "name": "Priya Sharma", "usn": "1MS21CS045", "college": "National Engineering College", "semester": "6th Sem", "total_marks": 410.0, "percentage": 82.0, "result": "FIRST CLASS"},
        {"file": "student_03.png", "name": "Michael Brown", "usn": "1MS21CS078", "college": "State University", "semester": "4th Sem", "total_marks": 380.0, "percentage": 76.0, "result": "FIRST CLASS"},
        {"file": "student_04.png", "name": "Deepa Nair", "usn": "1MS21CS092", "college": "City Institute of Technology", "semester": "5th Sem", "total_marks": 465.0, "percentage": 93.0, "result": "DISTINCTION"},
        {"file": "student_05.png", "name": "Rahul Verma", "usn": "1MS21CS110", "college": "Apex Institute of Technology", "semester": "6th Sem", "total_marks": 350.0, "percentage": 70.0, "result": "SECOND CLASS"},
    ]

    for item in students_data:
        p = LABELLED_DIR / item["file"]
        build_student_marksheet(p, item)
        ground_truth[item["file"]] = {
            "category": "students",
            "ground_truth": {
                "name": item["name"],
                "usn": item["usn"],
                "college": item["college"],
                "semester": item["semester"],
                "total_marks": item["total_marks"],
                "percentage": item["percentage"],
                "result": item["result"],
            }
        }

    cards_data = [
        {"file": "card_01.png", "person_name": "John Doe", "designation": "Senior Software Engineer", "company_name": "TechCorp Solutions", "phone": "+1-555-234-5678", "email": "john.doe@techcorp.com", "website": "www.techcorp.com", "address": "100 Silicon Way, Tech Park"},
        {"file": "card_02.png", "person_name": "Sarah Miller", "designation": "Marketing Director", "company_name": "Horizon Media", "phone": "+1-555-345-6789", "email": "sarah.miller@horizonmedia.com", "website": "www.horizonmedia.com", "address": "25 Broadway Ave, New York"},
        {"file": "card_03.png", "person_name": "David Lee", "designation": "Managing Partner", "company_name": "Lee Financial Consultants", "phone": "+1-555-456-7890", "email": "david.lee@leefinancial.com", "website": "www.leefinancial.com", "address": "500 Wall Street, Financial District"},
        {"file": "card_04.png", "person_name": "Emma Watson", "designation": "Creative Lead", "company_name": "Studio Design Labs", "phone": "+1-555-567-8901", "email": "emma.watson@studiodesign.com", "website": "www.studiodesign.com", "address": "12 Art Studio Lane, Seattle"},
        {"file": "card_05.png", "person_name": "Robert Chen", "designation": "Chief Executive Officer", "company_name": "Apex Robotics Inc", "phone": "+1-555-678-9012", "email": "robert.chen@apexrobotics.com", "website": "www.apexrobotics.com", "address": "77 Robotics Boulevard, Boston"},
    ]

    for item in cards_data:
        p = LABELLED_DIR / item["file"]
        build_business_card(p, item)
        ground_truth[item["file"]] = {
            "category": "business_cards",
            "ground_truth": {
                "person_name": item["person_name"],
                "designation": item["designation"],
                "company_name": item["company_name"],
                "phone": item["phone"],
                "email": item["email"],
                "website": item["website"],
                "address": item["address"],
            }
        }

    gt_path = LABELLED_DIR / "ground_truth.json"
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Successfully generated 15 labelled images and ground_truth.json in {LABELLED_DIR}")


if __name__ == "__main__":
    main()
