

#/rooms/views.python
import uuid
import asyncio
import threading

from urllib.parse import urlparse

from django.conf import settings
from django.db.models import F
from livekit import api as livekit_api
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rooms import redis_client as rc
from users.models import User, Follow


def _rewrite_media_url(request, url: str) -> str:
    """Replace the host in a stored media URL with the current request's host."""
    if not url:
        return ''
    try:
        parsed = urlparse(url)
        if parsed.path.startswith(settings.MEDIA_URL):
            return request.build_absolute_uri(parsed.path)
    except Exception:
        pass
    return url

LIVEKIT_API_KEY    = settings.LIVEKIT_API_KEY
LIVEKIT_API_SECRET = settings.LIVEKIT_API_SECRET
LIVEKIT_HOST       = settings.LIVEKIT_HOST


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


# ─────────────────────────────────────────────────────────────────────────────
# LiveKit SDK helpers — using the official async SDK exactly as before
# ─────────────────────────────────────────────────────────────────────────────

async def _lk_update_permissions(lk_room, identity, can_publish,
                                  can_publish_data=True):
    lk_client = livekit_api.LiveKitAPI(
        LIVEKIT_HOST, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await lk_client.room.update_participant(
            livekit_api.UpdateParticipantRequest(
                room=lk_room,
                identity=identity,
                permission=livekit_api.ParticipantPermission(
                    can_publish=can_publish,
                    can_subscribe=True,
                    can_publish_data=can_publish_data,
                ),
            )
        )
        print(f'[lk] ✅ {identity} canPublish={can_publish}')
    finally:
        await lk_client.aclose()


async def _lk_broadcast_chat_state(lk_room: str, disabled: bool):
    """Send a chat_disabled / chat_enabled data packet to every participant
    in the room using the LiveKit server API (reliable, server-authoritative)."""
    import json
    lk_client = livekit_api.LiveKitAPI(
        LIVEKIT_HOST, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        msg_type = 'chat_disabled' if disabled else 'chat_enabled'
        data = json.dumps({'type': msg_type}).encode('utf-8')
        await lk_client.room.send_data(
            livekit_api.SendDataRequest(
                room=lk_room,
                data=data,
                kind=0,  # DataPacketKind.RELIABLE = 0
            )
        )
        print(f'[chat] server broadcast {msg_type} → {lk_room}')
    finally:
        await lk_client.aclose()


async def _lk_remove_participant(lk_room, identity):
    lk_client = livekit_api.LiveKitAPI(
        LIVEKIT_HOST, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await lk_client.room.remove_participant(
            livekit_api.RoomParticipantIdentity(
                room=lk_room,
                identity=identity,
            )
        )
        print(f'[lk] ✅ removed {identity}')
    finally:
        await lk_client.aclose()


# ─────────────────────────────────────────────────────────────────────────────
# Rooms
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def rooms(request):
    if request.method == 'GET':
        rc.prune_expired()
        user  = _get_user(request)
        q     = request.GET.get('q', '').strip()
        raw_rooms = rc.get_all_rooms(q=q)
        enriched_rooms = []
        for room in raw_rooms:
            room_copy = dict(room)
            room_copy['space_id'] = room.get('space_id', '')
            host = User.objects.filter(id=room.get('host_id', '')).first()
            if host:
                raw_url = host.avatar_url or ''
                room_copy['host_avatar_url'] = _rewrite_media_url(request, raw_url)
            else:
                room_copy['host_avatar_url'] = ''
            if user is not None and host:
                room_copy['is_following_host'] = Follow.objects.filter(
                    follower=user, following=host).exists()
                room_copy['host_is_following_me'] = Follow.objects.filter(
                    follower=host, following=user).exists()
            else:
                room_copy['is_following_host'] = False
                room_copy['host_is_following_me'] = False
            enriched_rooms.append(room_copy)
        return Response(enriched_rooms)

    data      = request.data
    title     = data.get('title',     '').strip()
    category  = data.get('category',  '').strip()
    host_id   = data.get('host_id',   '').strip()
    host_name = data.get('host_name', '').strip()
    space_id  = data.get('space_id',  '').strip()

    errors = {}
    if not title:     errors['title']     = 'Title is required'
    if not category:  errors['category']  = 'Category is required'
    if not host_id:   errors['host_id']   = 'host_id is required'
    if not host_name: errors['host_name'] = 'host_name is required'
    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    room = rc.create_room(title=title, category=category,
                          host_id=host_id, host_name=host_name,
                          space_id=space_id)
    print(f'[create] room={room["id"]} host={host_id}')

    # Send push notifications to the host's followers in a background thread.
    # We use a thread so the API responds instantly — the host shouldn't wait
    # for FCM before their room is created. Fire-and-forget is fine here.
    def _notify():
        try:
            from users.models import User
            from notifications import send_room_created_notification
            host_user = User.objects.get(id=host_id)
            send_room_created_notification(host_user, room)
        except Exception as e:
            print(f'[notify] Failed to send notifications: {e}')

    threading.Thread(target=_notify, daemon=True).start()

    return Response(room, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
def room_detail(request, room_id):
    if request.method == 'GET':
        room = rc.get_room(room_id)
        if not room:
            return Response({'error': 'Room not found'}, status=404)
        return Response(room)

    room    = rc.get_room(room_id)
    deleted = rc.delete_room(room_id)
    if not deleted:
        return Response({'error': 'Room not found'}, status=404)

    if room:
        try:
            host_id = room.get('host_id', '')
            if host_id:
                User.objects.filter(id=host_id).update(talks_hosted=F('talks_hosted') + 1)
        except Exception as e:
            print(f'[talks_hosted] increment failed: {e}')

        # Hard-delete all chat messages for this room from MongoDB.
        try:
            from rooms import mongo_client as mc
            deleted = mc.delete_room_messages(room_id)
            print(f'[delete] purged {deleted} chat messages for room {room_id}')
        except Exception as e:
            print(f'[delete] mongo chat cleanup failed: {e}')

    return Response({'message': 'Room closed'})


@api_view(['GET'])
def get_token(request):
    identity    = request.query_params.get('identity', f'user-{uuid.uuid4().hex[:6]}')
    room        = request.query_params.get('room', f'room-{uuid.uuid4().hex[:6]}')
    name        = request.query_params.get('name', identity)
    role        = request.query_params.get('role', 'listener')
    can_publish = role in ('host', 'speaker')

    token = (
        livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(livekit_api.VideoGrants(
            room_join=True, room=room,
            can_publish=can_publish, can_subscribe=True,
            can_publish_data=True,
        ))
    )
    return Response({'token': token.to_jwt(), 'room': room,
                     'identity': identity, 'role': role})


@api_view(['POST'])
def join_room(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)

    identity = request.data.get('identity', f'user-{uuid.uuid4().hex[:6]}')
    name     = request.data.get('name', identity)
    role     = request.data.get('role', 'listener')

    if rc.is_banned(room_id, identity):
        print(f'[join] ❌ Banned: {identity}')
        return Response({'error': 'You have been removed from this room — BANNED'},
                        status=status.HTTP_403_FORBIDDEN)

    if role == 'listener':
        rc.increment_listeners(room_id)

    can_publish = role in ('host', 'speaker')
    token = (
        livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(livekit_api.VideoGrants(
            room_join=True,
            room=room['livekit_room_name'],
            can_publish=can_publish,
            can_subscribe=True,
            can_publish_data=True,
        ))
    )

    # For hosts: generate a short-lived admin token so the host device
    # can call LiveKit's UpdateParticipant API directly — no Django round trip.
    # This makes promote/demote instant regardless of where participants are.
    admin_token = None
    if role == 'host':
        admin_token = (
            livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_grants(livekit_api.VideoGrants(
                room_admin=True,
                room=room['livekit_room_name'],
            ))
        ).to_jwt()

    print(f'[join] room={room_id} identity={identity} role={role} admin_token={"yes" if admin_token else "no"}')
    return Response({
        'room':        room,
        'token':       token.to_jwt(),
        'identity':    identity,
        'role':        role,
        'admin_token': admin_token,
    })


@api_view(['POST'])
def leave_room(request, room_id):
    role = request.data.get('role', 'listener')
    if role == 'listener':
        rc.decrement_listeners(room_id)
    return Response({'message': 'Left room'})


# ─────────────────────────────────────────────────────────────────────────────
# Promotion / demotion
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def promote_participant(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)

    identity = request.data.get('identity', '').strip()
    if not identity:
        return Response({'error': 'identity required'}, status=400)

    try:
        asyncio.run(_lk_update_permissions(
            room['livekit_room_name'], identity, can_publish=True))
    except Exception as e:
        print(f'[promote] ❌ {e}')
        return Response({'error': str(e)}, status=500)

    return Response({'message': f'{identity} promoted', 'identity': identity})


@api_view(['POST'])
def demote_participant(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)

    identity = request.data.get('identity', '').strip()
    if not identity:
        return Response({'error': 'identity required'}, status=400)

    try:
        asyncio.run(_lk_update_permissions(
            room['livekit_room_name'], identity, can_publish=False))
    except Exception as e:
        print(f'[demote] ❌ {e}')
        return Response({'error': str(e)}, status=500)

    return Response({'message': f'{identity} demoted', 'identity': identity})


# ─────────────────────────────────────────────────────────────────────────────
# Moderation
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def kick_participant(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)

    identity = request.data.get('identity', '').strip()
    if not identity:
        return Response({'error': 'identity required'}, status=400)

    rc.ban_user(room_id, identity)

    try:
        asyncio.run(_lk_remove_participant(room['livekit_room_name'], identity))
    except Exception as e:
        print(f'[kick] ❌ {e}')

    return Response({'message': f'{identity} kicked', 'identity': identity})


@api_view(['POST'])
def mute_participant(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)

    identity = request.data.get('identity', '').strip()
    if not identity:
        return Response({'error': 'identity required'}, status=400)

    rc.mute_user(room_id, identity)
    try:
        asyncio.run(_lk_update_permissions(
            room['livekit_room_name'], identity,
            can_publish=False, can_publish_data=True))
    except Exception as e:
        print(f'[mute] ❌ {e}')
        return Response({'error': str(e)}, status=500)

    return Response({'message': f'{identity} muted', 'identity': identity})


@api_view(['POST'])
def unmute_participant(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)

    identity = request.data.get('identity', '').strip()
    if not identity:
        return Response({'error': 'identity required'}, status=400)

    rc.unmute_user(room_id, identity)
    try:
        asyncio.run(_lk_update_permissions(
            room['livekit_room_name'], identity,
            can_publish=True, can_publish_data=True))
    except Exception as e:
        print(f'[unmute] ❌ {e}')
        return Response({'error': str(e)}, status=500)

    return Response({'message': f'{identity} unmuted', 'identity': identity})


@api_view(['POST'])
def disable_chat(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)
    rc.set_chat_disabled(room_id, True)
    # Hard-delete chat history so a fresh slate appears if chat is re-enabled.
    try:
        from rooms import mongo_client as mc
        mc.delete_room_messages(room_id)
    except Exception as e:
        print(f'[chat] mongo delete failed: {e}')
    # Server-side broadcast so all connected clients update immediately.
    try:
        asyncio.run(_lk_broadcast_chat_state(room['livekit_room_name'], True))
    except Exception as e:
        print(f'[chat] broadcast failed: {e}')
    return Response({'chat_disabled': True})


@api_view(['POST'])
def enable_chat(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)
    rc.set_chat_disabled(room_id, False)
    try:
        asyncio.run(_lk_broadcast_chat_state(room['livekit_room_name'], False))
    except Exception as e:
        print(f'[chat] broadcast failed: {e}')
    return Response({'chat_disabled': False})


@api_view(['GET', 'POST'])
def room_messages(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)

    try:
        from rooms import mongo_client as mc
    except Exception as e:
        return Response({'error': f'MongoDB unavailable: {e}'}, status=503)

    if request.method == 'GET':
        try:
            messages = mc.get_messages(room_id)
            return Response({'messages': messages})
        except Exception as e:
            print(f'[chat] mongo get failed: {e}')
            return Response({'messages': []})

    # POST — save a single message
    sender_id   = (request.data.get('sender_id')   or '').strip()
    sender_name = (request.data.get('sender_name') or '').strip()
    text        = (request.data.get('text')        or '').strip()
    msg_type    = (request.data.get('message_type') or 'text').strip()

    if not sender_id or not sender_name or not text:
        return Response({'error': 'sender_id, sender_name and text are required'},
                        status=400)
    if rc.is_chat_disabled(room_id):
        return Response({'error': 'Chat is disabled'}, status=403)

    try:
        msg_id = mc.save_message(room_id, sender_id, sender_name, text, msg_type)
        return Response({'id': msg_id}, status=201)
    except Exception as e:
        print(f'[chat] mongo save failed: {e}')
        return Response({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# Raise-hand queue
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Room lifecycle
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def heartbeat(request, room_id):
    """
    Host-only ping sent every 60 s to prove the room is still live.
    If the backend stops receiving pings for HEARTBEAT_TIMEOUT seconds,
    the background reaper will close the room automatically.
    """
    if not rc.get_room(room_id):
        return Response({'error': 'Room not found'}, status=404)
    rc.update_heartbeat(room_id)
    return Response({'ok': True})


@api_view(['POST'])
def sync_count(request, room_id):
    """
    Overwrite listener_count with the authoritative headcount from the host's
    LiveKit client. Called whenever a participant joins or leaves — including
    crash-disconnects that never hit /leave/.
    """
    if not rc.get_room(room_id):
        return Response({'error': 'Room not found'}, status=404)
    count = request.data.get('listener_count')
    if count is None:
        return Response({'error': 'listener_count required'}, status=400)
    try:
        count = int(count)
    except (TypeError, ValueError):
        return Response({'error': 'listener_count must be an integer'}, status=400)
    rc.set_listener_count(room_id, count)
    return Response({'listener_count': max(0, count)})


# ─────────────────────────────────────────────────────────────────────────────
# Raise-hand queue
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def raise_hands(request, room_id):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)
    if request.method == 'GET':
        return Response({'queue': rc.get_raise_hands(room_id)})
    identity     = request.data.get('identity', '').strip()
    display_name = request.data.get('display_name', identity).strip()
    if not identity:
        return Response({'error': 'identity required'}, status=400)
    rc.add_raise_hand(room_id, identity, display_name)
    return Response({'message': 'Raise hand recorded'})


@api_view(['DELETE'])
def remove_raise_hand(request, room_id, identity):
    room = rc.get_room(room_id)
    if not room:
        return Response({'error': 'Room not found'}, status=404)
    rc.remove_raise_hand(room_id, identity)
    return Response({'message': 'Raise hand removed'})