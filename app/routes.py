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

limiter = Limiter(get_remote_address)

main = Blueprint("main", __name__)


@main.route("/", methods=["GET", "POST"])
@limiter.limit("5 per minute")  # ✅ Limit only this route
def index():
    result_file = None

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

        file_format = request.form.get("format", "csv")

        if file_format == "xlsx":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Transactions')
            output.seek(0)
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename_out = sanitize_filename(
                file.filename) + "_Categorized.xlsx"
        else:
            output = io.StringIO()
            df.to_csv(output, index=False, quoting=1)
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

        return redirect(url_for("main.index", result=file_id) + "#get-started")

    result_file_id = request.args.get("result")
    if result_file_id:
        file_info = current_app.config['PROCESSED_FILES'].get(result_file_id)
        if file_info:
            result_file = {"id": result_file_id, "name": file_info["filename"]}

    return render_template("index.html", result_file=result_file)


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


@main.route("/sample")
def load_sample():
    from .utils import sanitize_filename
    import io
    from uuid import uuid4
    import time

    # Load pre-processed categorized file from /static/
    with open(
            os.path.join(current_app.static_folder, "sample_categorized.csv"),
            "r") as f:
        content = f.read()

    file_id = str(uuid4())
    filename_out = "Sample_Categorized.csv"

    current_app.config['PROCESSED_FILES'][file_id] = {
        "filename": filename_out,
        "content": content,
        "mimetype": "text/csv",
        "binary": False
    }

    session.permanent = True
    session.setdefault("history", []).append({
        "id": file_id,
        "name": filename_out
    })
    session.modified = True
    time.sleep(3)
    return redirect(url_for("main.index", result=file_id) + "#get-started")
