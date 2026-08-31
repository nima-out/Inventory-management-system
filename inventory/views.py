from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

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
from .forms import (
    CategoryCatalogForm,
    InventoryMovementForm,
    ItemCatalogForm,
    ItemSearchForm,
    TransactionHistoryFilterForm,
)
from .models import Item
from .selectors import (
    get_inventory_summary,
    list_categories,
    list_low_stock_items,
    list_transaction_history,
    search_items,
)
from .services import (
    archive_item,
    create_category,
    create_item,
    delete_category,
    reactivate_item,
    record_inventory_movement,
    rename_category,
    update_item,
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
@permission_required("inventory.view_category", raise_exception=True)
def category_list(request):
    return render(
        request,
        "inventory/category_list.html",
        {"categories": list_categories()},
    )


@login_required
@permission_required("inventory.add_category", raise_exception=True)
@require_http_methods(["GET", "POST"])
def category_create(request):
    if request.method == "POST":
        form = CategoryCatalogForm(request.POST)
        if form.is_valid():
            try:
                category = create_category(
                    actor=request.user,
                    name=form.cleaned_data["name"],
                )
            except (InvalidCatalogNameError, DuplicateCategoryNameError) as error:
                form.add_error("name", str(error))
            except (
                InvalidInventoryUserError,
                InventoryPermissionDeniedError,
            ) as error:
                raise PermissionDenied(str(error)) from error
            else:
                messages.success(
                    request,
                    f"Category added: {category.name}.",
                )
                return redirect("inventory:category-list")
    else:
        form = CategoryCatalogForm()

    context = {
        "form": form,
        "page_title": "Add category",
        "page_description": "Create a category for grouping inventory items.",
        "sheet_title": "Category details",
        "sheet_note": "New category",
        "guidance": "Category names are unique regardless of capitalization.",
        "submit_label": "Add category",
        "cancel_url": reverse("inventory:category-list"),
    }
    return render(request, "inventory/catalog_form.html", context)


@login_required
@permission_required("inventory.change_category", raise_exception=True)
@require_http_methods(["GET", "POST"])
def category_update(request, category_id):
    category = get_object_or_404(list_categories(), pk=category_id)

    if request.method == "POST":
        form = CategoryCatalogForm(request.POST)
        if form.is_valid():
            try:
                category = rename_category(
                    actor=request.user,
                    category_id=category.pk,
                    name=form.cleaned_data["name"],
                )
            except (InvalidCatalogNameError, DuplicateCategoryNameError) as error:
                form.add_error("name", str(error))
            except CategoryNotFoundError as error:
                raise Http404(str(error)) from error
            except (
                InvalidInventoryUserError,
                InventoryPermissionDeniedError,
            ) as error:
                raise PermissionDenied(str(error)) from error
            else:
                messages.success(
                    request,
                    f"Category updated: {category.name}.",
                )
                return redirect("inventory:category-list")
    else:
        form = CategoryCatalogForm(initial={"name": category.name})

    context = {
        "form": form,
        "page_title": "Edit category",
        "page_description": f"Update the catalog label for {category.name}.",
        "sheet_title": "Category details",
        "sheet_note": "Existing category",
        "guidance": "The new name must remain unique regardless of capitalization.",
        "submit_label": "Save changes",
        "cancel_url": reverse("inventory:category-list"),
    }
    return render(request, "inventory/catalog_form.html", context)


@login_required
@permission_required("inventory.delete_category", raise_exception=True)
@require_http_methods(["GET", "POST"])
def category_delete(request, category_id):
    category = get_object_or_404(list_categories(), pk=category_id)
    context = {
        "page_title": "Delete category",
        "page_description": "Remove an empty category from the catalog.",
        "sheet_title": "Confirm category deletion",
        "sheet_note": "Permanent action",
        "facts": (
            ("Category", category.name),
            ("Assigned items", category.item_count),
        ),
        "warning": (
            "A category can be deleted only when it contains no active or "
            "inactive items. This action cannot be undone."
        ),
        "submit_label": "Delete category",
        "cancel_url": reverse("inventory:category-list"),
        "destructive": True,
    }

    if request.method == "POST":
        try:
            delete_category(actor=request.user, category_id=category.pk)
        except CategoryInUseError as error:
            context["action_error"] = str(error)
        except CategoryNotFoundError as error:
            raise Http404(str(error)) from error
        except (
            InvalidInventoryUserError,
            InventoryPermissionDeniedError,
        ) as error:
            raise PermissionDenied(str(error)) from error
        else:
            messages.success(
                request,
                f"Category deleted: {category.name}.",
            )
            return redirect("inventory:category-list")

    return render(request, "inventory/catalog_confirm.html", context)


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
@permission_required("inventory.add_item", raise_exception=True)
@require_http_methods(["GET", "POST"])
def item_create(request):
    if request.method == "POST":
        form = ItemCatalogForm(request.POST)
        if form.is_valid():
            category = form.cleaned_data["category"]
            try:
                item = create_item(
                    actor=request.user,
                    category_id=category.pk,
                    name=form.cleaned_data["name"],
                    reorder_level=form.cleaned_data["reorder_level"],
                )
            except (InvalidCatalogNameError, DuplicateItemNameError) as error:
                form.add_error("name", str(error))
            except InvalidReorderLevelError as error:
                form.add_error("reorder_level", str(error))
            except CategoryNotFoundError as error:
                form.add_error("category", str(error))
            except (
                InvalidInventoryUserError,
                InventoryPermissionDeniedError,
            ) as error:
                raise PermissionDenied(str(error)) from error
            else:
                messages.success(
                    request,
                    f"Item added: {item.name}. Initial stock is 0 units.",
                )
                return redirect("inventory:item-list")
    else:
        form = ItemCatalogForm()

    context = {
        "form": form,
        "page_title": "Add item",
        "page_description": "Create an inventory record before receiving stock.",
        "sheet_title": "Item details",
        "sheet_note": "New item",
        "guidance": (
            "New items start at 0 units. Use Move stock to record the "
            "initial quantity."
        ),
        "submit_label": "Add item",
        "cancel_url": reverse("inventory:item-list"),
    }
    return render(request, "inventory/catalog_form.html", context)


@login_required
@permission_required("inventory.change_item", raise_exception=True)
@require_http_methods(["GET", "POST"])
def item_update(request, item_id):
    item = get_object_or_404(
        Item.objects.select_related("category"),
        pk=item_id,
    )

    if request.method == "POST":
        form = ItemCatalogForm(request.POST)
        if form.is_valid():
            category = form.cleaned_data["category"]
            try:
                item = update_item(
                    actor=request.user,
                    item_id=item.pk,
                    category_id=category.pk,
                    name=form.cleaned_data["name"],
                    reorder_level=form.cleaned_data["reorder_level"],
                )
            except (InvalidCatalogNameError, DuplicateItemNameError) as error:
                form.add_error("name", str(error))
            except InvalidReorderLevelError as error:
                form.add_error("reorder_level", str(error))
            except CategoryNotFoundError as error:
                form.add_error("category", str(error))
            except InventoryItemNotFoundError as error:
                raise Http404(str(error)) from error
            except (
                InvalidInventoryUserError,
                InventoryPermissionDeniedError,
            ) as error:
                raise PermissionDenied(str(error)) from error
            else:
                messages.success(request, f"Item updated: {item.name}.")
                return redirect("inventory:item-list")
    else:
        form = ItemCatalogForm(
            initial={
                "name": item.name,
                "category": item.category_id,
                "reorder_level": item.reorder_level,
            }
        )

    context = {
        "form": form,
        "page_title": "Edit item",
        "page_description": f"Update the catalog details for {item.name}.",
        "sheet_title": "Item details",
        "sheet_note": "Existing item",
        "guidance": (
            "Quantity is controlled by recorded stock movements and cannot "
            "be edited here."
        ),
        "submit_label": "Save changes",
        "cancel_url": reverse("inventory:item-list"),
    }
    return render(request, "inventory/catalog_form.html", context)


@login_required
@permission_required("inventory.archive_item", raise_exception=True)
@require_http_methods(["GET", "POST"])
def item_archive(request, item_id):
    item = get_object_or_404(
        Item.objects.select_related("category"),
        pk=item_id,
    )
    context = {
        "page_title": "Archive item",
        "page_description": "Remove an item from active inventory operations.",
        "sheet_title": "Confirm item archival",
        "sheet_note": "Reversible action",
        "facts": (
            ("Item", item.name),
            ("Category", item.category.name),
            ("On hand", item.quantity),
        ),
        "warning": (
            "Archiving preserves the current quantity and complete movement "
            "history, but prevents further stock movements until reactivation."
        ),
        "submit_label": "Archive item",
        "cancel_url": reverse("inventory:item-list"),
        "destructive": True,
    }

    if request.method == "POST":
        try:
            item = archive_item(actor=request.user, item_id=item.pk)
        except InventoryItemNotFoundError as error:
            raise Http404(str(error)) from error
        except (
            InvalidInventoryUserError,
            InventoryPermissionDeniedError,
        ) as error:
            raise PermissionDenied(str(error)) from error
        else:
            messages.success(request, f"Item archived: {item.name}.")
            item_list_url = reverse("inventory:item-list")
            return redirect(f"{item_list_url}?include_inactive=on")

    return render(request, "inventory/catalog_confirm.html", context)


@login_required
@permission_required("inventory.reactivate_item", raise_exception=True)
@require_http_methods(["GET", "POST"])
def item_reactivate(request, item_id):
    item = get_object_or_404(
        Item.objects.select_related("category"),
        pk=item_id,
    )
    context = {
        "page_title": "Reactivate item",
        "page_description": "Return an archived item to active inventory.",
        "sheet_title": "Confirm item reactivation",
        "sheet_note": "Catalog action",
        "facts": (
            ("Item", item.name),
            ("Category", item.category.name),
            ("On hand", item.quantity),
        ),
        "warning": (
            "Reactivation makes the item available for stock movements and "
            "includes it in active inventory totals."
        ),
        "submit_label": "Reactivate item",
        "cancel_url": f"{reverse('inventory:item-list')}?include_inactive=on",
        "destructive": False,
    }

    if request.method == "POST":
        try:
            item = reactivate_item(actor=request.user, item_id=item.pk)
        except InventoryItemNotFoundError as error:
            raise Http404(str(error)) from error
        except (
            InvalidInventoryUserError,
            InventoryPermissionDeniedError,
        ) as error:
            raise PermissionDenied(str(error)) from error
        else:
            messages.success(request, f"Item reactivated: {item.name}.")
            item_list_url = reverse("inventory:item-list")
            return redirect(f"{item_list_url}?include_inactive=on")

    return render(request, "inventory/catalog_confirm.html", context)


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
