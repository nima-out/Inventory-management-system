from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Category


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