from datetime import date, datetime, time

from django.conf import settings
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from .exceptions import (
    InvalidDateRangeError,
    InvalidStockStatusError,
    InvalidTransactionTypeError,
)
from .models import Category, Item, TransactionHistory


STOCK_STATUS_LOW = "low"
STOCK_STATUS_OUT = "out"
STOCK_STATUS_HEALTHY = "healthy"

_STOCK_STATUS_FILTERS = {
    STOCK_STATUS_LOW: Q(quantity__lte=F("reorder_level")),
    STOCK_STATUS_OUT: Q(quantity=0),
    STOCK_STATUS_HEALTHY: Q(quantity__gt=F("reorder_level")),
}


def _normalize_history_bound(value, *, is_end):
    if isinstance(value, datetime):
        normalized_value = value
    elif isinstance(value, date):
        boundary_time = time.max if is_end else time.min
        normalized_value = datetime.combine(value, boundary_time)
    else:
        raise InvalidDateRangeError(
            "History bounds must be date or datetime values."
        )

    if settings.USE_TZ and timezone.is_naive(normalized_value):
        normalized_value = timezone.make_aware(
            normalized_value,
            timezone.get_current_timezone(),
        )

    return normalized_value


def get_inventory_summary():
    """Return dashboard totals for active inventory items."""
    return Item.objects.filter(is_active=True).aggregate(
        active_sku_count=Count("id"),
        total_units=Sum("quantity", default=0),
        low_stock_count=Count(
            "id",
            filter=Q(quantity__lte=F("reorder_level")),
        ),
        out_of_stock_count=Count(
            "id",
            filter=Q(quantity=0),
        ),
    )


def list_categories():
    """Return categories with the number of items assigned to each."""
    return Category.objects.annotate(
        item_count=Count("items"),
    ).order_by("name")


def list_low_stock_items():
    """Return active items at or below their reorder level."""
    return Item.objects.select_related("category").filter(
        is_active=True,
        quantity__lte=F("reorder_level"),
    )


def search_items(
    *,
    query=None,
    category_id=None,
    stock_status=None,
    include_inactive=False,
):
    """Return inventory items matching the supplied catalog filters."""
    if stock_status is not None and stock_status not in _STOCK_STATUS_FILTERS:
        supported_statuses = ", ".join(sorted(_STOCK_STATUS_FILTERS))
        raise InvalidStockStatusError(
            f"Stock status must be one of: {supported_statuses}."
        )

    items = Item.objects.select_related("category")

    if not include_inactive:
        items = items.filter(is_active=True)

    if query is not None:
        normalized_query = " ".join(str(query).split())
        if normalized_query:
            items = items.filter(name__icontains=normalized_query)

    if category_id is not None:
        items = items.filter(category_id=category_id)

    if stock_status is not None:
        items = items.filter(_STOCK_STATUS_FILTERS[stock_status])

    return items


def list_transaction_history(
    *,
    item_id=None,
    user_id=None,
    transaction_type=None,
    start=None,
    end=None,
):
    """Return newest-first transaction history matching the filters."""
    if (
        transaction_type is not None
        and transaction_type not in TransactionHistory.TransactionType.values
    ):
        raise InvalidTransactionTypeError(
            "Transaction type must be IN or OUT."
        )

    if start is not None:
        start = _normalize_history_bound(start, is_end=False)

    if end is not None:
        end = _normalize_history_bound(end, is_end=True)

    if start is not None and end is not None and start > end:
        raise InvalidDateRangeError(
            "Start must be earlier than or equal to end."
        )

    history = TransactionHistory.objects.select_related(
        "item",
        "item__category",
        "user",
    ).order_by("-timestamp", "-id")

    if item_id is not None:
        history = history.filter(item_id=item_id)

    if user_id is not None:
        history = history.filter(user_id=user_id)

    if transaction_type is not None:
        history = history.filter(transaction_type=transaction_type)

    if start is not None:
        history = history.filter(timestamp__gte=start)

    if end is not None:
        history = history.filter(timestamp__lte=end)

    return history
