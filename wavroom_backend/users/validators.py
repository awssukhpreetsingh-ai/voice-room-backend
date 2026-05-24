"""
users/validators.py — Profile field validation and cooldown enforcement.

All validation raises ProfileValidationError which views convert to HTTP responses.
Import config values from users.config — never hardcode limits here.
"""
import os
import re
from datetime import timedelta

from django.utils import timezone

from . import config as cfg


# ── Error type ────────────────────────────────────────────────────────────────

class ProfileValidationError(Exception):
    """Raised by validators to signal a user-facing validation failure."""

    def __init__(self, message: str, code: str, extra: dict | None = None):
        self.message = message
        self.code = code
        self.extra = extra or {}
        super().__init__(message)

    def to_response_dict(self) -> dict:
        d = {'error': self.message, 'code': self.code}
        d.update(self.extra)
        return d


# ── Name ─────────────────────────────────────────────────────────────────────

# Matches at least one Unicode letter (handles non-Latin scripts).
_HAS_LETTER_RE = re.compile(r'[^\W\d_]', re.UNICODE)
# Five or more of the same character in a row ("aaaaa", "!!!!!").
_SPAM_RE = re.compile(r'(.)\1{4,}', re.UNICODE)


def validate_name(raw: str) -> str:
    """
    Validate a display name and return the cleaned value.
    Raises ProfileValidationError describing the first failure.
    """
    if not raw or not raw.strip():
        raise ProfileValidationError('Name cannot be empty.', 'name_empty')

    # Collapse internal whitespace (tabs, multiple spaces) to single spaces.
    name = ' '.join(raw.split())

    if len(name) < cfg.NAME_MIN_LENGTH:
        raise ProfileValidationError(
            f'Name must be at least {cfg.NAME_MIN_LENGTH} characters.',
            'name_too_short',
        )

    if len(name) > cfg.NAME_MAX_LENGTH:
        raise ProfileValidationError(
            f'Name cannot exceed {cfg.NAME_MAX_LENGTH} characters.',
            'name_too_long',
        )

    words = name.split()
    if len(words) > cfg.NAME_MAX_WORDS:
        raise ProfileValidationError(
            f'Name cannot be more than {cfg.NAME_MAX_WORDS} words.',
            'name_too_many_words',
        )

    if not _HAS_LETTER_RE.search(name):
        raise ProfileValidationError(
            'Name must contain at least one letter.',
            'name_no_letters',
        )

    if _SPAM_RE.search(name):
        raise ProfileValidationError(
            'Name contains too many repeated characters.',
            'name_spam',
        )

    return name


# ── Username ──────────────────────────────────────────────────────────────────

# Must start with a letter; allows letters, numbers, underscores, hyphens.
_USERNAME_RE = re.compile(r'^[a-z][a-z0-9_-]*$')


def validate_username(raw: str) -> str:
    """
    Validate a username and return the normalised (lowercase) value.
    Raises ProfileValidationError on the first failure.
    """
    username = raw.strip().lower()

    if len(username) < cfg.USERNAME_MIN_LENGTH:
        raise ProfileValidationError(
            f'Username must be at least {cfg.USERNAME_MIN_LENGTH} characters.',
            'username_too_short',
        )

    if len(username) > cfg.USERNAME_MAX_LENGTH:
        raise ProfileValidationError(
            f'Username cannot exceed {cfg.USERNAME_MAX_LENGTH} characters.',
            'username_too_long',
        )

    if not _USERNAME_RE.match(username):
        raise ProfileValidationError(
            'Username must start with a letter and contain only letters, numbers, '
            'underscores (_), or hyphens (-).',
            'username_invalid',
        )

    return username


# ── Cooldown ──────────────────────────────────────────────────────────────────

def check_cooldown(last_updated_at, cooldown_hours: int, field_label: str) -> None:
    """
    Raise ProfileValidationError if cooldown_hours have not elapsed since
    last_updated_at.  Callers should catch this and return HTTP 429.

    last_updated_at=None (never updated) always passes — no cooldown on first change.
    cooldown_hours=0 disables the check entirely.
    """
    if cooldown_hours <= 0 or last_updated_at is None:
        return

    elapsed = timezone.now() - last_updated_at
    cooldown = timedelta(hours=cooldown_hours)
    if elapsed < cooldown:
        remaining_seconds = int((cooldown - elapsed).total_seconds())
        remaining_hours   = remaining_seconds // 3600
        remaining_minutes = (remaining_seconds % 3600) // 60
        human_wait = (
            f'{remaining_hours}h {remaining_minutes}m' if remaining_hours
            else f'{remaining_minutes}m'
        )
        raise ProfileValidationError(
            f'{field_label} was updated recently. '
            f'You can update it again in {human_wait}.',
            f'{field_label.lower().replace(" ", "_")}_cooldown',
            {'retry_after_seconds': remaining_seconds},
        )


# ── Image file ────────────────────────────────────────────────────────────────

# Magic byte signatures for allowed image types.
_MAGIC_SIGNATURES: list[tuple[bytes, bytes | None, str]] = [
    # (prefix_bytes, optional_additional_check_at_offset_8, mime)
    (b'\xff\xd8\xff',   None,     'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', None,  'image/png'),
    (b'RIFF',           b'WEBP',  'image/webp'),   # bytes 0-3 == RIFF, bytes 8-11 == WEBP
]


def _detect_image_mimetype(file_obj) -> str | None:
    """
    Detect image MIME type from magic bytes (first 12 bytes of file).
    Returns None if the file does not match any allowed signature.
    This cannot be spoofed by the client unlike the Content-Type header.
    """
    header = file_obj.read(12)
    file_obj.seek(0)

    for prefix, secondary, mime in _MAGIC_SIGNATURES:
        if header.startswith(prefix):
            if secondary is not None:
                # For RIFF/WebP: bytes 8-11 must be the secondary marker.
                if header[8:12] != secondary:
                    continue
            return mime
    return None


def validate_image(file_obj) -> None:
    """
    Validate an uploaded image file.  Raises ProfileValidationError if:
      - The file exceeds MAX_IMAGE_SIZE_BYTES
      - The file extension is not in ALLOWED_IMAGE_EXTENSIONS
      - The file's magic bytes don't match an allowed image format

    After this call the file cursor is at position 0, ready for reading.
    """
    # ── Size ──────────────────────────────────────────────────────────────────
    file_obj.seek(0, 2)          # seek to end
    size = file_obj.tell()
    file_obj.seek(0)             # reset

    if size > cfg.MAX_IMAGE_SIZE_BYTES:
        max_mb = cfg.MAX_IMAGE_SIZE_BYTES // (1024 * 1024)
        raise ProfileValidationError(
            f'Image must be smaller than {max_mb} MB.',
            'image_too_large',
        )

    if size == 0:
        raise ProfileValidationError('Uploaded file is empty.', 'image_empty')

    # ── Extension ─────────────────────────────────────────────────────────────
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in cfg.ALLOWED_IMAGE_EXTENSIONS:
        allowed = ', '.join(sorted(cfg.ALLOWED_IMAGE_EXTENSIONS))
        raise ProfileValidationError(
            f'File type not allowed. Accepted formats: {allowed}.',
            'image_invalid_extension',
        )

    # ── Magic bytes (content verification) ───────────────────────────────────
    detected = _detect_image_mimetype(file_obj)
    if not detected or detected not in cfg.ALLOWED_IMAGE_MIMETYPES:
        raise ProfileValidationError(
            'File content does not match an allowed image format (JPEG, PNG, or WebP).',
            'image_invalid_content',
        )
