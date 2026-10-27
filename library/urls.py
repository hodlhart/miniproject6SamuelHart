# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.index, name="index"),
    path("readers/<int:reader_id>/", views.wallet, name="wallet"),
    path("readers/<int:reader_id>/books/", views.books, name="books"),
    path("cards/", views.shop, name="shop"),
    path("readers/<int:reader_id>/cards/", views.my_cards, name="my_cards"),
]
