# users/urls.py


from django.urls import path
from users import views

urlpatterns = [
    # Auth
    path('auth/firebase/', views.firebase_auth_view, name='firebase-auth'),
    path('auth/me/',       views.me_view,            name='auth-me'),
    path('auth/profile/',  views.profile_view,       name='auth-profile'),

    path('auth/fcm-token/',     views.update_fcm_token, name='fcm-token'),
    path('auth/upload/avatar/', views.upload_avatar,    name='upload-avatar'),
    path('auth/upload/cover/',  views.upload_cover,     name='upload-cover'),

    # User profiles + follow/unfollow
    path('users/<str:user_id>/',            views.user_profile_view,   name='user-profile'),
    path('users/<str:user_id>/follow/',     views.follow_view,         name='follow'),
    path('users/<str:user_id>/followers/',  views.followers_list_view, name='followers'),
    path('users/<str:user_id>/following/',  views.following_list_view, name='following'),
]