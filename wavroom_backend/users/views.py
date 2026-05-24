# users/views.py

import os
import uuid
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from .models import User, Follow
from . import config as profile_config
from .validators import (
    ProfileValidationError,
    validate_name,
    validate_username,
    validate_image,
    check_cooldown,
)


def _init_firebase():
    if not firebase_admin._apps:
        cred_path = os.path.join(settings.BASE_DIR, 'firebase-credentials.json')
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print('[firebase] Admin SDK initialised ✅')
        else:
            print(f'[firebase] ⚠️  No credentials at {cred_path}')

_init_firebase()


def _verify_firebase_token(token_str):
    if not firebase_admin._apps:
        return {'uid': f'dev-{uuid.uuid4().hex[:8]}', 'phone_number': '', 'email': ''}
    try:
        return firebase_auth.verify_id_token(token_str)
    except Exception as e:
        print(f'[firebase] Token verify error: {e}')
        return None


def _rewrite_media_url(request, url: str) -> str:
    """
    Rewrite a stored absolute media URL to use the current request's host.

    upload_avatar / upload_cover store URLs built with request.build_absolute_uri()
    at upload time, embedding whatever tunnel/host was active then.  When the
    Cloudflare tunnel URL changes, those stored URLs become stale.  This helper
    replaces the host+scheme portion with the current request's host so the URL
    is always valid for the client making the request.
    """
    if not url:
        return ''
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        # Only rewrite paths under MEDIA_URL (don't touch external CDN URLs, etc.)
        if parsed.path.startswith(settings.MEDIA_URL):
            return request.build_absolute_uri(parsed.path)
    except Exception:
        pass
    return url


def _patch_media_urls(request, data: dict) -> dict:
    """Rewrite avatar_url and cover_image_url fields inside a to_dict() response."""
    for field in ('avatar_url', 'cover_image_url'):
        if field in data:
            data[field] = _rewrite_media_url(request, data[field])
    return data


def _get_user(request):
    auth  = request.headers.get('Authorization', '')
    token = None
    if auth.startswith('Bearer '):
        token = auth[7:]
    elif auth.startswith('Token '):
        token = auth[6:]

    if not token or not token.startswith('wavroom_'):
        return None

    parts = token.split('_')
    if len(parts) < 2:
        return None

    try:
        return User.objects.get(id=parts[1])
    except Exception:
        return None


# ══════════════════════════════════════════════
# AUTH ENDPOINTS
# ══════════════════════════════════════════════

@api_view(['POST'])
def firebase_auth_view(request):
    firebase_token = request.data.get('firebase_token', '')
    if not firebase_token:
        return Response({'error': 'firebase_token required'}, status=400)

    decoded = _verify_firebase_token(firebase_token)
    if not decoded:
        return Response({'error': 'Invalid Firebase token'}, status=401)

    uid   = decoded.get('uid', '')
    phone = decoded.get('phone_number', '') or ''
    email = decoded.get('email', '') or ''
    name  = decoded.get('name', '') or decoded.get('display_name', '') or ''

    user, created = User.objects.get_or_create(
        firebase_uid=uid,
        defaults={'phone': phone, 'email': email, 'name': name}
    )

    if not created:
        changed = False
        if phone and user.phone != phone: user.phone = phone; changed = True
        if email and user.email != email: user.email = email; changed = True
        if name and not user.name:        user.name  = name;  changed = True
        if changed: user.save()

    token = f'wavroom_{user.id}_{uuid.uuid4().hex[:8]}'
    print(f'[auth] {"Created" if created else "Login"} user={user.id} name={user.name}')

    return Response({
        'access':  token,
        'refresh': token,
        'user':    _patch_media_urls(request, user.to_dict()),
    })


@api_view(['GET'])
def me_view(request):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Invalid token'}, status=401)
    return Response(_patch_media_urls(request, user.to_dict(current_user=user)))


