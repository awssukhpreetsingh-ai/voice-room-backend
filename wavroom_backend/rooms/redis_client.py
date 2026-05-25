# # import json
# # import uuid
# # import redis
# # from datetime import datetime
# # from django.conf import settings

# # # ── Single Redis connection (reused across requests) ──
# # _redis = redis.Redis(
# #     host=settings.REDIS_HOST,
# #     port=settings.REDIS_PORT,
# #     db=settings.REDIS_DB,
# #     decode_responses=True,   # always return str, not bytes
# # )

# # def get_redis():
# #     return _redis


# # # ═══════════════════════════════════════════════
# # # Key scheme
# # #   rooms:list          → Redis Set  of all active room IDs
# # #   rooms:data:{id}     → Redis Hash of room fields
# # # ═══════════════════════════════════════════════

# # ROOMS_SET  = 'rooms:list'
# # ROOM_KEY   = lambda room_id: f'rooms:data:{room_id}'
# # TTL        = settings.ROOM_TTL_SECONDS   # 86400 = 24 h


# # # ── Create ─────────────────────────────────────
# # def create_room(title: str, category: str, host_id: str, host_name: str) -> dict:
# #     room_id          = uuid.uuid4().hex[:10]
# #     livekit_room_name = f'room-{room_id}'
# #     now              = datetime.utcnow().isoformat()

# #     room = {
# #         'id':                room_id,
# #         'title':             title,
# #         'category':          category,
# #         'host_id':           host_id,
# #         'host_name':         host_name,
# #         'livekit_room_name': livekit_room_name,
# #         'listener_count':    '0',
# #         'created_at':        now,
# #     }

# #     r = get_redis()
# #     pipe = r.pipeline()
# #     pipe.hset(ROOM_KEY(room_id), mapping=room)  # store fields as hash
# #     pipe.expire(ROOM_KEY(room_id), TTL)          # auto-expire after 24 h
# #     pipe.sadd(ROOMS_SET, room_id)                # add to active set
# #     pipe.execute()

# #     return _hash_to_dict(room)


# # # ── Get all active rooms ───────────────────────
# # def get_all_rooms() -> list[dict]:
# #     r = get_redis()
# #     room_ids = r.smembers(ROOMS_SET)

# #     rooms = []
# #     pipe  = r.pipeline()
# #     for rid in room_ids:
# #         pipe.hgetall(ROOM_KEY(rid))
# #     results = pipe.execute()

# #     for data in results:
# #         if data:                            # skip if TTL expired but set not cleaned
# #             rooms.append(_hash_to_dict(data))

# #     # Sort newest first
# #     rooms.sort(key=lambda x: x.get('created_at', ''), reverse=True)
# #     return rooms


# # # ── Get single room ────────────────────────────
# # def get_room(room_id: str) -> dict | None:
# #     r    = get_redis()
# #     data = r.hgetall(ROOM_KEY(room_id))
# #     return _hash_to_dict(data) if data else None


# # # ── Delete room ────────────────────────────────
# # def delete_room(room_id: str) -> bool:
# #     r = get_redis()
# #     pipe = r.pipeline()
# #     pipe.delete(ROOM_KEY(room_id))
# #     pipe.srem(ROOMS_SET, room_id)
# #     results = pipe.execute()
# #     return results[0] > 0   # True if the key existed


# # # ── Increment / decrement listener count ───────
# # def increment_listeners(room_id: str):
# #     get_redis().hincrby(ROOM_KEY(room_id), 'listener_count', 1)

# # def decrement_listeners(room_id: str):
# #     r   = get_redis()
# #     val = int(r.hget(ROOM_KEY(room_id), 'listener_count') or 0)
# #     if val > 0:
# #         r.hincrby(ROOM_KEY(room_id), 'listener_count', -1)


