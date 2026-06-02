from django.urls import path
from . import views

urlpatterns = [
    path('weight/', views.weight_list, name='weight_list'),
    path('weight/<int:pk>/delete/', views.weight_delete, name='weight_delete'),
    path('weight/goal/add/', views.weight_goal_add, name='weight_goal_add'),
    path('weight/goal/<int:pk>/delete/', views.weight_goal_delete, name='weight_goal_delete'),
    path('weight/prefs/', views.weight_chart_prefs_save, name='weight_chart_prefs_save'),
    path('exercise/', views.exercise, name='exercise'),
    path('exercise/<int:pk>/edit/', views.exercise_edit, name='exercise_edit'),
    path('exercise/<int:pk>/delete/', views.exercise_delete, name='exercise_delete'),
]
