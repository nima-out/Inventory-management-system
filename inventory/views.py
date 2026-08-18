from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import render

from .forms import ItemSearchForm, TransactionHistoryFilterForm
from .selectors import (
    get_inventory_summary,
    list_low_stock_items,
    list_transaction_history,
    search_items,
)


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
