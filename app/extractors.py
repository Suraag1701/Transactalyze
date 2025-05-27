import pandas as pd
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
import io
import os


def parse_file(file):
    filename = file.filename.lower()

    if filename.endswith(".csv"):
        return pd.read_csv(file)

    elif filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)

    elif filename.endswith(".pdf"):
        # Try extracting text using pdfplumber
        descriptions = []
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

        # If nothing found, try OCR
        if not descriptions:
            try:
                file.stream.seek(0)  # Reset stream
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

        return pd.DataFrame({'Description': descriptions})

    else:
        raise Exception(
            "Unsupported file type. Please upload a .csv, .xlsx, or .pdf file."
        )
