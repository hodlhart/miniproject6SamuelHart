# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.index, name="index"),
]
