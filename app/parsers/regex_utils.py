import re


def normalize_amount(raw_amt):
    """Normalize various formats of amount: (100), -100, 100 Cr/Dr, −100, etc."""
    if not raw_amt:
        return None

    amt = str(raw_amt).strip()

    # Remove currency symbols and commas
    amt = amt.replace("₹", "").replace("$", "").replace(",", "")
    amt = amt.replace("−", "-").replace("–", "-")  # Unicode minus and dash

    # Handle parentheses (negative)
    if amt.startswith("(") and amt.endswith(")"):
        amt = "-" + amt.strip("()")

    # Handle Dr/Cr suffix (case-insensitive)
    amt_lower = amt.lower()
    if amt_lower.endswith("dr"):
        amt = "-" + amt_lower[:-2].strip()
    elif amt_lower.endswith("cr"):
        amt = amt_lower[:-2].strip()

    amt = amt.strip()

    try:
        return float(amt)
    except ValueError:
        return None
