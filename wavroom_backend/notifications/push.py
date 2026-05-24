"""
FCM push notification helpers.

send_room_created_notification — multicast to all followers of a host.
send_single_push               — single-device push (used for follow, invite, etc).
"""

import logging
import os

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)


def _init_firebase():
    if not firebase_admin._apps:
        cred_path = os.path.join(settings.BASE_DIR, 'firebase-credentials.json')
        if os.path.exists(cred_path):
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        else:
            logger.warning(f'[firebase] No credentials found at {cred_path}')


def send_single_push(fcm_token: str, title: str, body: str, data: dict):
    """Send a push notification to a single device."""
    _init_firebase()
    if not firebase_admin._apps or not fcm_token:
        return
    try:
        msg = messaging.Message(
            token=fcm_token,
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='room_alerts',
                    color='#7C3AED',
                    click_action='FLUTTER_NOTIFICATION_CLICK',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default', badge=1),
                ),
            ),
        )
        messaging.send(msg)
    except Exception as e:
        logger.warning(f'[push] Single push failed: {e}')


def send_room_created_notification(host_user, room: dict):
    """
    Multicast push + create DB notification records for all followers of host_user.
    Called in a background thread from rooms/views.py — fire and forget.
    """
    _init_firebase()

    from users.models import Follow

    followers = list(
        Follow.objects
        .filter(following=host_user)
        .select_related('follower')
    )

    if not followers:
        return

    host_name  = host_user.name or 'Someone'
    room_title = room.get('title', 'a new room')
    room_id    = room.get('id', '')
    category   = room.get('category', '')

    title = f'{host_name} started a room 🎙'
    body  = f'"{room_title}" · {category} — tap to join'
    data  = {
        'type':     'room_started',
        'room_id':  room_id,
        'title':    room_title,
        'category': category,
        'host':     host_name,
    }

    # Persist in-app notification records for all followers
    try:
        from notifications.utils import bulk_create_notifications
        bulk_create_notifications(
            recipients=[f.follower for f in followers],
            notification_type='room_started',
            title=title,
            body=body,
            data=data,
        )
    except Exception as e:
        logger.error(f'[notify] DB bulk create failed: {e}')

    # FCM multicast (only to followers who have a token)
    tokens = [f.follower.fcm_token for f in followers if f.follower.fcm_token]
    if not tokens:
        return

    BATCH = 500
    total_ok = total_fail = 0

    for i in range(0, len(tokens), BATCH):
        batch = tokens[i:i + BATCH]
        message = messaging.MulticastMessage(
            tokens=batch,
            notification=messaging.Notification(title=title, body=body),
            data=data,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='room_alerts',
                    color='#7C3AED',
                    click_action='FLUTTER_NOTIFICATION_CLICK',
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default', badge=1),
                ),
            ),
        )
        try:
            response = messaging.send_each_for_multicast(message)
            total_ok   += response.success_count
            total_fail += response.failure_count
            if response.failure_count > 0:
                _remove_invalid_tokens(batch, response.responses)
        except Exception as e:
            logger.error(f'[notify] FCM batch error: {e}')

    logger.info(
        f'[notify] Room "{room_title}" by {host_name}: '
        f'{total_ok} sent, {total_fail} failed (of {len(tokens)} followers)'
    )


def _remove_invalid_tokens(tokens: list, responses: list):
    from users.models import User
    invalid = [
        tokens[i] for i, r in enumerate(responses)
        if not r.success and r.exception and
        'registration-token-not-registered' in str(r.exception)
    ]
    if invalid:
        updated = User.objects.filter(fcm_token__in=invalid).update(fcm_token='')
        logger.info(f'[notify] Cleared {updated} invalid FCM tokens')
