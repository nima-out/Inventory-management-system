from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from .models import Category, Item, TransactionHistory


class CategoryModelTests(TestCase):
    def test_string_representation_is_name(self):
        category = Category(name="Electronics")

        self.assertEqual(str(category), "Electronics")

    def test_categories_are_ordered_by_name(self):
        Category.objects.create(name="Tools")
        Category.objects.create(name="Electronics")

        names = list(Category.objects.values_list("name", flat=True))

        self.assertEqual(names, ["Electronics", "Tools"])

    def test_name_cannot_be_blank(self):
        category = Category(name="")

        with self.assertRaises(ValidationError):
            category.full_clean()

    def test_name_must_be_unique(self):
        Category.objects.create(name="Electronics")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="Electronics")

class ItemModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")

    def test_string_representation_is_name(self):
        item = Item(name="Laptop", category=self.category)

        self.assertEqual(str(item), "Laptop")

    def test_default_values(self):
        item = Item.objects.create(
            name="Laptop",
            category=self.category,
        )

        self.assertEqual(item.quantity, 0)
        self.assertEqual(item.reorder_level, 0)
        self.assertTrue(item.is_active)

    def test_item_name_is_unique_within_category(self):
        Item.objects.create(
            name="Laptop",
            category=self.category,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Item.objects.create(
                    name="Laptop",
                    category=self.category,
                )

    def test_same_name_is_allowed_in_different_categories(self):
        other_category = Category.objects.create(name="Office")

        Item.objects.create(name="Laptop", category=self.category)
        second_item = Item.objects.create(
            name="Laptop",
            category=other_category,
        )

        self.assertIsNotNone(second_item.pk)

    def test_quantity_cannot_be_negative(self):
        item = Item(
            name="Laptop",
            category=self.category,
            quantity=-1,
        )

        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_reorder_level_cannot_be_negative(self):
        item = Item(
            name="Laptop",
            category=self.category,
            reorder_level=-1,
        )

        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_item_at_reorder_level_is_low_stock(self):
        item = Item(
            name="Laptop",
            category=self.category,
            quantity=5,
            reorder_level=5,
        )

        self.assertTrue(item.is_low_stock)

    def test_item_above_reorder_level_is_not_low_stock(self):
        item = Item(
            name="Laptop",
            category=self.category,
            quantity=6,
            reorder_level=5,
        )

        self.assertFalse(item.is_low_stock)

    def test_category_with_items_cannot_be_deleted(self):
        Item.objects.create(
            name="Laptop",
            category=self.category,
        )

        with self.assertRaises(ProtectedError):
            self.category.delete()

class TransactionHistoryModelTests(TestCase):
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

    def create_transaction(self, **overrides):
        data = {
            "item": self.item,
            "user": self.user,
            "transaction_type": (
                TransactionHistory.TransactionType.STOCK_IN
            ),
            "quantity_moved": 5,
        }
        data.update(overrides)
        return TransactionHistory.objects.create(**data)

    def test_transaction_can_be_created(self):
        inventory_transaction = self.create_transaction()

        self.assertIsNotNone(inventory_transaction.pk)
        self.assertEqual(inventory_transaction.item, self.item)
        self.assertEqual(inventory_transaction.user, self.user)
        self.assertEqual(
            inventory_transaction.transaction_type,
            TransactionHistory.TransactionType.STOCK_IN,
        )
        self.assertEqual(inventory_transaction.quantity_moved, 5)
        self.assertIsNotNone(inventory_transaction.timestamp)

    def test_string_representation_describes_transaction(self):
        inventory_transaction = self.create_transaction(
            transaction_type=(
                TransactionHistory.TransactionType.STOCK_OUT
            ),
            quantity_moved=3,
        )

        self.assertEqual(
            str(inventory_transaction),
            "Laptop - Stock out (3)",
        )

    def test_related_names_are_available(self):
        inventory_transaction = self.create_transaction()

        self.assertEqual(
            self.item.transactions.get(),
            inventory_transaction,
        )
        self.assertEqual(
            self.user.inventory_transactions.get(),
            inventory_transaction,
        )

    def test_transactions_are_ordered_newest_first(self):
        first = self.create_transaction(quantity_moved=1)
        second = self.create_transaction(quantity_moved=2)

        transaction_ids = list(
            TransactionHistory.objects.values_list("id", flat=True)
        )

        self.assertEqual(transaction_ids, [second.id, first.id])

    def test_quantity_moved_must_be_greater_than_zero(self):
        inventory_transaction = TransactionHistory(
            item=self.item,
            user=self.user,
            transaction_type=(
                TransactionHistory.TransactionType.STOCK_IN
            ),
            quantity_moved=0,
        )

        with self.assertRaises(ValidationError):
            inventory_transaction.full_clean()

    def test_database_rejects_zero_quantity(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_transaction(quantity_moved=0)

    def test_transaction_type_must_be_valid(self):
        inventory_transaction = TransactionHistory(
            item=self.item,
            user=self.user,
            transaction_type="BAD",
            quantity_moved=1,
        )

        with self.assertRaises(ValidationError):
            inventory_transaction.full_clean()

    def test_database_rejects_invalid_transaction_type(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_transaction(transaction_type="BAD")

    def test_existing_transaction_cannot_be_modified(self):
        inventory_transaction = self.create_transaction(quantity_moved=5)
        inventory_transaction.quantity_moved = 10

        with self.assertRaisesMessage(
            ValidationError,
            "Transaction history cannot be modified.",
        ):
            inventory_transaction.save()

        inventory_transaction.refresh_from_db()
        self.assertEqual(inventory_transaction.quantity_moved, 5)

    def test_transaction_cannot_be_deleted(self):
        inventory_transaction = self.create_transaction()

        with self.assertRaisesMessage(
            ValidationError,
            "Transaction history cannot be deleted.",
        ):
            inventory_transaction.delete()

        self.assertTrue(
            TransactionHistory.objects.filter(
                pk=inventory_transaction.pk
            ).exists()
        )

    def test_referenced_item_cannot_be_deleted(self):
        self.create_transaction()

        with self.assertRaises(ProtectedError):
            self.item.delete()

    def test_referenced_user_cannot_be_deleted(self):
        self.create_transaction()

        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_queryset_update_is_rejected(self):
        inventory_transaction = self.create_transaction(quantity_moved=5)

        with self.assertRaisesMessage(
            ValidationError,
            "Transaction history cannot be modified.",
        ):
            TransactionHistory.objects.filter(
                pk=inventory_transaction.pk
            ).update(quantity_moved=10)

        inventory_transaction.refresh_from_db()
        self.assertEqual(inventory_transaction.quantity_moved, 5)

    def test_queryset_delete_is_rejected(self):
        inventory_transaction = self.create_transaction()

        with self.assertRaisesMessage(
            ValidationError,
            "Transaction history cannot be deleted.",
        ):
            TransactionHistory.objects.filter(
                pk=inventory_transaction.pk
            ).delete()

        self.assertTrue(
            TransactionHistory.objects.filter(
                pk=inventory_transaction.pk
            ).exists()
        )

    def test_bulk_update_is_rejected(self):
        inventory_transaction = self.create_transaction(quantity_moved=5)
        inventory_transaction.quantity_moved = 10

        with self.assertRaisesMessage(
            ValidationError,
            "Transaction history cannot be modified.",
        ):
            TransactionHistory.objects.bulk_update(
                [inventory_transaction],
                ["quantity_moved"],
            )

        inventory_transaction.refresh_from_db()
        self.assertEqual(inventory_transaction.quantity_moved, 5)