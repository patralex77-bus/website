from __future__ import annotations

import uuid
from pathlib import Path
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import current_app


def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def save_uploaded_image(file: FileStorage | None) -> tuple[str | None, str | None]:
    if not file or not file.filename:
        return None, None

    if not allowed_file(file.filename):
        raise ValueError("Unsupported file type. Allowed: jpg, jpeg, png, webp, gif.")

    original_name = secure_filename(file.filename)
    suffix = Path(original_name).suffix.lower()
    filename = f"{uuid.uuid4().hex}{suffix}"

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    full_path = upload_dir / filename
    file.save(full_path)

    return f"uploads/{filename}", original_name
