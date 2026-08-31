from django.test import TestCase

from .forms import (
    InventoryMovementForm,
    ItemCatalogForm,
    TransactionHistoryFilterForm,
)
from .models import Category, Item, TransactionHistory


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
