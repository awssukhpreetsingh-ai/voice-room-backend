import os

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.contrib.auth.models import User as DjangoUser
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from users.models import User, Follow
from spaces.models import Space, SpaceMembership, Discussion, Comment, SpaceReport
from rooms import redis_client as rc

from .models import AdminProfile, AdminToken, AuditLog
from .permissions import AdminRequired
from .serializers import (
    AdminProfileSerializer, UserAdminSerializer, SpaceAdminSerializer,
    ReportAdminSerializer, AuditLogSerializer,
)


def _ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def _log(admin, action, target_type, target_id, details=None, request=None):
    AuditLog.objects.create(
        admin=admin,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        details=details or {},
        ip_address=_ip(request) if request else None,
    )


# ── Auth ──────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def admin_login(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    if not username or not password:
        return Response({'error': 'Username and password required'}, status=400)

    django_user = authenticate(username=username, password=password)
    if not django_user:
        return Response({'error': 'Invalid credentials'}, status=401)

    try:
        admin = django_user.admin_profile
    except AdminProfile.DoesNotExist:
        return Response({'error': 'Not authorised as admin'}, status=403)

    if not admin.is_active:
        return Response({'error': 'Account disabled'}, status=403)

    token = AdminToken.create_for(admin)
    _log(admin, 'login', 'admin', admin.id, request=request)

    return Response({
        'token':      token.token,
        'expires_at': token.expires_at.isoformat(),
        'admin':      AdminProfileSerializer(admin).data,
    })


@api_view(['POST'])
def admin_logout(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err
    header = request.META.get('HTTP_AUTHORIZATION', '')
    AdminToken.objects.filter(token=header[len('AdminToken '):].strip()).delete()
    return Response({'message': 'Logged out'})


@api_view(['GET'])
def admin_me(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err
    return Response(AdminProfileSerializer(admin).data)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def dashboard_stats(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    now        = timezone.now()
    day_ago    = now - timedelta(days=1)
    week_ago   = now - timedelta(days=7)
    month_ago  = now - timedelta(days=30)

    total_users     = User.objects.count()
    new_today       = User.objects.filter(created_at__gte=day_ago).count()
    new_this_week   = User.objects.filter(created_at__gte=week_ago).count()
    new_this_month  = User.objects.filter(created_at__gte=month_ago).count()
    banned_count    = User.objects.filter(is_banned=True).count()

    try:
        rc.prune_expired()
        active_rooms   = rc.get_all_rooms()
        room_count     = len(active_rooms)
        total_listeners = sum(int(r.get('listener_count', 0)) for r in active_rooms)
    except Exception:
        room_count = total_listeners = 0
        active_rooms = []

    total_spaces     = Space.objects.count()
    total_discussions = Discussion.objects.count()
    pending_reports  = SpaceReport.objects.count()

    return Response({
        'users': {
            'total':         total_users,
            'new_today':     new_today,
            'new_this_week': new_this_week,
            'new_this_month': new_this_month,
            'banned':        banned_count,
        },
        'rooms': {
            'active':          room_count,
            'total_listeners': total_listeners,
        },
        'spaces': {
            'total': total_spaces,
        },
        'content': {
            'total_discussions': total_discussions,
            'pending_reports':   pending_reports,
        },
    })


# ── Users ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def list_users(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    search    = request.query_params.get('search', '').strip()
    status    = request.query_params.get('status', 'all')
    sort_by   = request.query_params.get('sort_by', '-created_at')
    page      = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))

    qs = User.objects.all()

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(username__icontains=search) | Q(email__icontains=search))

    if status == 'banned':
        qs = qs.filter(is_banned=True)
    elif status == 'active':
        qs = qs.filter(is_banned=False)

    safe_sorts = {'-created_at', 'created_at', '-talks_hosted', 'talks_hosted', '-reputation_score', 'name', '-name'}
    qs = qs.order_by(sort_by if sort_by in safe_sorts else '-created_at')

    total  = qs.count()
    start  = (page - 1) * page_size
    users  = qs[start: start + page_size]

    return Response({
        'users':       UserAdminSerializer(users, many=True).data,
        'total':       total,
        'page':        page,
        'page_size':   page_size,
        'total_pages': (total + page_size - 1) // page_size,
    })


