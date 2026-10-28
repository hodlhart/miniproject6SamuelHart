# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.index, name="index"),
    path("accounts/register/", views.register, name="register"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("readers/<int:reader_id>/", views.wallet, name="wallet"),
    path("readers/<int:reader_id>/log/", views.log_reading, name="log_reading"),
    path("readers/<int:reader_id>/shop/", views.reader_shop, name="reader_shop"),
    path("readers/<int:reader_id>/books/", views.books, name="books"),
    path("cards/", views.shop, name="shop"),
    path("art/<str:name>", views.serve_art, name="art"),
    path("readers/<int:reader_id>/cards/", views.my_cards, name="my_cards"),
    path(
        "readers/<int:reader_id>/cards/buy/<int:card_id>/",
        views.buy_card,
        name="buy_card",
    ),
    path("manage/cards/new/", views.manage_card_new, name="manage_card_new"),
    path("manage/cards/", views.manage_cards, name="manage_cards"),
    path("manage/readers/", views.manage_readers, name="manage_readers"),
    path(
        "manage/readers/<int:reader_id>/reset/",
        views.reset_energy,
        name="reset_energy",
    ),
]
