from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from users.models import User
from .models import (
    Space, SpaceMembership, ScheduledRoom,
    Discussion, Comment,
    DiscussionReaction, CommentReaction, SavedDiscussion,
    SpaceReport,
)


# ─────────────────────────────────────────────────────────────────────────────
# Auth + permission helpers
# ─────────────────────────────────────────────────────────────────────────────

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
        return User.objects.get(id=parts[1])
    except Exception:
        return None


def _get_membership(space, user):
    if user is None:
        return None
    try:
        return SpaceMembership.objects.get(space=space, user=user)
    except SpaceMembership.DoesNotExist:
        return None


def _require_membership(space, user):
    """Returns (membership, error_response). One of them will be None."""
    if not user:
        return None, Response({'error': 'Authentication required'}, status=401)
    m = _get_membership(space, user)
    if not m:
        return None, Response(
            {'error': 'Join this Realm to participate', 'requires_membership': True},
            status=403,
        )
    return m, None


def _require_can_create_room(space, user):
    """Returns (membership, error_response)."""
    m, err = _require_membership(space, user)
    if err:
        return None, err
    if not m.can_create_room():
        return None, Response(
            {'error': 'Only the Owner and SuperHosts can create Rooms'}, status=403)
    return m, None


def _require_owner(space, user):
    m, err = _require_membership(space, user)
    if err:
        return None, err
    if m.role != 'owner':
        return None, Response({'error': 'Owner access required'}, status=403)
    return m, None


# ─────────────────────────────────────────────────────────────────────────────
# Spaces
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def spaces_list(request):
    user = _get_user(request)

    if request.method == 'GET':
        q      = request.GET.get('q', '').strip()
        spaces = Space.objects.all().order_by('title')
        if q:
            spaces = spaces.filter(Q(title__icontains=q) | Q(tagline__icontains=q) | Q(description__icontains=q))
        return Response([s.to_dict(current_user=user) for s in spaces])

    # POST — create a new space (creator becomes owner)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    title = request.data.get('title', '').strip()
    if not title:
        return Response({'error': 'title required'}, status=400)

    space = Space.objects.create(
        title=title,
        tagline=request.data.get('tagline', ''),
        description=request.data.get('description', ''),
        emoji=request.data.get('emoji', '💬'),
        atmosphere=request.data.get('atmosphere', 'philosophy'),
        accent_color=request.data.get('accent_color', '#7C6FF7'),
    )
    SpaceMembership.objects.create(space=space, user=user, role='owner')
    return Response(space.to_dict(current_user=user), status=201)


@api_view(['GET', 'PATCH'])
def space_detail(request, space_id):
    user  = _get_user(request)
    space = get_object_or_404(Space, slug=space_id)

    if request.method == 'GET':
        return Response(space.to_dict(current_user=user))

    # PATCH — owner can edit realm details
    _, err = _require_owner(space, user)
    if err:
        return err

    for field in ('title', 'tagline', 'description', 'emoji', 'accent_color', 'atmosphere'):
        if field in request.data:
            setattr(space, field, request.data[field])
    space.save()
    return Response(space.to_dict(current_user=user))


@api_view(['POST', 'DELETE'])
def space_join(request, space_id):
    user  = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)
    space = get_object_or_404(Space, slug=space_id)

    if request.method == 'POST':
        membership, created = SpaceMembership.objects.get_or_create(
            space=space, user=user, defaults={'role': 'member'})
        return Response({
            'is_member':  True,
            'user_role':  membership.role,
            'member_count': space.member_count,
        })

    # DELETE — leave (owners cannot leave their own space)
    m = _get_membership(space, user)
    if m and m.role == 'owner':
        return Response({'error': 'Owner cannot leave their own Realm'}, status=400)
    SpaceMembership.objects.filter(space=space, user=user).delete()
    return Response({'is_member': False, 'user_role': None, 'member_count': space.member_count})


@api_view(['GET'])
def space_members(request, space_id):
    user  = _get_user(request)
    space = get_object_or_404(Space, slug=space_id)

    memberships = (
        SpaceMembership.objects
        .filter(space=space)
        .select_related('user')
        .order_by('role', 'joined_at')
    )
    data = [
        {
            'id':           str(m.user.id),
            'name':         m.user.name,
            'role':         m.role,
            'avatar_color': m.user.avatar_color,
            'avatar_url':   m.user.avatar_url or '',
            'joined_at':    m.joined_at.isoformat(),
        }
        for m in memberships
    ]
    return Response({'members': data, 'total': len(data)})


@api_view(['POST'])
def space_promote(request, space_id):
    """Owner promotes/demotes a member to superhost."""
    user  = _get_user(request)
    space = get_object_or_404(Space, slug=space_id)

    _, err = _require_owner(space, user)
    if err:
        return err

    target_user_id = request.data.get('user_id')
    new_role       = request.data.get('role', 'superhost')

    if new_role not in ('superhost', 'member'):
        return Response({'error': 'role must be superhost or member'}, status=400)

    m = get_object_or_404(SpaceMembership, space=space, user__id=target_user_id)
    if m.role == 'owner':
        return Response({'error': 'Cannot change the owner role'}, status=400)

    m.role = new_role
    m.save()
    return Response({'user_id': target_user_id, 'new_role': new_role})


