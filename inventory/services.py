from django.db import transaction
from django.db.models import F

from .exceptions import (
    InactiveItemError,
    InsufficientStockError,
    InvalidInventoryUserError,
    InvalidQuantityError,
    InvalidTransactionTypeError,
    InventoryItemNotFoundError,
)
from .models import Item, TransactionHistory


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

    if (
        user is None
        or getattr(user, "pk", None) is None
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "is_active", False)
    ):
        raise InvalidInventoryUserError(
            "An active authenticated user is required."
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
        ).update(quantity=F("quantity") + quantity)
    else:
        updated_rows = Item.objects.filter(
            pk=item.pk,
            is_active=True,
            quantity__gte=quantity,
        ).update(quantity=F("quantity") - quantity)

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
