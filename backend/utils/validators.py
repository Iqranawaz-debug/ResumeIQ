from utils.constants import (
    ALLOWED_EXTENSIONS,
    ERROR_EMPTY_FILE,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_TYPE,
    ERROR_NO_FILE,
    MAX_FILE_SIZE_MB,
)


def validate_resume_file(filename: str | None, size_bytes: int):
    """Validate a resume file's type and size.

    Returns a (is_valid, error_message) tuple; error_message is None when valid.
    """
    if not filename:
        return False, ERROR_NO_FILE

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        return False, ERROR_INVALID_TYPE

    if size_bytes == 0:
        return False, ERROR_EMPTY_FILE

    size_mb = size_bytes / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return False, ERROR_FILE_TOO_LARGE

    return True, None