# # # ── Clean up expired rooms from the set ────────
# # # Call this periodically or on list fetch
# # def prune_expired():
# #     r        = get_redis()
# #     room_ids = r.smembers(ROOMS_SET)
# #     for rid in room_ids:
# #         if not r.exists(ROOM_KEY(rid)):    # hash expired but ID still in set
# #             r.srem(ROOMS_SET, rid)


# # # ── Internal: Redis hash → clean Python dict ───
# # def _hash_to_dict(data: dict) -> dict:
# #     return {
# #         'id':                data.get('id', ''),
# #         'title':             data.get('title', ''),
# #         'category':          data.get('category', ''),
# #         'host_id':           data.get('host_id', ''),
# #         'host_name':         data.get('host_name', ''),
# #         'livekit_room_name': data.get('livekit_room_name', ''),
# #         'listener_count':    int(data.get('listener_count', 0)),
# #         'created_at':        data.get('created_at', ''),
# #     }


# import json
# import uuid
# import redis
# from datetime import datetime
# from django.conf import settings

# _redis = redis.Redis(
#     host=settings.REDIS_HOST,
#     port=settings.REDIS_PORT,
#     db=settings.REDIS_DB,
#     decode_responses=True,
# )

# def get_redis():
#     return _redis

# ROOMS_SET = 'rooms:list'
# ROOM_KEY  = lambda room_id: f'rooms:data:{room_id}'
# TTL       = settings.ROOM_TTL_SECONDS


# def create_room(title, category, host_id, host_name):
#     room_id           = uuid.uuid4().hex[:10]
#     livekit_room_name = f'room-{room_id}'
#     now               = datetime.utcnow().isoformat()

#     room = {
#         'id':                room_id,
#         'title':             title,
#         'category':          category,
#         'host_id':           host_id,
#         'host_name':         host_name,
#         'livekit_room_name': livekit_room_name,
#         'listener_count':    '0',
#         'created_at':        now,
#         # New moderation fields
#         'banned_users':      '[]',   # JSON list of identity strings
#         'muted_users':       '[]',   # JSON list of identity strings
#         'chat_disabled':     'false',
#     }

#     r = get_redis()
#     pipe = r.pipeline()
#     pipe.hset(ROOM_KEY(room_id), mapping=room)
#     pipe.expire(ROOM_KEY(room_id), TTL)
#     pipe.sadd(ROOMS_SET, room_id)
#     pipe.execute()

#     return _hash_to_dict(room)


# def get_all_rooms():
#     r        = get_redis()
#     room_ids = r.smembers(ROOMS_SET)
#     rooms    = []
#     pipe     = r.pipeline()
#     for rid in room_ids:
#         pipe.hgetall(ROOM_KEY(rid))
#     for data in pipe.execute():
#         if data:
#             rooms.append(_hash_to_dict(data))
#     rooms.sort(key=lambda x: x.get('created_at', ''), reverse=True)
#     return rooms


# def get_room(room_id):
#     data = get_redis().hgetall(ROOM_KEY(room_id))
#     return _hash_to_dict(data) if data else None


# def delete_room(room_id):
#     r = get_redis()
#     pipe = r.pipeline()
#     pipe.delete(ROOM_KEY(room_id))
#     pipe.srem(ROOMS_SET, room_id)
#     results = pipe.execute()
#     return results[0] > 0


# def increment_listeners(room_id):
#     get_redis().hincrby(ROOM_KEY(room_id), 'listener_count', 1)


# def decrement_listeners(room_id):
#     r   = get_redis()
#     val = int(r.hget(ROOM_KEY(room_id), 'listener_count') or 0)
#     if val > 0:
#         r.hincrby(ROOM_KEY(room_id), 'listener_count', -1)


# def prune_expired():
#     r        = get_redis()
#     room_ids = r.smembers(ROOMS_SET)
#     for rid in room_ids:
#         if not r.exists(ROOM_KEY(rid)):
#             r.srem(ROOMS_SET, rid)