@api_view(['GET', 'PATCH', 'DELETE'])
def user_detail(request, user_id):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    if request.method == 'GET':
        data = UserAdminSerializer(user).data
        data['stats'] = {
            'discussions':    Discussion.objects.filter(author=user).count(),
            'comments':       Comment.objects.filter(author=user).count(),
            'spaces_joined':  SpaceMembership.objects.filter(user=user).count(),
            'followers':      Follow.objects.filter(following=user).count(),
            'following':      Follow.objects.filter(follower=user).count(),
        }
        data['recent_discussions'] = list(
            Discussion.objects.filter(author=user)
            .order_by('-created_at')
            .values('id', 'title', 'created_at', 'space_id')[:5]
        )
        return Response(data)

    if request.method == 'PATCH':
        action = request.data.get('action')
        if action == 'ban':
            user.is_banned = True
            user.save(update_fields=['is_banned'])
            _log(admin, 'ban_user', 'user', user_id, {'reason': request.data.get('reason', '')}, request)
            return Response({'message': 'User banned'})
        if action == 'unban':
            user.is_banned = False
            user.save(update_fields=['is_banned'])
            _log(admin, 'unban_user', 'user', user_id, {}, request)
            return Response({'message': 'User unbanned'})
        return Response({'error': 'Unknown action'}, status=400)

    # DELETE
    _log(admin, 'delete_user', 'user', user_id, {'name': user.name, 'email': user.email}, request)
    user.delete()
    return Response({'message': 'User deleted'})


# ── Rooms ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def list_rooms(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    try:
        rc.prune_expired()
        rooms = rc.get_all_rooms()
    except Exception:
        rooms = []

    user_ids = {r.get('host_id') for r in rooms if r.get('host_id')}
    hosts    = {str(u.id): u for u in User.objects.filter(id__in=user_ids)}

    enriched = []
    for room in rooms:
        host = hosts.get(room.get('host_id', ''))
        enriched.append({
            **room,
            'host': {
                'id':           str(host.id),
                'name':         host.name,
                'email':        host.email,
                'avatar_color': host.avatar_color,
            } if host else None,
            'banned_users': rc.get_banned_users(room['id']),
            'muted_users':  rc.get_muted_users(room['id']),
        })

    return Response({'rooms': enriched, 'total': len(enriched)})


@api_view(['DELETE'])
def close_room(request, room_id):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)

    rc.delete_room(room_id)
    _log(admin, 'close_room', 'room', room_id,
         {'title': room.get('title', ''), 'host_id': room.get('host_id', '')}, request)
    return Response({'message': 'Room force-closed'})


# ── Spaces ────────────────────────────────────────────────────────────────────

_VALID_ATMOSPHERES = ['philosophy', 'ai_research', 'deep_science', 'psychology', 'entrepreneurship', 'English Speaking']


@api_view(['GET', 'POST'])
def list_spaces(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    if request.method == 'POST':
        title = request.data.get('title', '').strip()
        if not title:
            return Response({'error': 'title is required'}, status=400)

        atmosphere = request.data.get('atmosphere', 'philosophy')
        if atmosphere not in _VALID_ATMOSPHERES:
            return Response({'error': f'atmosphere must be one of {_VALID_ATMOSPHERES}'}, status=400)

        # Resolve owner — optional but recommended
        owner_id = request.data.get('owner_id', '').strip()
        owner = None
        if owner_id:
            try:
                owner = User.objects.get(id=owner_id)
            except (User.DoesNotExist, ValueError):
                return Response({'error': 'owner_id does not match any user'}, status=400)

        space = Space.objects.create(
            title=title,
            tagline=request.data.get('tagline', '').strip(),
            description=request.data.get('description', '').strip(),
            emoji=(request.data.get('emoji') or '💬').strip(),
            atmosphere=atmosphere,
            accent_color=(request.data.get('accent_color') or '#7C6FF7').strip(),
        )

        if owner:
            SpaceMembership.objects.create(space=space, user=owner, role='owner')

        _log(admin, 'create_space', 'space', str(space.id),
             {'title': space.title, 'slug': space.slug,
              'owner_id': str(owner.id) if owner else None}, request)
        return Response(SpaceAdminSerializer(space).data, status=201)

    # GET
    search    = request.query_params.get('search', '').strip()
    page      = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))

    qs = Space.objects.all().order_by('-created_at')
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(slug__icontains=search))

    total  = qs.count()
    spaces = qs[(page - 1) * page_size: page * page_size]

    return Response({
        'spaces':      SpaceAdminSerializer(spaces, many=True).data,
        'total':       total,
        'page':        page,
        'page_size':   page_size,
        'total_pages': (total + page_size - 1) // page_size,
    })