@api_view(['GET'])
def space_analytics(request, space_id):
    """Owner-only analytics snapshot."""
    user  = _get_user(request)
    space = get_object_or_404(Space, slug=space_id)

    _, err = _require_owner(space, user)
    if err:
        return err

    total_members   = space.member_count
    total_discussions = Discussion.objects.filter(space=space).count()
    total_comments    = Comment.objects.filter(discussion__space=space).count()

    # Top contributors by discussion count
    from django.db.models import Count
    top_contributors = (
        Discussion.objects
        .filter(space=space)
        .values('author__id', 'author__name', 'author__avatar_color')
        .annotate(post_count=Count('id'))
        .order_by('-post_count')[:5]
    )

    return Response({
        'member_count':      total_members,
        'discussion_count':  total_discussions,
        'comment_count':     total_comments,
        'live_rooms':        space._live_chamber_count(),
        'top_contributors': [
            {
                'id':           str(c['author__id']),
                'name':         c['author__name'],
                'avatar_color': c['author__avatar_color'],
                'post_count':   c['post_count'],
            }
            for c in top_contributors
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Rooms within a space
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def space_live_rooms(request, space_id):
    space = get_object_or_404(Space, slug=space_id)
    rooms = space._get_live_rooms()

    # Enrich each room with host avatar and normalise participant_count
    host_ids = {r.get('host_id') for r in rooms if r.get('host_id')}
    host_map = {
        str(u.id): u
        for u in User.objects.filter(id__in=host_ids)
    }

    enriched = []
    for r in rooms:
        room = dict(r)
        host = host_map.get(str(room.get('host_id', '')))
        room['host_avatar_url']   = host.avatar_url if host else ''
        room['host_avatar_color'] = host.avatar_color if host else '#7C6FF7'
        # Redis stores listener_count; Flutter _LiveRoomCard reads participant_count
        if 'participant_count' not in room:
            room['participant_count'] = room.get('listener_count', 0)
        enriched.append(room)

    return Response(enriched)


@api_view(['GET', 'POST'])
def space_scheduled_rooms(request, space_id):
    user  = _get_user(request)
    space = get_object_or_404(Space, slug=space_id)

    if request.method == 'GET':
        upcoming = ScheduledRoom.objects.filter(
            space=space, scheduled_at__gte=timezone.now()
        )
        return Response([r.to_dict() for r in upcoming])

    # POST — create scheduled room (owner/superhost only)
    _, err = _require_can_create_room(space, user)
    if err:
        return err

    title = request.data.get('title', '').strip()
    scheduled_at = request.data.get('scheduled_at')
    if not title or not scheduled_at:
        return Response({'error': 'title and scheduled_at required'}, status=400)

    room = ScheduledRoom.objects.create(
        space=space,
        host=user,
        title=title,
        description=request.data.get('description', ''),
        scheduled_at=scheduled_at,
    )
    return Response(room.to_dict(), status=201)


@api_view(['DELETE'])
def space_scheduled_room_detail(request, space_id, room_id):
    user  = _get_user(request)
    space = get_object_or_404(Space, slug=space_id)
    room  = get_object_or_404(ScheduledRoom, id=room_id, space=space)

    _, err = _require_can_create_room(space, user)
    if err:
        return err

    room.delete()
    return Response(status=204)


# ─────────────────────────────────────────────────────────────────────────────
# Discussions
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def space_discussions(request, space_id):
    user  = _get_user(request)
    space = get_object_or_404(Space, slug=space_id)

    if request.method == 'GET':
        # Public read — anyone can browse discussions
        discussions = (
            Discussion.objects
            .filter(space=space)
            .select_related('author', 'space')
        )
        return Response([d.to_dict(current_user=user) for d in discussions])

    # POST — members only
    membership, err = _require_membership(space, user)
    if err:
        return err

    title = request.data.get('title', '').strip()
    body  = request.data.get('body',  '').strip()
    if not body:
        return Response({'error': 'body is required'}, status=400)

    discussion = Discussion.objects.create(
        space=space,
        author=user,
        title=title,
        body=body,
        tags=request.data.get('tags', []),
        post_type=request.data.get('post_type', 'thought'),
        atmosphere=request.data.get('atmosphere', 'calm'),
        accent_color=request.data.get('accent_color', space.accent_color),
    )
    return Response(discussion.to_dict(current_user=user), status=201)


@api_view(['GET'])
def discussion_detail(request, discussion_id):
    user       = _get_user(request)
    discussion = get_object_or_404(Discussion, id=discussion_id)
    return Response(discussion.to_dict(current_user=user))


@api_view(['POST'])
def space_report(request, space_id):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    space  = get_object_or_404(Space, slug=space_id)
    reason = request.data.get('reason', '').strip()

    valid_reasons = {'spam', 'harassment', 'hate_speech', 'inappropriate', 'fake_quality', 'other'}
    if reason not in valid_reasons:
        return Response({'error': 'Invalid reason'}, status=400)

    _, created = SpaceReport.objects.get_or_create(
        space=space,
        reporter=user,
        defaults={
            'reason':  reason,
            'message': request.data.get('message', '').strip(),
        },
    )

    if not created:
        return Response({'already_reported': True}, status=200)

    return Response({'reported': True}, status=201)


@api_view(['GET'])
def global_search(request):
    """
    Combined search across live rooms + spaces.
    GET /api/search/?q=<query>
    Returns: { rooms: [...], spaces: [...], query: str }
    """
    q    = request.GET.get('q', '').strip()
    user = _get_user(request)

    if not q:
        return Response({'rooms': [], 'spaces': [], 'query': ''})

    spaces = Space.objects.filter(
        Q(title__icontains=q) | Q(tagline__icontains=q) | Q(description__icontains=q)
    )[:10]

    from rooms import redis_client as rc
    rc.prune_expired()
    rooms = rc.get_all_rooms(q=q)[:20]

    return Response({
        'spaces': [s.to_dict(current_user=user) for s in spaces],
        'rooms':  rooms,
        'query':  q,
    })


@api_view(['GET'])
def space_archive(request, space_id):
    """Archive placeholder — returns an empty state until the feature ships."""
    get_object_or_404(Space, slug=space_id)
    return Response({
        'items':   [],
        'has_more': False,
        'message': 'Archived conversations and moments will appear here in a future update.',
    })


@api_view(['POST'])
def discussion_react(request, discussion_id):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    discussion    = get_object_or_404(Discussion, id=discussion_id)
    reaction_type = request.data.get('reaction_type', '')

    if reaction_type not in ('appreciate', 'insightful', 'curious'):
        return Response({'error': 'Invalid reaction_type'}, status=400)

    qs = DiscussionReaction.objects.filter(
        discussion=discussion, user=user, reaction_type=reaction_type)
    if qs.exists():
        qs.delete()
    else:
        DiscussionReaction.objects.create(
            discussion=discussion, user=user, reaction_type=reaction_type)

    reactions = {
        'appreciate': DiscussionReaction.objects.filter(discussion=discussion, reaction_type='appreciate').count(),
        'insightful': DiscussionReaction.objects.filter(discussion=discussion, reaction_type='insightful').count(),
        'curious':    DiscussionReaction.objects.filter(discussion=discussion, reaction_type='curious').count(),
    }
    return Response({'reactions': reactions})


@api_view(['POST', 'DELETE'])
def discussion_save(request, discussion_id):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    discussion = get_object_or_404(Discussion, id=discussion_id)

    if request.method == 'POST':
        SavedDiscussion.objects.get_or_create(discussion=discussion, user=user)
        return Response({'is_saved': True})

    SavedDiscussion.objects.filter(discussion=discussion, user=user).delete()
    return Response({'is_saved': False})


# ─────────────────────────────────────────────────────────────────────────────
# Comments
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def discussion_comments(request, discussion_id):
    user       = _get_user(request)
    discussion = get_object_or_404(Discussion, id=discussion_id)

    if request.method == 'GET':
        comments = (
            Comment.objects
            .filter(discussion=discussion, parent=None)
            .select_related('author', 'discussion__space')
            .prefetch_related('replies__author')
        )
        return Response([c.to_dict() for c in comments])

    # POST — members only
    membership, err = _require_membership(discussion.space, user)
    if err:
        return err

    body = request.data.get('body', '').strip()
    if not body:
        return Response({'error': 'body is required'}, status=400)

    parent = None
    parent_id = request.data.get('parent_comment_id')
    if parent_id:
        parent = get_object_or_404(Comment, id=parent_id, discussion=discussion)

    comment = Comment.objects.create(
        discussion=discussion, author=user, body=body, parent=parent)
    return Response(comment.to_dict(), status=201)


@api_view(['POST'])
def comment_react(request, comment_id):
    user = _get_user(request)
    if not user:
        return Response({'error': 'Authentication required'}, status=401)

    comment       = get_object_or_404(Comment, id=comment_id)
    reaction_type = request.data.get('reaction_type', '')

    if reaction_type not in ('appreciate', 'insightful', 'curious'):
        return Response({'error': 'Invalid reaction_type'}, status=400)

    qs = CommentReaction.objects.filter(
        comment=comment, user=user, reaction_type=reaction_type)
    if qs.exists():
        qs.delete()
    else:
        CommentReaction.objects.create(
            comment=comment, user=user, reaction_type=reaction_type)

    reactions = {
        'appreciate': CommentReaction.objects.filter(comment=comment, reaction_type='appreciate').count(),
        'insightful': CommentReaction.objects.filter(comment=comment, reaction_type='insightful').count(),
        'curious':    CommentReaction.objects.filter(comment=comment, reaction_type='curious').count(),
    }
    return Response({'reactions': reactions})
