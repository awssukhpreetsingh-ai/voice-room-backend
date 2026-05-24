import os
import uuid
import json
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sock import Sock
# import livekit.api as api 
from livekit import api
from dotenv import load_dotenv
import sqlite3

load_dotenv()

app = Flask(__name__)
CORS(app)
sock = Sock(app)

LIVEKIT_API_KEY    = os.getenv("LIVEKIT_API_KEY",    "APIgcHVczTcYFxW")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "5dGJyWaRGzV2Yx0E4OG6OJvvac4nrRIsdESH03cTSHG")
LIVEKIT_HOST       = os.getenv("LIVEKIT_HOST",       "https://your-project.livekit.cloud")

DB_PATH = "wavroom.db"

# ─────────────────────────────────────────────
# WebSocket connections per room
# { room_id: [ ws_connection, ... ] }
# ─────────────────────────────────────────────
room_connections: dict[str, list] = {}


# ═══════════════════════════════════════════════
# DATABASE SETUP
# ═══════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # lets us do row["column_name"]
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                category    TEXT NOT NULL,
                host_id     TEXT NOT NULL,
                host_name   TEXT NOT NULL,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS hand_raises (
                id          TEXT PRIMARY KEY,
                room_id     TEXT NOT NULL,
                identity    TEXT NOT NULL,
                display_name TEXT NOT NULL,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT NOT NULL
            )
        """)
        db.commit()

init_db()


# ═══════════════════════════════════════════════
# HELPER — format room row as dict
# ═══════════════════════════════════════════════
def room_to_dict(row):
    return {
        "id":         row["id"],
        "title":      row["title"],
        "category":   row["category"],
        "host_id":    row["host_id"],
        "host_name":  row["host_name"],
        "is_active":  bool(row["is_active"]),
        "created_at": row["created_at"],
    }


# ═══════════════════════════════════════════════
# HELPER — broadcast WS message to a room
# ═══════════════════════════════════════════════
def broadcast(room_id: str, payload: dict):
    dead = []
    for ws in room_connections.get(room_id, []):
        try:
            ws.send(json.dumps(payload))
        except Exception:
            dead.append(ws)
    # remove dead connections
    for ws in dead:
        room_connections[room_id].remove(ws)


# ═══════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════

# ── GET /rooms ──────────────────────────────────
# Returns list of active rooms
@app.route("/rooms", methods=["GET"])
def list_rooms():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM rooms WHERE is_active = 1 ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([room_to_dict(r) for r in rows])


# ── POST /rooms ─────────────────────────────────
# Creates a new room
# Body: { title, category, host_id, host_name }
@app.route("/rooms", methods=["POST"])
def create_room():
    data = request.get_json()
    room_id = f"room-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        db.execute(
            "INSERT INTO rooms (id, title, category, host_id, host_name, created_at) VALUES (?,?,?,?,?,?)",
            (room_id, data["title"], data["category"], data["host_id"], data["host_name"], now)
        )
        db.commit()

    return jsonify({"room_id": room_id, "message": "Room created"}), 201


# ── DELETE /rooms/<room_id> ──────────────────────
# Host closes the room
@app.route("/rooms/<room_id>", methods=["DELETE"])
def close_room(room_id):
    with get_db() as db:
        db.execute("UPDATE rooms SET is_active = 0 WHERE id = ?", (room_id,))
        db.commit()

    # Notify everyone in the room that it closed
    broadcast(room_id, {"type": "room_closed"})
    return jsonify({"message": "Room closed"})


# ── GET /get-token ───────────────────────────────
# Returns a LiveKit JWT for a given room + identity
# Query: ?room=<room_id>&identity=<user_id>&name=<display_name>&role=host|speaker|listener
@app.route("/get-token", methods=["GET"])
def get_token():
    identity = request.args.get("identity", f"user-{uuid.uuid4().hex[:6]}")
    room     = request.args.get("room",     f"room-{uuid.uuid4().hex[:6]}")
    name     = request.args.get("name",     identity)
    role     = request.args.get("role",     "listener")  # host | speaker | listener

    # Hosts and speakers can publish audio; listeners cannot
    can_publish = role in ("host", "speaker")

    print(f"Token: room={room}, identity={identity}, role={role}, can_publish={can_publish}")

    token = (
        livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(livekit_api.VideoGrants(
            room_join=True,
            room=room,
            can_publish=can_publish,
            can_subscribe=True,
        ))
    )

    return jsonify({
        "token":    token.to_jwt(),
        "room":     room,
        "identity": identity,
        "role":     role,
    })


# ── POST /rooms/<room_id>/raise-hand ────────────
# Listener raises hand
# Body: { identity, display_name }
@app.route("/rooms/<room_id>/raise-hand", methods=["POST"])
def raise_hand(room_id):
    data = request.get_json()
    raise_id = uuid.uuid4().hex
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        db.execute(
            "INSERT INTO hand_raises (id, room_id, identity, display_name, created_at) VALUES (?,?,?,?,?)",
            (raise_id, room_id, data["identity"], data["display_name"], now)
        )
        db.commit()

    # Push WS notification to everyone in the room (especially the host)
    broadcast(room_id, {
        "type":         "hand_raised",
        "raise_id":     raise_id,
        "identity":     data["identity"],
        "display_name": data["display_name"],
    })

    return jsonify({"raise_id": raise_id, "message": "Hand raised"})


# ── POST /rooms/<room_id>/allow-speaker ─────────
# Host approves a hand raise → updates LiveKit permissions
# Body: { identity }
@app.route("/rooms/<room_id>/allow-speaker", methods=["POST"])
def allow_speaker(room_id):
    data     = request.get_json()
    identity = data["identity"]

    # Update hand_raise status in DB
    with get_db() as db:
        db.execute(
            "UPDATE hand_raises SET status = 'approved' WHERE room_id = ? AND identity = ? AND status = 'pending'",
            (room_id, identity)
        )
        db.commit()

    # Update LiveKit participant permissions via server API
    lk_client = livekit_api.LiveKitAPI(
        LIVEKIT_HOST,
        LIVEKIT_API_KEY,
        LIVEKIT_API_SECRET,
    )

    async def _update():
        await lk_client.room.update_participant(
            livekit_api.UpdateParticipantRequest(
                room=room_id,
                identity=identity,
                permission=livekit_api.ParticipantPermission(
                    can_publish=True,
                    can_subscribe=True,
                ),
            )
        )
        await lk_client.aclose()

    asyncio.run(_update())

    # Tell all WS clients that this person was promoted
    broadcast(room_id, {
        "type":     "speaker_allowed",
        "identity": identity,
    })

    return jsonify({"message": f"{identity} is now a speaker"})


# ── GET /rooms/<room_id>/hand-raises ────────────
# Returns pending hand raises for a room (for host view)
@app.route("/rooms/<room_id>/hand-raises", methods=["GET"])
def get_hand_raises(room_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM hand_raises WHERE room_id = ? AND status = 'pending' ORDER BY created_at ASC",
            (room_id,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ═══════════════════════════════════════════════
# WEBSOCKET — /ws/room/<room_id>
# Each Flutter client connects here on room entry
# ═══════════════════════════════════════════════
@sock.route("/ws/room/<room_id>")
def room_ws(ws, room_id):
    # Register this connection
    if room_id not in room_connections:
        room_connections[room_id] = []
    room_connections[room_id].append(ws)
    print(f"WS connected: room={room_id}, total={len(room_connections[room_id])}")

    try:
        while True:
            raw = ws.receive()
            if raw is None:
                break
            msg = json.loads(raw)
            print(f"WS message in {room_id}: {msg}")

            # Forward all messages to the rest of the room
            # (Flutter handles type-based routing on the client side)
            broadcast(room_id, msg)

    except Exception as e:
        print(f"WS error: {e}")
    finally:
        if room_id in room_connections and ws in room_connections[room_id]:
            room_connections[room_id].remove(ws)
        print(f"WS disconnected: room={room_id}")


# ═══════════════════════════════════════════════
if __name__ == "__main__":
    app.run(port=5001, debug=True)