@api_view(['PATCH'])
def profile_view(request):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Invalid token'}, status=401)

    # Fields that can be set directly without special validation.
    # avatar_url / cover_image_url are intentionally excluded — those must go
    # through the dedicated upload endpoints so cooldowns and file validation apply.
    # talks_hosted / reputation_score are system-managed fields, not user-editable.
    SAFE_FIELDS = [
        'gender', 'interests', 'avatar_color',
        'linkedin_url', 'twitter_url', 'website_url', 'onboarding_complete',
    ]
    for field in SAFE_FIELDS:
        if field in request.data:
            setattr(user, field, request.data[field])

    # ── Name: validated + cooldown-protected ─────────────────────────────────
    if 'name' in request.data:
        try:
            cleaned_name = validate_name(request.data['name'])
        except ProfileValidationError as exc:
            return Response(exc.to_response_dict(), status=400)

        # Cooldown applies only after onboarding is complete.
        # Users can freely correct their name during the initial setup flow.
        if user.onboarding_complete:
            try:
                check_cooldown(
                    user.name_updated_at,
                    profile_config.NAME_COOLDOWN_HOURS,
                    'Name',
                )
            except ProfileValidationError as exc:
                return Response(exc.to_response_dict(), status=429)

        user.name = cleaned_name
        user.name_updated_at = timezone.now()

    # ── Bio: length-limited ───────────────────────────────────────────────────
    if 'bio' in request.data:
        bio = (request.data['bio'] or '').strip()
        if len(bio) > profile_config.BIO_MAX_LENGTH:
            return Response({
                'error': f'Bio cannot exceed {profile_config.BIO_MAX_LENGTH} characters.',
                'code': 'bio_too_long',
            }, status=400)
        user.bio = bio

    # ── Username: format-validated + uniqueness-enforced ─────────────────────
    if 'username' in request.data:
        raw = (request.data['username'] or '').strip() or None
        if raw:
            try:
                raw = validate_username(raw)
            except ProfileValidationError as exc:
                return Response(exc.to_response_dict(), status=400)
            if User.objects.filter(username=raw).exclude(pk=user.pk).exists():
                return Response(
                    {'error': 'Username already taken.', 'code': 'username_taken'},
                    status=400,
                )
        user.username = raw

    user.save()
    return Response(_patch_media_urls(request, user.to_dict(current_user=user)))


def _delete_old_media(old_url: str, media_prefix: str) -> None:
    """Delete the old media file from storage (S3 or local legacy)."""
    if not old_url:
        return
    try:
        from urllib.parse import urlparse
        path = urlparse(old_url).path.lstrip('/')
        # Strip legacy local '/media/' prefix if present
        if path.startswith('media/'):
            path = path[len('media/'):]
        if not path.startswith(media_prefix):
            return
        if default_storage.exists(path):
            default_storage.delete(path)
    except Exception as e:
        print(f'[media] Failed to delete old file: {e}')


@api_view(['POST'])
@parser_classes([MultiPartParser])
def upload_avatar(request):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Invalid token'}, status=401)

    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file provided'}, status=400)

    # Cooldown check before doing any file I/O.
    try:
        check_cooldown(
            user.avatar_updated_at,
            profile_config.AVATAR_COOLDOWN_HOURS,
            'Profile picture',
        )
    except ProfileValidationError as exc:
        return Response(exc.to_response_dict(), status=429)

    # Validate size, extension, and magic bytes.
    try:
        validate_image(file)
    except ProfileValidationError as exc:
        return Response(exc.to_response_dict(), status=400)

    _delete_old_media(user.avatar_url, 'uploads/profile_pictures/')

    ext  = os.path.splitext(file.name)[1].lower() or '.jpg'
    path = f'uploads/profile_pictures/{user.id}{ext}'
    if default_storage.exists(path):
        default_storage.delete(path)
    saved_path = default_storage.save(path, ContentFile(file.read()))
    url = default_storage.url(saved_path)

    user.avatar_url = url
    user.avatar_updated_at = timezone.now()
    user.save(update_fields=['avatar_url', 'avatar_updated_at'])
    return Response({'avatar_url': url})


