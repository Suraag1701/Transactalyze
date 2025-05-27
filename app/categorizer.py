import openai
import os

# Load API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Default 10 categories (used in free tier)
DEFAULT_CATEGORIES = [
    "Groceries", "Dining & Takeout", "Housing & Utilities", "Transportation",
    "Health & Wellness", "Entertainment", "Shopping & Retail", "Travel",
    "Income", "Miscellaneous"
]


def normalize_category(raw, category_list):
    """Match raw GPT output to closest valid category from list."""
    raw_clean = raw.strip().lower()
    for valid in category_list:
        if raw_clean == valid.lower() or valid.lower() in raw_clean:
            return valid
    return "Miscellaneous"


def categorize_transactions(descriptions,
                            known_examples=None,
                            category_list=None):
    categorized = []
    known_examples = known_examples or []
    category_list = category_list or DEFAULT_CATEGORIES

    # Build example context string if any
    example_str = ""
    if known_examples:
        example_str += "Here are known transaction descriptions and their categories:\n"
        for cat, desc in known_examples:
            example_str += f'- "{desc}" → "{cat}"\n'
        example_str += "\nFollow this pattern and categorize the transaction below:\n"

    # Create system message based on category list
    system_message = (
        "Your task is to act as a transaction categorizer for a personal finance app. "
        "You must choose the most appropriate category for each transaction description.\n\n"
        "Use only one of the following categories:\n" +
        ", ".join(category_list) + "\n\n"
        "Return only the category name. Do not explain or add anything else. "
        "If the description clearly doesn’t fit any category, then and only then return: Miscellaneous."
    )

    for desc in descriptions:
        try:
            user_prompt = (
                example_str +
                f'Transaction description: {desc}\nCategory (choose only from the above list):'
            )
            messages = [{
                "role": "system",
                "content": system_message
            }, {
                "role": "user",
                "content": user_prompt
            }]
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=10,
                temperature=0.2,
            )
            raw_category = response.choices[0].message.content.strip()
            category = normalize_category(raw_category, category_list)
            categorized.append(category)

        except Exception as e:
            print(f"OpenAI error for '{desc}': {e}")
            categorized.append("Miscellaneous")

    return categorized
