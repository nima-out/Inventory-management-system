from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .exceptions import (
    InvalidDateRangeError,
    InvalidStockStatusError,
    InvalidTransactionTypeError,
)
from .models import Category, Item, TransactionHistory
from .selectors import (
    STOCK_STATUS_HEALTHY,
    STOCK_STATUS_LOW,
    STOCK_STATUS_OUT,
    get_inventory_summary,
    list_categories,
    list_low_stock_items,
    list_transaction_history,
    search_items,
)
from .services import archive_item, record_inventory_movement


class InventorySelectorTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username="selector-manager",
            password="test-password",
        )
        self.guitars = Category.objects.create(name="Guitars")
        self.accessories = Category.objects.create(name="Accessories")

    def create_item(
        self,
        *,
        name,
        quantity,
        reorder_level,
        category=None,
        active=True,
    ):
        item = Item.objects.create(
            category=category or self.guitars,
            name=name,
            reorder_level=reorder_level,
        )
        if quantity:
            record_inventory_movement(
                item_id=item.pk,
                user=self.actor,
                transaction_type=(
                    TransactionHistory.TransactionType.STOCK_IN
                ),
                quantity=quantity,
            )
        if not active:
            archive_item(actor=self.actor, item_id=item.pk)
        item.refresh_from_db()
        return item

    def test_inventory_summary_counts_active_stock(self):
        self.create_item(name="Low", quantity=2, reorder_level=3)
        self.create_item(name="Healthy", quantity=5, reorder_level=2)
        self.create_item(name="Out", quantity=0, reorder_level=1)
        self.create_item(
            name="Archived",
            quantity=10,
            reorder_level=1,
            active=False,
        )

        self.assertEqual(
            get_inventory_summary(),
            {
                "active_sku_count": 3,
                "total_units": 7,
                "low_stock_count": 2,
                "out_of_stock_count": 1,
            },
        )

    def test_category_and_low_stock_lists_include_expected_records(self):
        low = self.create_item(name="Low", quantity=1, reorder_level=2)
        self.create_item(
            name="Cable",
            quantity=5,
            reorder_level=1,
            category=self.accessories,
        )
        self.create_item(
            name="Archived low",
            quantity=0,
            reorder_level=2,
            active=False,
        )

        category_counts = {
            category.name: category.item_count
            for category in list_categories()
        }
        self.assertEqual(category_counts, {"Accessories": 1, "Guitars": 2})
        self.assertEqual(list(list_low_stock_items()), [low])

    def test_search_combines_name_category_and_active_filters(self):
        match = self.create_item(
            name="Player Telecaster",
            quantity=3,
            reorder_level=1,
        )
        archived = self.create_item(
            name="Archived Telecaster",
            quantity=2,
            reorder_level=1,
            active=False,
        )
        self.create_item(
            name="Telecaster Cable",
            quantity=4,
            reorder_level=1,
            category=self.accessories,
        )

        active_results = list(
            search_items(query="  Telecaster ", category_id=self.guitars.pk)
        )
        all_results = list(
            search_items(
                query="Telecaster",
                category_id=self.guitars.pk,
                include_inactive=True,
            )
        )

        self.assertEqual(active_results, [match])
        self.assertCountEqual(all_results, [match, archived])

    def test_search_stock_statuses(self):
        low = self.create_item(name="Low", quantity=1, reorder_level=2)
        out = self.create_item(name="Out", quantity=0, reorder_level=2)
        healthy = self.create_item(name="Healthy", quantity=3, reorder_level=2)

        self.assertCountEqual(
            search_items(stock_status=STOCK_STATUS_LOW),
            [low, out],
        )
        self.assertEqual(
            list(search_items(stock_status=STOCK_STATUS_OUT)),
            [out],
        )
        self.assertEqual(
            list(search_items(stock_status=STOCK_STATUS_HEALTHY)),
            [healthy],
        )

    def test_invalid_stock_status_is_rejected(self):
        with self.assertRaises(InvalidStockStatusError):
            search_items(stock_status="unknown")

    def test_history_filters_and_validates_bounds(self):
        item = self.create_item(name="Guitar", quantity=5, reorder_level=1)
        stock_out = record_inventory_movement(
            item_id=item.pk,
            user=self.actor,
            transaction_type=TransactionHistory.TransactionType.STOCK_OUT,
            quantity=2,
        )
        today = timezone.localdate()

        self.assertEqual(
            list(
                list_transaction_history(
                    item_id=item.pk,
                    user_id=self.actor.pk,
                    transaction_type=(
                        TransactionHistory.TransactionType.STOCK_OUT
                    ),
                    start=today,
                    end=today,
                )
            ),
            [stock_out],
        )

        with self.assertRaises(InvalidTransactionTypeError):
            list_transaction_history(transaction_type="BAD")
        with self.assertRaises(InvalidDateRangeError):
            list_transaction_history(
                start=today,
                end=today - timedelta(days=1),
            )