@api_view(['POST'])
@parser_classes([MultiPartParser])
def upload_cover(request):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Invalid token'}, status=401)

    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file provided'}, status=400)

    # Cooldown check before doing any file I/O.
    try:
        check_cooldown(
            user.cover_updated_at,
            profile_config.COVER_COOLDOWN_HOURS,
            'Cover image',
        )
    except ProfileValidationError as exc:
        return Response(exc.to_response_dict(), status=429)

    # Validate size, extension, and magic bytes.
    try:
        validate_image(file)
    except ProfileValidationError as exc:
        return Response(exc.to_response_dict(), status=400)

    _delete_old_media(user.cover_image_url, 'uploads/cover_images/')

    ext  = os.path.splitext(file.name)[1].lower() or '.jpg'
    path = f'uploads/cover_images/{user.id}{ext}'
    if default_storage.exists(path):
        default_storage.delete(path)
    saved_path = default_storage.save(path, ContentFile(file.read()))
    url = default_storage.url(saved_path)

    user.cover_image_url = url
    user.cover_updated_at = timezone.now()
    user.save(update_fields=['cover_image_url', 'cover_updated_at'])
    return Response({'cover_image_url': url})


# ══════════════════════════════════════════════
# NEW: FCM token endpoint
# Flutter calls this on every app launch so the token stays current.
# FCM tokens rotate periodically — if we don't update them, notifications stop.
# ══════════════════════════════════════════════

@api_view(['POST'])
def update_fcm_token(request):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Invalid token'}, status=401)

    fcm_token = request.data.get('fcm_token', '').strip()
    if not fcm_token:
        return Response({'error': 'fcm_token required'}, status=400)

    # Only write if changed — avoids unnecessary DB writes on every app open
    if user.fcm_token != fcm_token:
        user.fcm_token = fcm_token
        user.save(update_fields=['fcm_token'])
        print(f'[fcm] Updated token for user={user.id}')

    return Response({'message': 'FCM token updated'})


# ══════════════════════════════════════════════
# USER PROFILE ENDPOINTS
# ══════════════════════════════════════════════

@api_view(['GET'])
def user_profile_view(request, user_id):
    target       = get_object_or_404(User, id=user_id)
    current_user = _get_user(request)
    return Response(_patch_media_urls(request, target.to_dict(current_user=current_user)))


@api_view(['POST', 'DELETE'])
def follow_view(request, user_id):
    current_user = _get_user(request)
    if not current_user:
        return Response({'error': 'Invalid token'}, status=401)

    target = get_object_or_404(User, id=user_id)
    if current_user.id == target.id:
        return Response({'error': 'Cannot follow yourself'}, status=400)

    if request.method == 'DELETE':
        Follow.objects.filter(follower=current_user, following=target).delete()
        return Response({
            'following':       False,
            'follower_count':  target.follower_count,
            'following_count': current_user.following_count,
        })

    # POST — follow
    _, created = Follow.objects.get_or_create(follower=current_user, following=target)

    if created:
        try:
            from notifications.utils import create_notification
            create_notification(
                recipient=target,
                notification_type='new_follower',
                title='New follower',
                body=f'{current_user.name or "Someone"} started following you.',
                data={'user_id': str(current_user.id), 'user_name': current_user.name or ''},
            )
        except Exception as e:
            print(f'[notify] follow notification failed: {e}')

    return Response({
        'following':       True,
        'follower_count':  target.follower_count,
        'following_count': current_user.following_count,
    })


@api_view(['GET'])
def followers_list_view(request, user_id):
    target       = get_object_or_404(User, id=user_id)
    current_user = _get_user(request)
    followers    = User.objects.filter(following_set__following=target)
    return Response([_patch_media_urls(request, u.to_dict(current_user=current_user)) for u in followers])


@api_view(['GET'])
def following_list_view(request, user_id):
    target       = get_object_or_404(User, id=user_id)
    current_user = _get_user(request)
    following    = User.objects.filter(follower_set__follower=target)
    return Response([_patch_media_urls(request, u.to_dict(current_user=current_user)) for u in following])