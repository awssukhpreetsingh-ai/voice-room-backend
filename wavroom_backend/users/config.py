"""
users/config.py — Centralized profile validation & restriction settings.

Every value can be overridden via an environment variable without touching code.
Change these in your hosting platform's env config (e.g. Railway, Render, Heroku)
or in core/.env for local development.
"""
import os

# ── Name ─────────────────────────────────────────────────────────────────────
# Minimum/maximum character count after collapsing whitespace.
NAME_MIN_LENGTH = int(os.getenv('PROFILE_NAME_MIN_LENGTH', 2))
NAME_MAX_LENGTH = int(os.getenv('PROFILE_NAME_MAX_LENGTH', 50))
# Maximum number of space-separated words.
NAME_MAX_WORDS  = int(os.getenv('PROFILE_NAME_MAX_WORDS', 5))

# ── Username ──────────────────────────────────────────────────────────────────
USERNAME_MIN_LENGTH = int(os.getenv('PROFILE_USERNAME_MIN_LENGTH', 3))
USERNAME_MAX_LENGTH = int(os.getenv('PROFILE_USERNAME_MAX_LENGTH', 30))

# ── Bio ───────────────────────────────────────────────────────────────────────
BIO_MAX_LENGTH = int(os.getenv('PROFILE_BIO_MAX_LENGTH', 300))

# ── Update cooldowns (in hours, 0 = no cooldown) ─────────────────────────────
# Users must wait this long between each type of profile change.
NAME_COOLDOWN_HOURS   = int(os.getenv('PROFILE_NAME_COOLDOWN_HOURS', 24))
AVATAR_COOLDOWN_HOURS = int(os.getenv('PROFILE_AVATAR_COOLDOWN_HOURS', 24))
COVER_COOLDOWN_HOURS  = int(os.getenv('PROFILE_COVER_COOLDOWN_HOURS', 24))

# ── Image uploads ─────────────────────────────────────────────────────────────
MAX_IMAGE_SIZE_BYTES    = int(os.getenv('PROFILE_MAX_IMAGE_SIZE_MB', 5)) * 1024 * 1024
ALLOWED_IMAGE_MIMETYPES = frozenset({'image/jpeg', 'image/png', 'image/webp'})
ALLOWED_IMAGE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.webp'})
