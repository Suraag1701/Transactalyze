from flask import Blueprint, request, render_template, send_file, session, current_app, redirect, url_for
from uuid import uuid4
import pandas as pd
import io
from .extractors import parse_file
from .categorizer import categorize_transactions, DEFAULT_CATEGORIES
from .utils import sanitize_filename
import os
import hashlib
import xlsxwriter
from flask_limiter.util import get_remote_address
from flask_limiter import Limiter
from flask import render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import User
from . import db

limiter = Limiter(get_remote_address)

main = Blueprint("main", __name__)


@main.route("/", methods=["GET", "POST"])
@limiter.limit("5 per minute")  # ✅ Limit only this route
def index():
    result_file = None
    category_totals = None  # ⬅️ Initialize to default for GET

    if request.method == "POST":
        if request.form.get("website"):
            return render_template("index.html",
                                   error="⚠️ Bot-like activity detected.")

        file = request.files.get('file')
        if not file or file.filename == '':
            session["form_error"] = "⚠️ No file selected."
            return redirect(url_for("main.index") + "#get-started")

        # File type validation
        allowed_exts = ('.csv', '.xls', '.xlsx', '.pdf')
        if not file.filename.lower().endswith(allowed_exts):
            session[
                "form_error"] = "⚠️ Unsupported file type. Please upload a CSV, Excel, or PDF."
            return redirect(url_for("main.index") + "#get-started")

        # File size limit: 5MB
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        if file_length > 5 * 1024 * 1024:
            session["form_error"] = "⚠️ File size exceeds 5MB limit."
            return redirect(url_for("main.index") + "#get-started")

        try:
            df = parse_file(file)
            category_col = next(
                (col for col in df.columns
                 if col.lower() in ["category", "type", "tag"]), None)
            known_examples = df[[
                category_col, 'Description'
            ]].dropna().head(10).values.tolist() if category_col else []
        except Exception as e:
            session["form_error"] = f"⚠️ File processing error: {str(e)}"
            return redirect(url_for("main.index") + "#get-started")

        if 'Description' not in df.columns:
            session[
                "form_error"] = "⚠️ File must contain a 'Description' column."
            return redirect(url_for("main.index") + "#get-started")

        if len(df) > 50:
            session[
                "form_error"] = "⚠️ Free version is limited to 50 transactions per file."
            return redirect(url_for("main.index") + "#get-started")

        if 'Description' not in df.columns:
            session[
                "form_error"] = "⚠️ File must contain a 'Description' column."
            return redirect(url_for("main.index") + "#get-started")

        descriptions = df['Description'].fillna("").astype(str).tolist()

        hash_key = hashlib.sha256("".join(descriptions).encode()).hexdigest()

        if hash_key in current_app.config['HASHED_RESULTS']:
            df["AutoCategory_v1"] = current_app.config['HASHED_RESULTS'][
                hash_key]
        else:
            categories = categorize_transactions(
                descriptions,
                known_examples=known_examples,
                category_list=DEFAULT_CATEGORIES)
            current_app.config['HASHED_RESULTS'][hash_key] = categories
            df["AutoCategory_v1"] = categories

        # ⬅️ Compute category totals
        category_totals = df.groupby("AutoCategory_v1")["Amount"].sum().round(
            2).reset_index()
        category_totals.columns = ["Category", "Total"]
        session["category_totals"] = category_totals.to_dict(orient="records")

        file_format = request.form.get("format", "csv")

        if file_format == "xlsx":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Write the main transaction DataFrame
                df.to_excel(writer, index=False, sheet_name='Transactions')

                # Access workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Transactions']

                # Prepare category totals
                category_totals_df = df.groupby(
                    "AutoCategory_v1")["Amount"].sum().round(2).reset_index()
                category_totals_df.columns = ["Category", "Total"]

                # Determine where to place totals
                num_columns = len(df.columns)
                start_col = num_columns + 5  # 5 columns after the end of main table
                start_row = 2  # Start at row 3 (0-indexed)

                # Write headers
                worksheet.write(start_row, start_col, "Category")
                worksheet.write(start_row, start_col + 1, "Total")

                # Write category totals
                for i, row in category_totals_df.iterrows():
                    worksheet.write(start_row + 1 + i, start_col,
                                    row["Category"])
                    worksheet.write(start_row + 1 + i, start_col + 1,
                                    row["Total"])

            output.seek(0)
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename_out = sanitize_filename(
                file.filename) + "_Categorized.xlsx"
        else:
            output = io.StringIO()
            df.to_csv(output, index=False, quoting=1)

            # Append a separator and the category totals
            output.write("\n\nCategory Totals\n")

            category_totals_df = df.groupby(
                "AutoCategory_v1")["Amount"].sum().round(2).reset_index()
            category_totals_df.columns = ["Category", "Total"]
            category_totals_df.to_csv(output, index=False)

            output.seek(0)

            mime_type = "text/csv"
            filename_out = sanitize_filename(
                file.filename) + "_Categorized.csv"

        file_id = str(uuid4())

        current_app.config['PROCESSED_FILES'][file_id] = {
            "filename": filename_out,
            "content": output.getvalue() if file_format == "csv" else output,
            "mimetype": mime_type,
            "binary": file_format == "xlsx"
        }

        session.permanent = True
        session.setdefault("history", []).append({
            "id": file_id,
            "name": filename_out
        })
        session.modified = True
        session["categorized_data"] = df[[
            "Date", "Description", "Amount", "AutoCategory_v1"
        ]].to_dict(orient="records")

        return redirect(url_for("main.index", result=file_id))

    # ⬅️ Handle result after redirect
    result_file_id = request.args.get("result")
    # categorized_data = session.get("categorized_data")
    parsed_preview = None
    if result_file_id:
        file_info = current_app.config['PROCESSED_FILES'].get(result_file_id)
        if file_info:
            result_file = {"id": result_file_id, "name": file_info["filename"]}
            category_totals = session.get("category_totals")
            preview_data = session.get("categorized_data")
            if preview_data:
                parsed_preview = preview_data[:8]  # only show top 8 rows

    response = render_template("index.html",
                               result_file=result_file,
                               category_totals=category_totals,
                               parsed_preview=parsed_preview)

    # Clean up session keys (safe to call after render)
    session.pop("categorized_data", None)
    session.pop("category_totals", None)

    return response


