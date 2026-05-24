"""
Notification creation helpers used by views and signals across the project.
"""
import logging

logger = logging.getLogger(__name__)


def create_notification(recipient, notification_type: str, title: str, body: str,
                        data: dict = None, send_push: bool = True):
    """
    Create a single in-app DB notification and optionally send an FCM push.

    recipient         — users.models.User instance
    notification_type — one of Notification.Type values
    send_push         — set False when the FCM push was already sent separately
    """
    from notifications.models import Notification

    n = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        body=body,
        data=data or {},
    )

    if send_push and getattr(recipient, 'fcm_token', ''):
        try:
            from notifications.push import send_single_push
            send_single_push(recipient.fcm_token, title, body, data or {})
        except Exception as e:
            logger.warning(f'[notify] push failed for user {recipient.id}: {e}')

    return n


def bulk_create_notifications(recipients, notification_type: str, title: str,
                               body: str, data: dict = None):
    """
    Bulk-insert DB notification records for a list of User objects.
    Does NOT send FCM — caller handles that separately for batching efficiency.
    """
    from notifications.models import Notification

    objs = [
        Notification(
            recipient=r,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
        )
        for r in recipients
    ]
    Notification.objects.bulk_create(objs)
    logger.info(f'[notify] bulk_create: {len(objs)} {notification_type} records')
