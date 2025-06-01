import pandas as pd
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract
import re
from app.parsers.fallback_text_parser import parse_unstructured_text_block
import logging


def detect_header_row(df_raw):
    for i, row in df_raw.iterrows():
        row_lower = [str(cell).strip().lower() for cell in row.values]
        if ("description" in row_lower
                or "narration" in row_lower) and ("amount" in row_lower
                                                  or "debit" in row_lower
                                                  or "credit" in row_lower):
            return i
    return 0  # fallback if no match


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
            logging.warning(f"[pdfplumber] Failed: {e}")
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
        raw_text = "\n".join(descriptions)
        df = parse_unstructured_text_block(raw_text)

        if df.empty:
            raise Exception(
                "No valid transactions found in PDF after parsing.")
        return df

    else:
        raise Exception(
            "Unsupported file type. Please upload a .csv, .xlsx, or .pdf file."
        )
