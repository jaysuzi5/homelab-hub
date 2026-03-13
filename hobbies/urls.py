from django.urls import path
from . import views

urlpatterns = [
    path('reading/', views.reading_list, name='reading_list'),
    path('reading/add/', views.book_add, name='book_add'),
    path('reading/search/', views.book_search, name='book_search'),
    path('reading/<int:pk>/delete/', views.book_delete, name='book_delete'),
]
