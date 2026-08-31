from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Category, Item, TransactionHistory
from .services import record_inventory_movement


class InventoryViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="web-manager",
            password="test-password",
        )
        self.category = Category.objects.create(name="Guitars")
        self.item = Item.objects.create(
            category=self.category,
            name="Telecaster",
            reorder_level=2,
        )
        record_inventory_movement(
            item_id=self.item.pk,
            user=self.user,
            transaction_type=TransactionHistory.TransactionType.STOCK_IN,
            quantity=5,
        )
        self.item.refresh_from_db()

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("inventory:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('inventory:dashboard')}",
        )

    def test_authenticated_user_without_permission_receives_403(self):
        viewer = get_user_model().objects.create_user(
            username="viewer",
            password="test-password",
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse("inventory:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_dashboard_uses_current_inventory_summary(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("inventory:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inventory/dashboard.html")
        self.assertEqual(response.context["summary"]["total_units"], 5)

    def test_item_create_starts_at_zero(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("inventory:item-create"),
            {
                "name": "Stratocaster",
                "category": self.category.pk,
                "reorder_level": 3,
            },
        )

        self.assertRedirects(response, reverse("inventory:item-list"))
        self.assertEqual(Item.objects.get(name="Stratocaster").quantity, 0)

    def test_stock_movement_updates_item_and_redirects_to_history(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("inventory:record-movement"),
            {
                "item": self.item.pk,
                "transaction_type": (
                    TransactionHistory.TransactionType.STOCK_OUT
                ),
                "quantity": 2,
            },
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 3)
        self.assertRedirects(
            response,
            f"{reverse('inventory:transaction-history')}?item={self.item.pk}",
        )

    def test_insufficient_stock_is_rendered_as_form_error(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("inventory:record-movement"),
            {
                "item": self.item.pk,
                "transaction_type": (
                    TransactionHistory.TransactionType.STOCK_OUT
                ),
                "quantity": 6,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not enough stock")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)

    def test_category_with_item_cannot_be_deleted(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "inventory:category-delete",
                kwargs={"category_id": self.category.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot be deleted")
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_item_can_be_archived_and_reactivated(self):
        self.client.force_login(self.user)
        archive_url = reverse(
            "inventory:item-archive",
            kwargs={"item_id": self.item.pk},
        )
        reactivate_url = reverse(
            "inventory:item-reactivate",
            kwargs={"item_id": self.item.pk},
        )

        self.client.post(archive_url)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

        self.client.post(reactivate_url)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_transaction_history_can_filter_by_item(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("inventory:transaction-history"),
            {"item": self.item.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)


class ProvisionedGroupTests(TestCase):
    def test_manager_has_catalog_and_movement_permissions(self):
        manager = Group.objects.get(name="Manager")
        codenames = set(
            manager.permissions.values_list("codename", flat=True)
        )

        self.assertTrue(
            {
                "add_category",
                "change_category",
                "delete_category",
                "add_item",
                "change_item",
                "archive_item",
                "reactivate_item",
                "record_inventory_movement",
            }.issubset(codenames)
        )

    def test_staff_is_read_and_movement_only(self):
        staff = Group.objects.get(name="Staff")
        codenames = set(staff.permissions.values_list("codename", flat=True))

        self.assertEqual(
            codenames,
            {
                "view_category",
                "view_item",
                "record_inventory_movement",
                "view_transactionhistory",
            },
        )
