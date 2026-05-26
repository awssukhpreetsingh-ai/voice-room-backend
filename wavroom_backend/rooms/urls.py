

#/rooms/urls.py

from django.urls import path
from rooms import views

urlpatterns = [
    # Room CRUD
    path('rooms/',                              views.rooms,               name='rooms'),
    path('rooms/<str:room_id>/',               views.room_detail,         name='room-detail'),

    # Join / leave
    path('rooms/<str:room_id>/join/',          views.join_room,           name='join-room'),
    path('rooms/<str:room_id>/leave/',         views.leave_room,          name='leave-room'),

    # Stage management
    path('rooms/<str:room_id>/promote/',       views.promote_participant,  name='promote'),
    path('rooms/<str:room_id>/demote/',        views.demote_participant,   name='demote'),

    # Moderation
    path('rooms/<str:room_id>/kick/',          views.kick_participant,     name='kick'),
    path('rooms/<str:room_id>/mute/',          views.mute_participant,     name='mute'),
    path('rooms/<str:room_id>/unmute/',        views.unmute_participant,   name='unmute'),
    path('rooms/<str:room_id>/chat/disable/',   views.disable_chat,  name='chat-disable'),
    path('rooms/<str:room_id>/chat/enable/',    views.enable_chat,   name='chat-enable'),
    path('rooms/<str:room_id>/chat/messages/',  views.room_messages, name='chat-messages'),

    # LiveKit token
    path('token/',                             views.get_token,           name='get-token'),

    # Room lifecycle
    path('rooms/<str:room_id>/heartbeat/',   views.heartbeat,   name='heartbeat'),
    path('rooms/<str:room_id>/sync_count/',  views.sync_count,  name='sync-count'),

    # Raise-hand queue (persisted in Redis)
    path('rooms/<str:room_id>/raise_hands/',                    views.raise_hands,        name='raise-hands'),
    path('rooms/<str:room_id>/raise_hands/<str:identity>/',     views.remove_raise_hand,  name='raise-hands-remove'),
]