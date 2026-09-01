from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from ..models import Category, Item


class InventoryUiRenderingTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_superuser(
            username="ui-manager",
            password="test-password",
        )
        self.category = Category.objects.create(name="Amplifiers")
        self.item = Item.objects.create(
            category=self.category,
            name="Twin Reverb",
            reorder_level=2,
        )

    def test_login_uses_local_assets_and_accessible_password_control(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "/static/vendor/bootstrap/5.3.8/bootstrap.min.css",
        )
        self.assertContains(
            response,
            "/static/vendor/bootstrap/5.3.8/bootstrap.bundle.min.js",
        )
        self.assertContains(response, "/static/inventory/js/app.js")
        self.assertContains(response, 'data-bs-theme="dark"')
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, "data-password-toggle")
        self.assertContains(response, 'aria-pressed="false"')

    def test_authenticated_shell_links_mobile_toggle_to_offcanvas(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("inventory:dashboard"))

        self.assertContains(response, 'data-bs-target="#primary-navigation"')
        self.assertContains(response, 'aria-controls="primary-navigation"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, 'id="primary-navigation"')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'class="rack-panel"')

    def test_navigation_remains_permission_aware(self):
        staff_user = get_user_model().objects.create_user(
            username="ui-staff",
            password="test-password",
        )
        staff_user.groups.add(Group.objects.get(name="Staff"))
        self.client.force_login(staff_user)

        response = self.client.get(reverse("inventory:item-list"))

        self.assertContains(response, reverse("inventory:item-list"))
        self.assertContains(response, reverse("inventory:record-movement"))
        self.assertNotContains(response, reverse("inventory:item-create"))
        self.assertNotContains(response, reverse("inventory:category-create"))

    def test_item_filters_include_progressive_enhancement_hooks(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("inventory:item-list"),
            {"stock_status": "low"},
        )

        self.assertContains(response, 'data-bs-target="#item-filters"')
        self.assertContains(response, "data-filter-panel")
        self.assertContains(response, 'data-expanded="true"')
        self.assertContains(response, 'aria-expanded="true"')

    def test_post_forms_expose_busy_and_dirty_state_hooks(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("inventory:item-create"))

        self.assertContains(response, "data-submit-form")
        self.assertContains(response, "data-dirty-guard")
        self.assertContains(response, "data-submit-button")
        self.assertContains(response, 'data-busy-label="Adding item…"')

    def test_server_validation_renders_linked_invalid_field_feedback(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("inventory:item-create"),
            {
                "name": "Twin Reverb",
                "category": self.category.pk,
                "reorder_level": -1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(
            response,
            'aria-describedby="id_reorder_level-feedback"',
        )
        self.assertContains(response, 'id="id_reorder_level-feedback"')
