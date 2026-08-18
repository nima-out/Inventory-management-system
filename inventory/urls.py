from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("items/", views.item_list, name="item-list"),
    path("movements/new/", views.record_movement, name="record-movement"),
    path("history/", views.transaction_history, name="transaction-history"),
]