# # ── Moderation helpers ─────────────────────────

# def ban_user(room_id, identity):
#     """Add identity to banned list. Returns updated list."""
#     r    = get_redis()
#     raw  = r.hget(ROOM_KEY(room_id), 'banned_users') or '[]'
#     lst  = json.loads(raw)
#     if identity not in lst:
#         lst.append(identity)
#         r.hset(ROOM_KEY(room_id), 'banned_users', json.dumps(lst))
#     return lst


# def is_banned(room_id, identity):
#     r   = get_redis()
#     raw = r.hget(ROOM_KEY(room_id), 'banned_users') or '[]'
#     return identity in json.loads(raw)


# def mute_user(room_id, identity):
#     r   = get_redis()
#     raw = r.hget(ROOM_KEY(room_id), 'muted_users') or '[]'
#     lst = json.loads(raw)
#     if identity not in lst:
#         lst.append(identity)
#         r.hset(ROOM_KEY(room_id), 'muted_users', json.dumps(lst))
#     return lst


# def unmute_user(room_id, identity):
#     r   = get_redis()
#     raw = r.hget(ROOM_KEY(room_id), 'muted_users') or '[]'
#     lst = json.loads(raw)
#     if identity in lst:
#         lst.remove(identity)
#         r.hset(ROOM_KEY(room_id), 'muted_users', json.dumps(lst))
#     return lst


# def is_muted(room_id, identity):
#     r   = get_redis()
#     raw = r.hget(ROOM_KEY(room_id), 'muted_users') or '[]'
#     return identity in json.loads(raw)


# def set_chat_disabled(room_id, disabled: bool):
#     get_redis().hset(ROOM_KEY(room_id), 'chat_disabled',
#                      'true' if disabled else 'false')


# def is_chat_disabled(room_id):
#     r   = get_redis()
#     val = r.hget(ROOM_KEY(room_id), 'chat_disabled') or 'false'
#     return val == 'true'


# def _hash_to_dict(data):
#     return {
#         'id':                data.get('id', ''),
#         'title':             data.get('title', ''),
#         'category':          data.get('category', ''),
#         'host_id':           data.get('host_id', ''),
#         'host_name':         data.get('host_name', ''),
#         'livekit_room_name': data.get('livekit_room_name', ''),
#         'listener_count':    int(data.get('listener_count', 0)),
#         'created_at':        data.get('created_at', ''),
#         'banned_users':      json.loads(data.get('banned_users', '[]')),
#         'muted_users':       json.loads(data.get('muted_users', '[]')),
#         'chat_disabled':     data.get('chat_disabled', 'false') == 'true',
#     }



# redis_client.py
#
# FIXES APPLIED:
# 1. Raise-hand queue stored as a Redis sorted set (score = timestamp).
#    This gives us: persistence across host reconnects, ordering by time,
#    and O(1) add/remove operations.
# 2. add_raise_hand / remove_raise_hand / get_raise_hands / clear_raise_hands
#    added as proper Redis operations.
# All existing functionality unchanged.

import json
import uuid
import redis
import time
from datetime import datetime
from django.conf import settings

_redis = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)

def get_redis():
    return _redis

ROOMS_SET      = 'rooms:list'
ROOM_KEY       = lambda room_id: f'rooms:data:{room_id}'
RAISE_HAND_KEY = lambda room_id: f'rooms:raise_hands:{room_id}'
TTL            = settings.ROOM_TTL_SECONDS


# Keys for per-room moderation sets (Redis SET, not JSON list).
# Using Redis sets eliminates the read-modify-write race condition that the
# old JSON list approach had under concurrent mute/ban operations.
BANNED_KEY = lambda room_id: f'rooms:banned:{room_id}'
MUTED_KEY  = lambda room_id: f'rooms:muted:{room_id}'


