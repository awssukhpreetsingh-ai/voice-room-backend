import os
import datetime
from pymongo import MongoClient, ASCENDING


_client = None


def _get_col():
    global _client
    if _client is None:
        uri = os.environ.get('MONGODB_URI', 'mongodb+srv://voice_room_user:yWBrT7XcqHSu57Hr@cluster0.2ma5955.mongodb.net/voice_room_db')
        if not uri:
            raise RuntimeError('MONGODB_URI environment variable is not set')
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Ensure the index exists (idempotent)
        _client['wavroom']['room_messages'].create_index(
            [('room_id', ASCENDING), ('timestamp', ASCENDING)]
        )
    return _client['wavroom']['room_messages']


def save_message(room_id: str, sender_id: str, sender_name: str,
                 text: str, message_type: str = 'text') -> str:
    col = _get_col()
    result = col.insert_one({
        'room_id':      room_id,
        'sender_id':    sender_id,
        'sender_name':  sender_name,
        'text':         text,
        'timestamp':    datetime.datetime.utcnow(),
        'message_type': message_type,
    })
    return str(result.inserted_id)


def get_messages(room_id: str) -> list:
    col = _get_col()
    docs = col.find({'room_id': room_id}, sort=[('timestamp', ASCENDING)])
    result = []
    for doc in docs:
        ts = doc['timestamp']
        result.append({
            'sender_id':    doc['sender_id'],
            'sender_name':  doc['sender_name'],
            'text':         doc['text'],
            'timestamp':    (ts.isoformat() + 'Z') if isinstance(ts, datetime.datetime) else str(ts),
            'message_type': doc.get('message_type', 'text'),
        })
    return result


def delete_room_messages(room_id: str) -> int:
    col = _get_col()
    result = col.delete_many({'room_id': room_id})
    return result.deleted_count
