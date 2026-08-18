from django.contrib import admin

from .models import Category, Item, TransactionHistory


class ReadOnlyAdminMixin:
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(Category)
class CategoryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Item)
class ItemAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "quantity",
        "reorder_level",
        "low_stock",
        "is_active",
    )
    list_filter = ("is_active", "category")
    search_fields = ("name", "category__name")
    list_select_related = ("category",)
    ordering = ("name",)

    @admin.display(boolean=True, description="Low stock")
    def low_stock(self, obj):
        return obj.is_low_stock


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "timestamp",
        "item",
        "item_category",
        "user",
        "transaction_type",
        "quantity_moved",
    )
    list_filter = (
        "transaction_type",
        "timestamp",
        "item__category",
    )
    search_fields = (
        "item__name",
        "item__category__name",
        "user__username",
        "user__email",
    )
    list_select_related = ("item", "item__category", "user")
    ordering = ("-timestamp", "-id")
    date_hierarchy = "timestamp"

    @admin.display(ordering="item__category__name", description="Category")
    def item_category(self, obj):
        return obj.item.category
