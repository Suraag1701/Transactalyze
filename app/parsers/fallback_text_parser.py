import re
import pandas as pd
from datetime import datetime
from dateutil import parser
from app.parsers.regex_utils import normalize_amount

# Extended date patterns
DATE_PATTERNS = [
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}", r"\b\d{2}/\d{2}/\d{2,4}\b",
    r"\b\d{2}-\d{2}-\d{2,4}\b", r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{2}\.\d{2}\.\d{4}\b", r"\b\d{2}-[A-Za-z]{3}-\d{2,4}\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{4}\b",
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b"
]

# Recognize amount (basic fallback)
AMOUNT_PATTERN = r"(-?\(?₹?\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?(?:Cr|Dr)?)"


def normalize_date(date_str):
    try:
        dt = parser.parse(date_str, dayfirst=False)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return date_str


def extract_date(line):
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, line)
        if match:
            return match.group(0)
    return None


def extract_desc_amount(line):
    # Clean line: remove leading/trailing quotes and normalize whitespace
    line = line.strip().strip('"').replace("“", "").replace("”", "")

    # Regex pattern:
    # Group 1 = description
    # Group 2 = amount (handles parentheses, commas, optional Cr/Dr)
    pattern = r"(.+?)\s+(\(?-?[\d,]+\.?\d*\)?(?:\s*(?:Cr|Dr))?)$"

    match = re.search(pattern, line)
    if match:
        desc = match.group(1).strip()
        amt = match.group(2).strip()
        # Additional logic: if 'Dr' is in description but not in amount
        if ("Dr" in desc and "Dr" not in amt):
            amt = "-" + amt
            desc = desc.replace("Dr", "").strip()
        elif ("Cr" in desc and "Cr" not in amt):
            desc = desc.replace("Cr", "").strip()
        return desc, amt

    return None, None


def extract_transactions_from_text(lines):
    transactions = []
    current_date = None

    for line in lines:
        print("\n====================")
        print("Original line:", line)

        line = line.strip()
        if not line or len(line) < 6:
            print("Skipped: Line too short or empty")
            continue

        date_candidate = extract_date(line)
        print("Extracted date:", date_candidate)

        if date_candidate:
            current_date = normalize_date(date_candidate)
            print("Normalized date:", current_date)
            line = line.replace(date_candidate, "").strip()

        desc, amt = extract_desc_amount(line)
        print("Extracted description:", desc)
        print("Extracted amount:", amt)

        normalized_amt = normalize_amount(amt)
        print("Normalized amount:", normalized_amt)

        if current_date and desc and normalized_amt is not None:
            transactions.append({
                "Date": current_date,
                "Description": desc,
                "Amount": normalized_amt,
                "Category": None
            })
            print("✅ Transaction added")
        else:
            print("❌ Transaction skipped - Missing required fields")

    return pd.DataFrame(transactions)


def parse_unstructured_text_block(raw_text: str) -> pd.DataFrame:
    lines = raw_text.split('\n')
    lines = [line.strip() for line in lines if len(line.strip()) > 5]

    if not lines:
        raise Exception("No usable lines found in uploaded file.")

    # UPDATED heuristic to catch more tabbed lines
    tabbed_line_count = sum(
        [1 for line in lines if len(re.findall(r"\S+", line)) >= 4])

    if tabbed_line_count >= 3:
        print("🧭 Routed to TAB-PARSER")
        df = extract_tabbed_transactions(lines)
    else:
        print("🧭 Routed to FALLBACK")
        df = extract_transactions_from_text(lines)

    if df.empty:
        raise Exception("No valid transactions could be parsed from the file.")

    return df


def extract_tabbed_transactions(lines):
    transactions = []
    current_date = None

    for line in lines:
        print("\n====================")
        print("Original line:", line)

        # Primary split: 2+ spaces (structured)
        parts = re.split(r'\s{2,}', line.strip())

        # Fallback: if parts too few, split by any whitespace
        if len(parts) < 3:
            parts = re.findall(r'\S+', line.strip().strip('"'))

        parts = [p.strip() for p in parts if p.strip()]
        print("Split parts:", parts)

        if len(parts) < 3:
            print("❌ Skipped - not enough parts")
            continue

        date_candidate = extract_date(parts[0])
        if date_candidate:
            current_date = normalize_date(date_candidate)

            # Attempt to extract the last numeric value (likely amount)
            potential_amounts = parts[1:]
            amount = None
            for val in reversed(potential_amounts):
                normalized = normalize_amount(val)
                if normalized is not None:
                    amount = val
                    break

            # Description is all remaining text after date and amount
            desc = " ".join(parts[1:]).replace(
                amount, "").strip() if amount else " ".join(parts[1:])

            print("Extracted date:", current_date)
            print("Extracted description:", desc)
            print("Extracted amount:", amount)

            normalized_amt = normalize_amount(amount)
            if current_date and desc and normalized_amt is not None:
                transactions.append({
                    "Date": current_date,
                    "Description": desc,
                    "Amount": normalized_amt,
                    "Category": None
                })
        else:
            print("❌ Skipped - could not detect date")

    return pd.DataFrame(transactions)
