from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .exceptions import (
    InactiveItemError,
    InsufficientStockError,
    InvalidInventoryUserError,
    InvalidQuantityError,
    InvalidTransactionTypeError,
    InventoryItemNotFoundError,
    InventoryPermissionDeniedError,
)
from .forms import (
    InventoryMovementForm,
    ItemSearchForm,
    TransactionHistoryFilterForm,
)
from .selectors import (
    get_inventory_summary,
    list_low_stock_items,
    list_transaction_history,
    search_items,
)
from .services import record_inventory_movement


def _query_without_page(request):
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return query_params.urlencode()


@login_required
@permission_required("inventory.view_item", raise_exception=True)
def dashboard(request):
    context = {
        "summary": get_inventory_summary(),
        "low_stock_items": list_low_stock_items()[:10],
    }
    return render(request, "inventory/dashboard.html", context)


@login_required
@permission_required("inventory.view_item", raise_exception=True)
def item_list(request):
    form = ItemSearchForm(request.GET)
    items = search_items().none()

    if form.is_valid():
        category = form.cleaned_data["category"]
        items = search_items(
            query=form.cleaned_data["query"],
            category_id=category.pk if category else None,
            stock_status=form.cleaned_data["stock_status"] or None,
            include_inactive=form.cleaned_data["include_inactive"],
        )

    page_obj = Paginator(items, 25).get_page(request.GET.get("page"))
    context = {
        "form": form,
        "page_obj": page_obj,
        "filter_query": _query_without_page(request),
    }
    return render(request, "inventory/item_list.html", context)


@login_required
@permission_required(
    "inventory.record_inventory_movement",
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def record_movement(request):
    if request.method == "POST":
        form = InventoryMovementForm(request.POST)
        if form.is_valid():
            item = form.cleaned_data["item"]

            try:
                movement = record_inventory_movement(
                    item_id=item.pk,
                    user=request.user,
                    transaction_type=form.cleaned_data[
                        "transaction_type"
                    ],
                    quantity=form.cleaned_data["quantity"],
                )
            except InsufficientStockError as error:
                form.add_error("quantity", str(error))
            except (InactiveItemError, InventoryItemNotFoundError) as error:
                form.add_error("item", str(error))
            except InvalidQuantityError as error:
                form.add_error("quantity", str(error))
            except InvalidTransactionTypeError as error:
                form.add_error("transaction_type", str(error))
            except (
                InvalidInventoryUserError,
                InventoryPermissionDeniedError,
            ) as error:
                raise PermissionDenied(str(error)) from error
            else:
                unit_label = (
                    "unit" if movement.quantity_moved == 1 else "units"
                )
                messages.success(
                    request,
                    f"{movement.get_transaction_type_display()} recorded "
                    f"for {movement.item.name}: "
                    f"{movement.quantity_moved} {unit_label}.",
                )
                history_url = reverse(
                    "inventory:transaction-history"
                )
                history_query = urlencode({"item": movement.item_id})
                return redirect(f"{history_url}?{history_query}")
    else:
        form = InventoryMovementForm(
            initial={"item": request.GET.get("item")}
        )

    return render(
        request,
        "inventory/movement_form.html",
        {"form": form},
    )


@login_required
@permission_required("inventory.view_transactionhistory", raise_exception=True)
def transaction_history(request):
    form = TransactionHistoryFilterForm(request.GET)
    history = list_transaction_history().none()

    if form.is_valid():
        item = form.cleaned_data["item"]
        user = form.cleaned_data["user"]
        history = list_transaction_history(
            item_id=item.pk if item else None,
            user_id=user.pk if user else None,
            transaction_type=form.cleaned_data["transaction_type"] or None,
            start=form.cleaned_data["start"],
            end=form.cleaned_data["end"],
        )

    page_obj = Paginator(history, 50).get_page(request.GET.get("page"))
    context = {
        "form": form,
        "page_obj": page_obj,
        "filter_query": _query_without_page(request),
    }
    return render(request, "inventory/transaction_history.html", context)
