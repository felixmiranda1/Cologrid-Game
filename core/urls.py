from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('new/', views.new_game, name='new_game'),
    path('board/', views.board, name='board'),
    path('game/', views.remote_game, name='remote_game'),
]
