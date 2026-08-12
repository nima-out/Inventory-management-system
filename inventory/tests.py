from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from .models import Category,Item 


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