def create_room(title, category, host_id, host_name, space_id=None):
    room_id           = uuid.uuid4().hex[:10]
    livekit_room_name = f'room-{room_id}'
    now               = datetime.utcnow().isoformat()

    room = {
        'id':                room_id,
        'title':             title,
        'category':          category,
        'host_id':           host_id,
        'host_name':         host_name,
        'livekit_room_name': livekit_room_name,
        'listener_count':    '0',
        'created_at':        now,
        'last_heartbeat':    str(time.time()),  # initialised so new rooms aren't immediately reaped
        'chat_disabled':     'false',
        'space_id':          space_id or '',
    }

    r = get_redis()
    pipe = r.pipeline()
    pipe.hset(ROOM_KEY(room_id), mapping=room)
    pipe.expire(ROOM_KEY(room_id), TTL)
    pipe.sadd(ROOMS_SET, room_id)
    pipe.execute()

    return _hash_to_dict(room)


def get_all_rooms(q: str = ''):
    r        = get_redis()
    room_ids = r.smembers(ROOMS_SET)
    rooms    = []
    pipe     = r.pipeline()
    for rid in room_ids:
        pipe.hgetall(ROOM_KEY(rid))
    q_lower = q.lower().strip() if q else ''
    for data in pipe.execute():
        if not data:
            continue
        if q_lower:
            title_match = q_lower in data.get('title', '').lower()
            cat_match   = q_lower in data.get('category', '').lower()
            host_match  = q_lower in data.get('host_name', '').lower()
            if not (title_match or cat_match or host_match):
                continue
        rooms.append(_hash_to_dict(data))
    rooms.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return rooms


def get_room(room_id):
    data = get_redis().hgetall(ROOM_KEY(room_id))
    return _hash_to_dict(data) if data else None


def delete_room(room_id):
    r = get_redis()
    pipe = r.pipeline()
    pipe.delete(ROOM_KEY(room_id))
    pipe.delete(RAISE_HAND_KEY(room_id))
    pipe.delete(BANNED_KEY(room_id))
    pipe.delete(MUTED_KEY(room_id))
    pipe.srem(ROOMS_SET, room_id)
    results = pipe.execute()
    return results[0] > 0


def increment_listeners(room_id):
    get_redis().hincrby(ROOM_KEY(room_id), 'listener_count', 1)


def decrement_listeners(room_id):
    r = get_redis()
    # Clamp to 0 — can underflow if a client crashes without calling /leave/.
    new_val = r.hincrby(ROOM_KEY(room_id), 'listener_count', -1)
    if new_val < 0:
        r.hset(ROOM_KEY(room_id), 'listener_count', 0)


def prune_expired():
    """
    Only removes orphaned set entries — rooms whose Redis hash has expired
    (hit the 4-hour TTL) but whose ID is still in rooms:list.
    Rooms are NEVER auto-deleted by this function; only the host closing
    the room (DELETE /rooms/<id>/) removes an active room.
    """
    r        = get_redis()
    room_ids = r.smembers(ROOMS_SET)
    for rid in room_ids:
        if not r.exists(ROOM_KEY(rid)):
            r.delete(RAISE_HAND_KEY(rid))
            r.delete(BANNED_KEY(rid))
            r.delete(MUTED_KEY(rid))
            r.srem(ROOMS_SET, rid)
            print(f'[prune] swept TTL-expired room {rid}')


# ── Moderation ─────────────────────────────────
# banned_users and muted_users are stored as Redis SETs (BANNED_KEY / MUTED_KEY)
# rather than JSON-encoded lists inside the room hash. Redis SET operations
# (SADD, SREM, SISMEMBER) are atomic, eliminating the read-modify-write race
# that existed with the old JSON list approach under concurrent moderation calls.

def ban_user(room_id, identity):
    r = get_redis()
    r.sadd(BANNED_KEY(room_id), identity)
    r.expire(BANNED_KEY(room_id), TTL)


def is_banned(room_id, identity):
    return bool(get_redis().sismember(BANNED_KEY(room_id), identity))