@api_view(['GET', 'DELETE'])
def space_detail(request, space_id):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    try:
        space = Space.objects.get(Q(id=space_id) | Q(slug=space_id))
    except (Space.DoesNotExist, DjangoValidationError):
        try:
            space = Space.objects.get(slug=space_id)
        except Space.DoesNotExist:
            return Response({'error': 'Space not found'}, status=404)

    if request.method == 'GET':
        data = SpaceAdminSerializer(space).data
        data['discussion_count'] = Discussion.objects.filter(space=space).count()
        data['report_count']     = SpaceReport.objects.filter(space=space).count()
        data['recent_reports']   = ReportAdminSerializer(
            SpaceReport.objects.filter(space=space).order_by('-created_at')[:5], many=True
        ).data
        return Response(data)

    _log(admin, 'delete_space', 'space', str(space.id), {'title': space.title, 'slug': space.slug}, request)
    space.delete()
    return Response({'message': 'Space deleted'})


@api_view(['POST'])
@parser_classes([MultiPartParser])
def upload_space_cover(request, space_id):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    try:
        space = Space.objects.get(Q(id=space_id) | Q(slug=space_id))
    except (Space.DoesNotExist, DjangoValidationError):
        try:
            space = Space.objects.get(slug=space_id)
        except Space.DoesNotExist:
            return Response({'error': 'Space not found'}, status=404)

    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file provided'}, status=400)

    ext  = os.path.splitext(file.name)[1].lower() or '.jpg'
    path = f'uploads/space_covers/{space.slug}{ext}'

    if default_storage.exists(path):
        default_storage.delete(path)

    saved_path = default_storage.save(path, ContentFile(file.read()))
    url = default_storage.url(saved_path)

    space.cover_image_url = url
    space.save(update_fields=['cover_image_url'])

    _log(admin, 'upload_space_cover', 'space', str(space.id), {'slug': space.slug}, request)
    return Response({'cover_image_url': url})


# ── Moderation / Reports ──────────────────────────────────────────────────────

@api_view(['GET'])
def list_reports(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    page      = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))

    reports = SpaceReport.objects.select_related('space', 'reporter').order_by('-created_at')
    total   = reports.count()

    return Response({
        'reports':     ReportAdminSerializer(reports[(page - 1) * page_size: page * page_size], many=True).data,
        'total':       total,
        'page':        page,
        'page_size':   page_size,
        'total_pages': (total + page_size - 1) // page_size,
    })


@api_view(['DELETE'])
def resolve_report(request, report_id):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    try:
        report = SpaceReport.objects.get(id=report_id)
    except SpaceReport.DoesNotExist:
        return Response({'error': 'Report not found'}, status=404)

    _log(admin, 'resolve_report', 'report', report_id, {'reason': report.reason}, request)
    report.delete()
    return Response({'message': 'Report resolved'})


# ── Analytics ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def analytics_user_growth(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    days = min(90, max(7, int(request.query_params.get('days', 30))))
    now  = timezone.now()

    data = []
    for i in range(days, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        data.append({
            'date':      day_start.strftime('%Y-%m-%d'),
            'new_users': User.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
        })

    return Response({'data': data, 'total_users': User.objects.count()})


@api_view(['GET'])
def analytics_top_spaces(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    spaces = Space.objects.annotate(
        member_count_ann=Count('memberships'),
        discussion_count_ann=Count('discussions'),
    ).order_by('-member_count_ann')[:10]

    return Response({
        'spaces': [
            {
                'id':               str(s.id),
                'title':            s.title,
                'emoji':            s.emoji,
                'atmosphere':       s.atmosphere,
                'accent_color':     s.accent_color,
                'member_count':     s.member_count_ann,
                'discussion_count': s.discussion_count_ann,
            }
            for s in spaces
        ]
    })


@api_view(['GET'])
def analytics_discussions(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    by_type = (
        Discussion.objects.values('post_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    by_atmosphere = (
        Discussion.objects.values('atmosphere')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    days = min(90, max(7, int(request.query_params.get('days', 30))))
    now  = timezone.now()
    trend = []
    for i in range(days, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        trend.append({
            'date':  day_start.strftime('%Y-%m-%d'),
            'count': Discussion.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
        })

    return Response({
        'by_type':       list(by_type),
        'by_atmosphere': list(by_atmosphere),
        'trend':         trend,
        'total':         Discussion.objects.count(),
    })


# ── Audit Logs ────────────────────────────────────────────────────────────────

@api_view(['GET'])
def audit_logs(request):
    admin, err = AdminRequired.resolve(request)
    if err:
        return err

    page      = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))

    logs  = AuditLog.objects.select_related('admin__django_user').all()
    total = logs.count()

    return Response({
        'logs':        AuditLogSerializer(logs[(page - 1) * page_size: page * page_size], many=True).data,
        'total':       total,
        'page':        page,
        'page_size':   page_size,
        'total_pages': (total + page_size - 1) // page_size,
    })
