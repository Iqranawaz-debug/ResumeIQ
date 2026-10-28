from io import BytesIO
from zipfile import ZipFile, BadZipFile

from fastapi import HTTPException
from utils import limits


async def read_upload(file, allowed, maximum):
    extension = (file.filename or "").rsplit(".", 1)[-1].lower()
    if not file.filename or "." not in file.filename or extension not in allowed:
        raise HTTPException(415, "Supported formats: " + ", ".join(allowed) + ".")
    if file.size is not None and file.size > maximum:
        raise HTTPException(413, "File exceeds the configured size limit.")
    content = bytearray()
    while chunk := await file.read(min(65536, maximum + 1 - len(content))):
        content.extend(chunk)
        if len(content) > maximum:
            raise HTTPException(413, "File exceeds the configured size limit.")
    if not content:
        raise HTTPException(422, "The uploaded file is empty.")
    return bytes(content)


def validate_format(extension, content):
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise limits.UnreadableDocument("This file is not a valid PDF. Re-export it as PDF or upload a DOCX instead.")
    if extension == "docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > limits.ZIP_ENTRIES or sum(e.file_size for e in entries) > limits.ZIP_BYTES:
                    raise limits.DocumentLimitError("DOCX expanded content exceeds the configured limit.")
                if any(e.flag_bits & 1 for e in entries):
                    raise limits.UnreadableDocument("Encrypted (password-protected) DOCX files are not supported. Remove the password and upload it again.")
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(archive.namelist()):
                    raise limits.UnreadableDocument("This file is not a valid DOCX document. Re-save it from Word or upload a PDF instead.")
        except BadZipFile as exc:
            raise limits.UnreadableDocument("This file is not a valid DOCX document. Re-save it from Word or upload a PDF instead.") from exc
