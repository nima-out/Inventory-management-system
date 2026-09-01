from django.test import TestCase

from ..forms import (
    InventoryMovementForm,
    ItemCatalogForm,
    ItemSearchForm,
    StockroomAuthenticationForm,
    TransactionHistoryFilterForm,
)
from ..models import Category, Item, TransactionHistory


class InventoryFormTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Guitars")
        self.active_item = Item.objects.create(
            category=self.category,
            name="Active Guitar",
        )
        self.inactive_item = Item.objects.create(
            category=self.category,
            name="Archived Guitar",
            is_active=False,
        )

    def test_movement_form_lists_only_active_items(self):
        form = InventoryMovementForm()

        self.assertEqual(list(form.fields["item"].queryset), [self.active_item])
        self.assertIn(
            "Active Guitar — Guitars (0 on hand)",
            form.fields["item"].label_from_instance(self.active_item),
        )

    def test_movement_form_requires_positive_quantity(self):
        form = InventoryMovementForm(
            data={
                "item": self.active_item.pk,
                "transaction_type": (
                    TransactionHistory.TransactionType.STOCK_IN
                ),
                "quantity": 0,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_item_form_rejects_negative_reorder_level(self):
        form = ItemCatalogForm(
            data={
                "name": "Telecaster",
                "category": self.category.pk,
                "reorder_level": -1,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("reorder_level", form.errors)

    def test_history_form_rejects_reversed_date_range(self):
        form = TransactionHistoryFilterForm(
            data={"start": "2026-09-02", "end": "2026-09-01"}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("start date", form.non_field_errors()[0])

    def test_shared_widget_classes_and_input_attributes_are_applied(self):
        form = ItemSearchForm()

        self.assertIn(
            "form-control",
            form.fields["query"].widget.attrs["class"],
        )
        self.assertIn(
            "form-select",
            form.fields["category"].widget.attrs["class"],
        )
        self.assertIn(
            "form-check-input",
            form.fields["include_inactive"].widget.attrs["class"],
        )
        self.assertEqual(
            form.fields["query"].widget.attrs["placeholder"],
            "Search by item name…",
        )
        self.assertEqual(
            form.fields["query"].widget.attrs["aria-describedby"],
            "id_query-feedback",
        )

    def test_invalid_fields_receive_aria_invalid(self):
        form = ItemCatalogForm(
            data={
                "name": "Telecaster",
                "category": self.category.pk,
                "reorder_level": -1,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.fields["reorder_level"].widget.attrs["aria-invalid"],
            "true",
        )

    def test_authentication_form_uses_expected_autocomplete_values(self):
        form = StockroomAuthenticationForm()

        self.assertEqual(
            form.fields["username"].widget.attrs["autocomplete"],
            "username",
        )
        self.assertEqual(
            form.fields["password"].widget.attrs["autocomplete"],
            "current-password",
        )
        self.assertNotIn("autofocus", form.fields["username"].widget.attrs)
