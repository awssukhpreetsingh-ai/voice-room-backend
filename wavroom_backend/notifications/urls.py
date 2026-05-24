from django.urls import path
from notifications import views

urlpatterns = [
    path('notifications/',                        views.notification_list,   name='notifications-list'),
    path('notifications/count/',                  views.notification_count,  name='notifications-count'),
    path('notifications/read_all/',               views.mark_all_read,       name='notifications-read-all'),
    path('notifications/<str:notification_id>/',  views.notification_detail, name='notification-detail'),
]
