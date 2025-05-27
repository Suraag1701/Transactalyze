import pandas as pd
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract
import re


def detect_header_row(df_raw):
    for i, row in df_raw.iterrows():
        row_lower = [str(cell).strip().lower() for cell in row.values]
        if ("description" in row_lower
                or "narration" in row_lower) and ("amount" in row_lower
                                                  or "debit" in row_lower
                                                  or "credit" in row_lower):
            return i
    return 0  # fallback if no match


def extract_transactions_from_lines(lines):
    transactions = []

    # Match: Date, Description, Amount, [Optional Category]
    pattern_with_cat = r"(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+\$([0-9,]+\.\d{2})\s+([A-Za-z &]+)$"
    pattern_without_cat = r"(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+\$([0-9,]+\.\d{2})"

    for line in lines:
        match_with_cat = re.search(pattern_with_cat, line)
        match_no_cat = re.search(pattern_without_cat, line)

        if match_with_cat:
            date, desc, amt, category = match_with_cat.groups()
        elif match_no_cat:
            date, desc, amt = match_no_cat.groups()
            category = None
        else:
            continue

        transactions.append({
            "Date": date,
            "Description": desc.strip(),
            "Amount": float(amt.replace(",", "")),
            "Category": category.strip() if category else None
        })

    return pd.DataFrame(transactions)


def parse_file(file):
    filename = file.filename.lower()

    if filename.endswith(".csv"):
        preview = pd.read_csv(file, header=None, nrows=20)
        file.seek(0)
        skip = detect_header_row(preview)
        return pd.read_csv(file, skiprows=skip)

    elif filename.endswith((".xlsx", ".xls")):
        preview = pd.read_excel(file, header=None, nrows=20)
        file.seek(0)
        skip = detect_header_row(preview)
        return pd.read_excel(file, skiprows=skip)

    elif filename.endswith(".pdf"):
        descriptions = []

        # Try pdfplumber first
        try:
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        lines = text.split('\n')
                        descriptions.extend([
                            line.strip() for line in lines
                            if len(line.strip()) > 5
                        ])
        except Exception as e:
            print(f"[pdfplumber] Failed: {e}")
            descriptions = []

        # OCR fallback
        if not descriptions:
            try:
                file.stream.seek(0)
                images = convert_from_bytes(file.read())
                for img in images:
                    text = pytesseract.image_to_string(img)
                    lines = text.split('\n')
                    descriptions.extend([
                        line.strip() for line in lines if len(line.strip()) > 5
                    ])
            except Exception as e:
                raise Exception(f"OCR PDF processing failed: {e}")

        if not descriptions:
            raise Exception(
                "Could not extract any transaction descriptions from the PDF.")

        # Parse structured transactions
        df = extract_transactions_from_lines(descriptions)

        if df.empty:
            raise Exception(
                "No valid transactions found in PDF after parsing.")

        return df

    else:
        raise Exception(
            "Unsupported file type. Please upload a .csv, .xlsx, or .pdf file."
        )
