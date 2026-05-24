from django.core.paginator import Paginator
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Notification


def _get_user(request):
    auth = request.headers.get('Authorization', '')
    token = None
    if auth.startswith('Token '):
        token = auth[6:]
    elif auth.startswith('Bearer '):
        token = auth[7:]
    if not token or not token.startswith('wavroom_'):
        return None
    parts = token.split('_')
    if len(parts) < 2:
        return None
    try:
        from users.models import User
        return User.objects.get(id=parts[1])
    except Exception:
        return None


@api_view(['GET'])
def notification_list(request):
    """
    GET /api/notifications/
    Optional: ?unread_only=true  — filter to unread only
    Optional: ?page=<n>          — page number (20 per page)
    """
    user = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    unread_only = request.GET.get('unread_only', '').lower() == 'true'
    qs = Notification.objects.filter(recipient=user)
    if unread_only:
        qs = qs.filter(is_read=False)

    page_num  = max(1, int(request.GET.get('page', 1)))
    paginator = Paginator(qs, 20)
    page      = paginator.get_page(page_num)

    return Response({
        'notifications': [n.to_dict() for n in page],
        'total':         paginator.count,
        'unread':        Notification.objects.filter(recipient=user, is_read=False).count(),
        'has_more':      page.has_next(),
        'page':          page_num,
    })


@api_view(['GET'])
def notification_count(request):
    """
    GET /api/notifications/count/
    Returns { "unread": <int> } — used for the badge in the app bar.
    """
    user = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    unread = Notification.objects.filter(recipient=user, is_read=False).count()
    return Response({'unread': unread})


@api_view(['POST'])
def mark_all_read(request):
    """POST /api/notifications/read_all/"""
    user = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    updated = Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)
    return Response({'marked_read': updated})


@api_view(['PATCH'])
def notification_detail(request, notification_id):
    """PATCH /api/notifications/<id>/  — mark a single notification as read."""
    user = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    try:
        n = Notification.objects.get(id=notification_id, recipient=user)
    except Notification.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    n.is_read = True
    n.save(update_fields=['is_read'])
    return Response(n.to_dict())
