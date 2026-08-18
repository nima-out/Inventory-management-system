from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from .exceptions import (
    CategoryInUseError,
    CategoryNotFoundError,
    DuplicateCategoryNameError,
    DuplicateItemNameError,
    InactiveItemError,
    InsufficientStockError,
    InvalidCatalogNameError,
    InvalidInventoryUserError,
    InvalidQuantityError,
    InvalidReorderLevelError,
    InvalidTransactionTypeError,
    InventoryItemNotFoundError,
    InventoryPermissionDeniedError,
)
from .models import Category, Item, TransactionHistory


def _require_active_actor(actor):
    if (
        actor is None
        or getattr(actor, "pk", None) is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
    ):
        raise InvalidInventoryUserError(
            "An active authenticated user is required."
        )

    return actor


def _require_permission(actor, permission):
    actor = _require_active_actor(actor)
    if not actor.has_perm(permission):
        raise InventoryPermissionDeniedError(
            f"Permission required: {permission}."
        )

    return actor


def _normalize_name(name):
    if not isinstance(name, str):
        raise InvalidCatalogNameError("Name must be text.")

    normalized_name = " ".join(name.split())
    if not normalized_name:
        raise InvalidCatalogNameError("Name cannot be blank.")

    return normalized_name


def _validate_reorder_level(reorder_level):
    if type(reorder_level) is not int or reorder_level < 0:
        raise InvalidReorderLevelError(
            "Reorder level must be a non-negative integer."
        )

    return reorder_level


def _get_category(category_id):
    try:
        return Category.objects.get(pk=category_id)
    except (Category.DoesNotExist, TypeError, ValueError):
        raise CategoryNotFoundError(
            "The requested category does not exist."
        ) from None


def _get_item(item_id):
    try:
        return Item.objects.select_related("category").get(pk=item_id)
    except (Item.DoesNotExist, TypeError, ValueError):
        raise InventoryItemNotFoundError(
            "The requested inventory item does not exist."
        ) from None


@transaction.atomic
def record_inventory_movement(
    *,
    item_id,
    user,
    transaction_type,
    quantity,
):
    if type(quantity) is not int or quantity <= 0:
        raise InvalidQuantityError(
            "Movement quantity must be a positive integer."
        )

    if transaction_type not in TransactionHistory.TransactionType.values:
        raise InvalidTransactionTypeError(
            "Transaction type must be IN or OUT."
        )

    user = _require_permission(
        user,
        "inventory.record_inventory_movement",
    )

    try:
        item = Item.objects.get(pk=item_id)
    except (Item.DoesNotExist, TypeError, ValueError):
        raise InventoryItemNotFoundError(
            "The requested inventory item does not exist."
        ) from None

    if not item.is_active:
        raise InactiveItemError(
            "Stock cannot be moved for an inactive item."
        )

    if transaction_type == TransactionHistory.TransactionType.STOCK_IN:
        updated_rows = Item.objects.filter(
            pk=item.pk,
            is_active=True,
        )._increase_quantity(quantity)
    else:
        updated_rows = Item.objects.filter(
            pk=item.pk,
            is_active=True,
        )._decrease_quantity_if_available(quantity)

        if updated_rows == 0:
            raise InsufficientStockError(
                "There is not enough stock for this movement."
            )

    if updated_rows == 0:
        raise InactiveItemError(
            "The item became unavailable during the movement."
        )

    item.refresh_from_db(fields=["quantity"])

    return TransactionHistory.objects.create(
        item=item,
        user=user,
        transaction_type=transaction_type,
        quantity_moved=quantity,
    )


def create_category(*, actor, name):
    _require_permission(actor, "inventory.add_category")
    normalized_name = _normalize_name(name)

    if Category.objects.filter(name__iexact=normalized_name).exists():
        raise DuplicateCategoryNameError(
            "A category with this name already exists."
        )

    try:
        with transaction.atomic():
            return Category.objects.create(name=normalized_name)
    except IntegrityError as error:
        raise DuplicateCategoryNameError(
            "A category with this name already exists."
        ) from error


def rename_category(*, actor, category_id, name):
    _require_permission(actor, "inventory.change_category")
    category = _get_category(category_id)
    normalized_name = _normalize_name(name)

    duplicate_exists = Category.objects.filter(
        name__iexact=normalized_name
    ).exclude(pk=category.pk).exists()
    if duplicate_exists:
        raise DuplicateCategoryNameError(
            "A category with this name already exists."
        )

    category.name = normalized_name
    try:
        with transaction.atomic():
            category.save(update_fields=["name"])
    except IntegrityError as error:
        raise DuplicateCategoryNameError(
            "A category with this name already exists."
        ) from error

    return category


def delete_category(*, actor, category_id):
    _require_permission(actor, "inventory.delete_category")
    category = _get_category(category_id)

    if category.items.exists():
        raise CategoryInUseError(
            "A category containing items cannot be deleted."
        )

    try:
        with transaction.atomic():
            category.delete()
    except ProtectedError as error:
        raise CategoryInUseError(
            "A category containing items cannot be deleted."
        ) from error


def create_item(
    *,
    actor,
    category_id,
    name,
    reorder_level=0,
):
    _require_permission(actor, "inventory.add_item")
    category = _get_category(category_id)
    normalized_name = _normalize_name(name)
    reorder_level = _validate_reorder_level(reorder_level)

    duplicate_exists = Item.objects.filter(
        category=category,
        name__iexact=normalized_name,
    ).exists()
    if duplicate_exists:
        raise DuplicateItemNameError(
            "An item with this name already exists in the category."
        )

    try:
        with transaction.atomic():
            return Item.objects.create(
                category=category,
                name=normalized_name,
                reorder_level=reorder_level,
            )
    except IntegrityError as error:
        raise DuplicateItemNameError(
            "An item with this name already exists in the category."
        ) from error


def update_item(
    *,
    actor,
    item_id,
    category_id,
    name,
    reorder_level,
):
    _require_permission(actor, "inventory.change_item")
    item = _get_item(item_id)
    category = _get_category(category_id)
    normalized_name = _normalize_name(name)
    reorder_level = _validate_reorder_level(reorder_level)

    duplicate_exists = Item.objects.filter(
        category=category,
        name__iexact=normalized_name,
    ).exclude(pk=item.pk).exists()
    if duplicate_exists:
        raise DuplicateItemNameError(
            "An item with this name already exists in the category."
        )

    item.category = category
    item.name = normalized_name
    item.reorder_level = reorder_level
    try:
        with transaction.atomic():
            item.save(
                update_fields=["category", "name", "reorder_level"]
            )
    except IntegrityError as error:
        raise DuplicateItemNameError(
            "An item with this name already exists in the category."
        ) from error

    return item


def archive_item(*, actor, item_id):
    _require_permission(actor, "inventory.archive_item")
    item = _get_item(item_id)
    item.is_active = False
    item.save(update_fields=["is_active"])
    return item


def reactivate_item(*, actor, item_id):
    _require_permission(actor, "inventory.reactivate_item")
    item = _get_item(item_id)
    item.is_active = True
    item.save(update_fields=["is_active"])
    return item