def mute_user(room_id, identity):
    r = get_redis()
    r.sadd(MUTED_KEY(room_id), identity)
    r.expire(MUTED_KEY(room_id), TTL)


def unmute_user(room_id, identity):
    get_redis().srem(MUTED_KEY(room_id), identity)


def is_muted(room_id, identity):
    return bool(get_redis().sismember(MUTED_KEY(room_id), identity))


def get_banned_users(room_id):
    return list(get_redis().smembers(BANNED_KEY(room_id)))


def get_muted_users(room_id):
    return list(get_redis().smembers(MUTED_KEY(room_id)))


def set_chat_disabled(room_id, disabled: bool):
    get_redis().hset(ROOM_KEY(room_id), 'chat_disabled',
                     'true' if disabled else 'false')


def is_chat_disabled(room_id):
    r   = get_redis()
    val = r.hget(ROOM_KEY(room_id), 'chat_disabled') or 'false'
    return val == 'true'


# ── Raise-hand queue — NEW ─────────────────────
# Stored as a Redis sorted set:
#   key   = rooms:raise_hands:{room_id}
#   member = JSON string: {"identity": "...", "display_name": "..."}
#   score  = Unix timestamp (seconds) — preserves raise order

def add_raise_hand(room_id: str, identity: str, display_name: str):
    """Add or refresh a raise-hand entry. Uses current time as score."""
    r      = get_redis()
    member = json.dumps({'identity': identity, 'display_name': display_name})
    score  = time.time()
    r.zadd(RAISE_HAND_KEY(room_id), {member: score})
    # Expire the key alongside the room TTL
    r.expire(RAISE_HAND_KEY(room_id), TTL)


def remove_raise_hand(room_id: str, identity: str):
    """Remove a specific identity's raise-hand."""
    r       = get_redis()
    members = r.zrange(RAISE_HAND_KEY(room_id), 0, -1)
    for m in members:
        try:
            data = json.loads(m)
            if data.get('identity') == identity:
                r.zrem(RAISE_HAND_KEY(room_id), m)
                break
        except (json.JSONDecodeError, KeyError):
            continue


def get_raise_hands(room_id: str) -> list:
    """
    Return all pending raise-hands in chronological order.
    Each entry is {'identity': ..., 'display_name': ...}.
    """
    r       = get_redis()
    members = r.zrange(RAISE_HAND_KEY(room_id), 0, -1)
    result  = []
    for m in members:
        try:
            result.append(json.loads(m))
        except json.JSONDecodeError:
            continue
    return result


def clear_raise_hands(room_id: str):
    """Remove all raise-hands for a room (e.g. when room closes)."""
    get_redis().delete(RAISE_HAND_KEY(room_id))


# ── Heartbeat & count sync ──────────────────────

def update_heartbeat(room_id: str):
    """Refresh the room TTL so an active room never hits Redis expiry."""
    r = get_redis()
    r.hset(ROOM_KEY(room_id), 'last_heartbeat', str(time.time()))
    r.expire(ROOM_KEY(room_id), TTL)   # reset the 4-hour clock on every ping


def set_listener_count(room_id: str, count: int):
    """Overwrite listener_count with the authoritative value from LiveKit."""
    get_redis().hset(ROOM_KEY(room_id), 'listener_count', max(0, count))


def _hash_to_dict(data):
    return {
        'id':                data.get('id', ''),
        'title':             data.get('title', ''),
        'category':          data.get('category', ''),
        'host_id':           data.get('host_id', ''),
        'host_name':         data.get('host_name', ''),
        'livekit_room_name': data.get('livekit_room_name', ''),
        'listener_count':    int(data.get('listener_count', 0)),
        'created_at':        data.get('created_at', ''),
        'chat_disabled':     data.get('chat_disabled', 'false') == 'true',
        'space_id':          data.get('space_id', ''),
    }