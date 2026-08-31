from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("categories/", views.category_list, name="category-list"),
    path("categories/new/", views.category_create, name="category-create"),
    path(
        "categories/<int:category_id>/edit/",
        views.category_update,
        name="category-update",
    ),
    path(
        "categories/<int:category_id>/delete/",
        views.category_delete,
        name="category-delete",
    ),
    path("items/", views.item_list, name="item-list"),
    path("items/new/", views.item_create, name="item-create"),
    path(
        "items/<int:item_id>/edit/",
        views.item_update,
        name="item-update",
    ),
    path(
        "items/<int:item_id>/archive/",
        views.item_archive,
        name="item-archive",
    ),
    path(
        "items/<int:item_id>/reactivate/",
        views.item_reactivate,
        name="item-reactivate",
    ),
    path("movements/new/", views.record_movement, name="record-movement"),
    path("history/", views.transaction_history, name="transaction-history"),
]
