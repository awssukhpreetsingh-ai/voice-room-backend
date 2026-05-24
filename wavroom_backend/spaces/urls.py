from django.urls import path
from spaces import views

urlpatterns = [
    # ── Global search ────────────────────────────────────────────────────────
    path('search/',                                             views.global_search,               name='global-search'),

    # ── Spaces ───────────────────────────────────────────────────────────────
    path('spaces/',                                            views.spaces_list,                  name='spaces-list'),
    path('spaces/<str:space_id>/',                             views.space_detail,                 name='space-detail'),
    path('spaces/<str:space_id>/join/',                        views.space_join,                   name='space-join'),
    path('spaces/<str:space_id>/members/',                     views.space_members,                name='space-members'),
    path('spaces/<str:space_id>/promote/',                     views.space_promote,                name='space-promote'),
    path('spaces/<str:space_id>/analytics/',                   views.space_analytics,              name='space-analytics'),
    path('spaces/<str:space_id>/report/',                      views.space_report,                 name='space-report'),
    path('spaces/<str:space_id>/archive/',                     views.space_archive,                name='space-archive'),

    # ── Rooms within a space ─────────────────────────────────────────────────
    path('spaces/<str:space_id>/rooms/',                       views.space_live_rooms,             name='space-live-rooms'),
    path('spaces/<str:space_id>/scheduled-rooms/',             views.space_scheduled_rooms,        name='space-scheduled-rooms'),
    path('spaces/<str:space_id>/scheduled-rooms/<str:room_id>/', views.space_scheduled_room_detail, name='space-scheduled-room-detail'),

    # ── Discussions ──────────────────────────────────────────────────────────
    path('spaces/<str:space_id>/discussions/',                 views.space_discussions,            name='space-discussions'),
    path('discussions/<str:discussion_id>/',                   views.discussion_detail,            name='discussion-detail'),
    path('discussions/<str:discussion_id>/react/',             views.discussion_react,             name='discussion-react'),
    path('discussions/<str:discussion_id>/save/',              views.discussion_save,              name='discussion-save'),
    path('discussions/<str:discussion_id>/comments/',          views.discussion_comments,          name='discussion-comments'),

    # ── Comments ─────────────────────────────────────────────────────────────
    path('comments/<str:comment_id>/react/',                   views.comment_react,                name='comment-react'),
]
