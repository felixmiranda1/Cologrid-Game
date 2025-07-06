from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('new/', views.new_game, name='new_game'),
    path('board/<str:code>/', views.board, name='board'),
    path('game/', views.remote_game, name='remote_game'),
    # Multiplayer session URLs
    path('session/create/', views.create_session_view, name='create_session'),
    path('session/join/<str:code>/', views.join_session_view, name='join_session'),
    path("session/<str:code>/redirect_check/", views.player_redirect_status_view, name="player_redirect_status"),
    path("session/submit_move/", views.submit_move_view, name="submit_move"),
    path('session/<str:session_code>/submit_hint/', views.submit_hint_view, name='submit_hint'),
    path('session/lobby/', views.lobby_view, name='lobby'),
    path('session/lobby/players/', views.players_list_partial, name='players_list_partial'),
    path('session/start/', views.start_game_view, name='start_game'),
    path('session/waiting_hint/', views.waiting_hint_view, name='waiting_hint'),
    path("session/results/", views.round_results_view, name="round_results"),
    path("session/next/", views.next_round_view, name="next_round"),
]