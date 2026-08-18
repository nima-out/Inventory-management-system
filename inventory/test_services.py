from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from .exceptions import (
    InactiveItemError,
    InsufficientStockError,
    InvalidInventoryUserError,
    InvalidQuantityError,
    InvalidTransactionTypeError,
    InventoryItemNotFoundError,
)
from .models import Category, Item, TransactionHistory
from .services import record_inventory_movement


class InventoryMovementServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="manager",
            password="test-password",
        )
        self.category = Category.objects.create(name="Electronics")
        self.item = Item.objects.create(
            category=self.category,
            name="Laptop",
            quantity=10,
            reorder_level=2,
        )

    def record_movement(self, **overrides):
        data = {
            "item_id": self.item.pk,
            "user": self.user,
            "transaction_type": (
                TransactionHistory.TransactionType.STOCK_IN
            ),
            "quantity": 5,
        }
        data.update(overrides)
        return record_inventory_movement(**data)

    def test_stock_in_increases_quantity_and_creates_history(self):
        movement = self.record_movement(quantity=5)

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 15)
        self.assertEqual(movement.item, self.item)
        self.assertEqual(movement.user, self.user)
        self.assertEqual(
            movement.transaction_type,
            TransactionHistory.TransactionType.STOCK_IN,
        )
        self.assertEqual(movement.quantity_moved, 5)

    def test_stock_out_decreases_quantity_and_creates_history(self):
        movement = self.record_movement(
            transaction_type=(
                TransactionHistory.TransactionType.STOCK_OUT
            ),
            quantity=4,
        )

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 6)
        self.assertEqual(
            movement.transaction_type,
            TransactionHistory.TransactionType.STOCK_OUT,
        )
        self.assertEqual(movement.quantity_moved, 4)

    def test_stock_out_can_reduce_quantity_to_zero(self):
        self.record_movement(
            transaction_type=(
                TransactionHistory.TransactionType.STOCK_OUT
            ),
            quantity=10,
        )

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 0)

    def test_insufficient_stock_changes_nothing(self):
        with self.assertRaises(InsufficientStockError):
            self.record_movement(
                transaction_type=(
                    TransactionHistory.TransactionType.STOCK_OUT
                ),
                quantity=11,
            )

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(TransactionHistory.objects.count(), 0)

    def test_invalid_quantities_are_rejected(self):
        for quantity in (0, -1, 1.5, True, "5"):
            with self.subTest(quantity=quantity):
                with self.assertRaises(InvalidQuantityError):
                    self.record_movement(quantity=quantity)

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(TransactionHistory.objects.count(), 0)

    def test_invalid_transaction_type_is_rejected(self):
        with self.assertRaises(InvalidTransactionTypeError):
            self.record_movement(transaction_type="INVALID")

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(TransactionHistory.objects.count(), 0)

    def test_inactive_item_is_rejected(self):
        self.item.is_active = False
        self.item.save()

        with self.assertRaises(InactiveItemError):
            self.record_movement()

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(TransactionHistory.objects.count(), 0)

    def test_unknown_item_is_rejected(self):
        with self.assertRaises(InventoryItemNotFoundError):
            self.record_movement(item_id=999999)

        self.assertEqual(TransactionHistory.objects.count(), 0)

    def test_anonymous_user_is_rejected(self):
        with self.assertRaises(InvalidInventoryUserError):
            self.record_movement(user=AnonymousUser())

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(TransactionHistory.objects.count(), 0)

    def test_quantity_update_rolls_back_if_history_creation_fails(self):
        with patch.object(
            TransactionHistory,
            "save",
            side_effect=RuntimeError("History creation failed."),
        ):
            with self.assertRaises(RuntimeError):
                self.record_movement(quantity=5)

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(TransactionHistory.objects.count(), 0)
