import zipfile
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError

MAX_RESUME_SIZE = 5 * 1024 * 1024
ALLOWED_RESUME_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}
OLE_COMPOUND_FILE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


def validate_resume_file(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_RESUME_TYPES:
        raise ValidationError("Upload a PDF, DOC, or DOCX resume.")

    if uploaded_file.size > MAX_RESUME_SIZE:
        raise ValidationError("Resume files must be 5 MB or smaller.")

    content_type = getattr(uploaded_file, "content_type", None)
    if content_type and content_type not in ALLOWED_RESUME_TYPES[extension]:
        raise ValidationError("The uploaded file type does not match its extension.")

    uploaded_file.seek(0)
    signature = uploaded_file.read(8)
    uploaded_file.seek(0)

    if extension == ".pdf" and not signature.startswith(b"%PDF-"):
        raise ValidationError("The file does not contain a valid PDF signature.")
    if extension == ".doc" and signature != OLE_COMPOUND_FILE_SIGNATURE:
        raise ValidationError("The file does not contain a valid DOC signature.")
    if extension == ".docx":
        try:
            with zipfile.ZipFile(uploaded_file) as archive:
                entries = archive.infolist()
                names = {entry.filename for entry in entries}
                total_uncompressed_size = sum(entry.file_size for entry in entries)
        except (OSError, zipfile.BadZipFile) as error:
            raise ValidationError(
                "The file does not contain a valid DOCX document."
            ) from error
        finally:
            uploaded_file.seek(0)

        if (
            "[Content_Types].xml" not in names
            or "word/document.xml" not in names
            or len(entries) > 1000
            or total_uncompressed_size > 25 * 1024 * 1024
        ):
            raise ValidationError("The file does not contain a valid DOCX document.")

    uploaded_file.seek(0)


def resume_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"resumes/{instance.user_id}/{uuid4().hex}{extension}"
