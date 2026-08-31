from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from ..exceptions import (
    CategoryInUseError,
    DuplicateCategoryNameError,
    InactiveItemError,
    InsufficientStockError,
    InvalidInventoryUserError,
    InvalidQuantityError,
    InvalidTransactionTypeError,
    InventoryItemNotFoundError,
    InventoryPermissionDeniedError,
)
from ..models import Category, Item, TransactionHistory
from ..services import (
    archive_item,
    create_category,
    create_item,
    delete_category,
    reactivate_item,
    record_inventory_movement,
    rename_category,
    update_item,
)


class InventoryMovementServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="manager",
            password="test-password",
        )
        movement_permission = Permission.objects.get(
            content_type__app_label="inventory",
            codename="record_inventory_movement",
        )
        self.user.user_permissions.add(movement_permission)
        self.category = Category.objects.create(name="Electronics")
        self.item = Item.objects.create(
            category=self.category,
            name="Laptop",
            reorder_level=2,
        )
        record_inventory_movement(
            item_id=self.item.pk,
            user=self.user,
            transaction_type=TransactionHistory.TransactionType.STOCK_IN,
            quantity=10,
        )
        self.item.refresh_from_db()
        self.initial_transaction_count = 1

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
        self.assertEqual(
            TransactionHistory.objects.count(),
            self.initial_transaction_count,
        )

    def test_invalid_quantities_are_rejected(self):
        for quantity in (0, -1, 1.5, True, "5"):
            with self.subTest(quantity=quantity):
                with self.assertRaises(InvalidQuantityError):
                    self.record_movement(quantity=quantity)

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(
            TransactionHistory.objects.count(),
            self.initial_transaction_count,
        )

    def test_invalid_transaction_type_is_rejected(self):
        with self.assertRaises(InvalidTransactionTypeError):
            self.record_movement(transaction_type="INVALID")

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(
            TransactionHistory.objects.count(),
            self.initial_transaction_count,
        )

    def test_inactive_item_is_rejected(self):
        self.item.is_active = False
        self.item.save()

        with self.assertRaises(InactiveItemError):
            self.record_movement()

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(
            TransactionHistory.objects.count(),
            self.initial_transaction_count,
        )

    def test_unknown_item_is_rejected(self):
        with self.assertRaises(InventoryItemNotFoundError):
            self.record_movement(item_id=999999)

        self.assertEqual(
            TransactionHistory.objects.count(),
            self.initial_transaction_count,
        )

    def test_anonymous_user_is_rejected(self):
        with self.assertRaises(InvalidInventoryUserError):
            self.record_movement(user=AnonymousUser())

        self.item.refresh_from_db()

        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(
            TransactionHistory.objects.count(),
            self.initial_transaction_count,
        )

    def test_user_without_permission_is_rejected(self):
        unauthorized_user = get_user_model().objects.create_user(
            username="unauthorized",
            password="test-password",
        )

        with self.assertRaises(InventoryPermissionDeniedError):
            self.record_movement(user=unauthorized_user)

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(
            TransactionHistory.objects.count(),
            self.initial_transaction_count,
        )

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
        self.assertEqual(
            TransactionHistory.objects.count(),
            self.initial_transaction_count,
        )


class CatalogServiceTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username="catalog-manager",
            password="test-password",
        )

    def test_category_lifecycle_normalizes_names(self):
        category = create_category(
            actor=self.actor,
            name="  Electric   Guitars  ",
        )
        renamed = rename_category(
            actor=self.actor,
            category_id=category.pk,
            name=" Solid   Body ",
        )

        self.assertEqual(renamed.name, "Solid Body")

    def test_duplicate_category_name_is_case_insensitive(self):
        create_category(actor=self.actor, name="Accessories")

        with self.assertRaises(DuplicateCategoryNameError):
            create_category(actor=self.actor, name="accessories")

    def test_empty_category_can_be_deleted(self):
        category = create_category(actor=self.actor, name="Empty")

        delete_category(actor=self.actor, category_id=category.pk)

        self.assertFalse(Category.objects.filter(pk=category.pk).exists())

    def test_category_with_item_cannot_be_deleted(self):
        category = create_category(actor=self.actor, name="Guitars")
        create_item(
            actor=self.actor,
            category_id=category.pk,
            name="Telecaster",
        )

        with self.assertRaises(CategoryInUseError):
            delete_category(actor=self.actor, category_id=category.pk)

    def test_item_lifecycle_preserves_service_managed_quantity(self):
        category = create_category(actor=self.actor, name="Guitars")
        item = create_item(
            actor=self.actor,
            category_id=category.pk,
            name="  Player   Telecaster ",
            reorder_level=2,
        )
        record_inventory_movement(
            item_id=item.pk,
            user=self.actor,
            transaction_type=TransactionHistory.TransactionType.STOCK_IN,
            quantity=5,
        )

        item = update_item(
            actor=self.actor,
            item_id=item.pk,
            category_id=category.pk,
            name="Player II Telecaster",
            reorder_level=3,
        )
        archive_item(actor=self.actor, item_id=item.pk)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 5)
        self.assertFalse(item.is_active)

        reactivate_item(actor=self.actor, item_id=item.pk)
        item.refresh_from_db()
        self.assertEqual(item.name, "Player II Telecaster")
        self.assertEqual(item.reorder_level, 3)
        self.assertEqual(item.quantity, 5)
        self.assertTrue(item.is_active)

    def test_catalog_service_requires_permission(self):
        unauthorized_user = get_user_model().objects.create_user(
            username="viewer",
            password="test-password",
        )

        with self.assertRaises(InventoryPermissionDeniedError):
            create_category(actor=unauthorized_user, name="Guitars")
