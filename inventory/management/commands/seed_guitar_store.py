from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Category, Item, TransactionHistory
from inventory.seed_data import GUITAR_STORE_CATALOG
from inventory.services import (
    create_category,
    create_item,
    record_inventory_movement,
)


class Command(BaseCommand):
    help = (
        "Idempotently create the demo guitar-store catalog and initial stock."
    )

    required_permissions = (
        "inventory.add_category",
        "inventory.add_item",
        "inventory.record_inventory_movement",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=True,
            help=(
                "Existing active user who will own initial stock movements."
            ),
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            actor = user_model._default_manager.get(
                username=options["username"]
            )
        except user_model.DoesNotExist as error:
            raise CommandError(
                f"User does not exist: {options['username']}"
            ) from error

        if not actor.is_active:
            raise CommandError("The seed user must be active.")

        missing_permissions = [
            permission
            for permission in self.required_permissions
            if not actor.has_perm(permission)
        ]
        if missing_permissions:
            raise CommandError(
                "The seed user is missing permissions: "
                + ", ".join(missing_permissions)
            )

        summary = {
            "categories_created": 0,
            "categories_existing": 0,
            "items_created": 0,
            "items_existing": 0,
            "movements_created": 0,
        }

        with transaction.atomic():
            for category_name, item_specs in GUITAR_STORE_CATALOG.items():
                category = Category.objects.filter(
                    name__iexact=category_name
                ).first()
                if category is None:
                    category = create_category(
                        actor=actor,
                        name=category_name,
                    )
                    summary["categories_created"] += 1
                else:
                    summary["categories_existing"] += 1

                for item_name, reorder_level, initial_quantity in item_specs:
                    item = Item.objects.filter(
                        category=category,
                        name__iexact=item_name,
                    ).first()
                    if item is not None:
                        summary["items_existing"] += 1
                        continue

                    item = create_item(
                        actor=actor,
                        category_id=category.pk,
                        name=item_name,
                        reorder_level=reorder_level,
                    )
                    summary["items_created"] += 1

                    if initial_quantity > 0:
                        record_inventory_movement(
                            item_id=item.pk,
                            user=actor,
                            transaction_type=(
                                TransactionHistory.TransactionType.STOCK_IN
                            ),
                            quantity=initial_quantity,
                        )
                        summary["movements_created"] += 1

        self.stdout.write(
            self.style.SUCCESS("Guitar-store demo data is ready.")
        )
        self.stdout.write(
            ", ".join(
                f"{label}={count}" for label, count in summary.items()
            )
        )
