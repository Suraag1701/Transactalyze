import os


def sanitize_filename(filename):
    """
    Removes extension and special characters to create a safe filename base.
    Example: "Bank Statement (March).xlsx" → "Bank_Statement_March"
    """
    name = os.path.splitext(filename)[0]  # Remove .csv, .pdf, etc.
    safe = "".join(c for c in name
                   if c.isalnum() or c in (' ', '-', '_')).strip()
    return safe.replace(" ", "_")
