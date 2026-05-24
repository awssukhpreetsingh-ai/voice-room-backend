from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('admin/auth/login/',  views.admin_login,  name='admin-login'),
    path('admin/auth/logout/', views.admin_logout, name='admin-logout'),
    path('admin/auth/me/',     views.admin_me,     name='admin-me'),

    # Dashboard
    path('admin/dashboard/',   views.dashboard_stats, name='admin-dashboard'),

    # Users
    path('admin/users/',          views.list_users,   name='admin-users-list'),
    path('admin/users/<uuid:user_id>/', views.user_detail, name='admin-user-detail'),

    # Rooms
    path('admin/rooms/',              views.list_rooms,  name='admin-rooms-list'),
    path('admin/rooms/<str:room_id>/', views.close_room,  name='admin-room-close'),

    # Spaces
    path('admin/spaces/',                              views.list_spaces,        name='admin-spaces-list'),
    path('admin/spaces/<str:space_id>/',               views.space_detail,       name='admin-space-detail'),
    path('admin/spaces/<str:space_id>/upload_cover/',  views.upload_space_cover, name='admin-space-cover'),

    # Reports / Moderation
    path('admin/reports/',               views.list_reports,   name='admin-reports-list'),
    path('admin/reports/<int:report_id>/', views.resolve_report, name='admin-report-resolve'),

    # Analytics
    path('admin/analytics/users/',       views.analytics_user_growth,  name='admin-analytics-users'),
    path('admin/analytics/spaces/',      views.analytics_top_spaces,   name='admin-analytics-spaces'),
    path('admin/analytics/discussions/', views.analytics_discussions,  name='admin-analytics-discussions'),

    # Audit Logs
    path('admin/audit-logs/', views.audit_logs, name='admin-audit-logs'),
]