@main.route("/history/<file_id>")
def download_from_history(file_id):
    file_info = current_app.config['PROCESSED_FILES'].get(file_id)
    if not file_info:
        return "File not found or expired.", 404

    content = io.BytesIO(file_info["content"].encode(
    )) if not file_info.get("binary") else file_info["content"]

    return send_file(content,
                     mimetype=file_info.get("mimetype", "text/csv"),
                     as_attachment=True,
                     download_name=file_info["filename"])


@main.route("/privacy")
def privacy():
    return render_template("privacy.html")


@main.route("/feedback")
def feedback():
    return render_template("feedback.html")


@main.route("/about")
def about():
    return render_template("about.html")


@main.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Check if user exists
        user = User.query.filter_by(email=email).first()
        if user:
            flash("Email already exists. Please log in.", "warning")
            return redirect(url_for("main.login"))

        # Create new user
        new_user = User(email=email,
                        password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash("Account created successfully!", "success")
        return redirect(url_for("main.index"))

    return render_template("signup.html")


@main.route("/login")
def login():
    return render_template("login.html")


@main.route("/sample")
def load_sample():
    import os
    import time
    import csv
    from io import StringIO
    from uuid import uuid4
    from markupsafe import Markup

    # Load pre-processed categorized file from /static/
    sample_path = os.path.join(current_app.static_folder,
                               "sample_categorized.csv")
    with open(sample_path, "r") as f:
        content = f.read()

    file_id = str(uuid4())
    filename_out = "Sample_Categorized.csv"

    # Parse the CSV content to build preview
    reader = csv.DictReader(StringIO(content))
    parsed_preview = list(reader)[:10]

    # Add to in-memory store
    current_app.config['PROCESSED_FILES'][file_id] = {
        "filename": filename_out,
        "content": content,
        "mimetype": "text/csv",
        "binary": False
    }

    # Add to session history
    session.permanent = True
    session.setdefault("history", []).append({
        "id": file_id,
        "name": filename_out
    })
    session.modified = True

    # Optional delay to mimic real processing
    time.sleep(1)

    # Render index with sample preview
    result_file = type("Result", (), {})()
    result_file.id = file_id
    result_file.name = filename_out

    return render_template(
        "index.html",
        parsed_preview=parsed_preview,
        result_file=result_file,
        sample_route_fix=Markup(
            "<script>window.history.replaceState({}, '', '/');</script>"))
