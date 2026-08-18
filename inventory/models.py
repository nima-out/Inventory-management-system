from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="category_name_ci_unique",
            ),
        ]

    def __str__(self):
        return self.name


class ItemQuerySet(models.QuerySet):
    quantity_error_message = (
        "Item quantity can only be changed through the inventory "
        "movement service."
    )
    deletion_error_message = "Items must be archived instead of deleted."

    def update(self, **kwargs):
        if "quantity" in kwargs:
            raise ValidationError(self.quantity_error_message)

        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if "quantity" in fields:
            raise ValidationError(self.quantity_error_message)

        return super().bulk_update(
            objs,
            fields,
            batch_size=batch_size,
        )

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        objs = list(objs)
        if any(item.quantity != 0 for item in objs):
            raise ValidationError(self.quantity_error_message)

        if update_conflicts and "quantity" in (update_fields or ()):
            raise ValidationError(self.quantity_error_message)

        return super().bulk_create(
            objs,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )

    def delete(self):
        raise ValidationError(self.deletion_error_message)

    def _change_quantity(self, expression):
        return super().update(quantity=expression)

    def _increase_quantity(self, quantity):
        return self._change_quantity(models.F("quantity") + quantity)

    def _decrease_quantity_if_available(self, quantity):
        return self.filter(quantity__gte=quantity)._change_quantity(
            models.F("quantity") - quantity
        )


class Item(models.Model):
    objects = ItemQuerySet.as_manager()

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="items",
    )
    name = models.CharField(max_length=150)
    quantity = models.PositiveIntegerField(default=0, editable=False)
    reorder_level = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        permissions = [
            ("record_inventory_movement", "Can record inventory movement"),
            ("archive_item", "Can archive item"),
            ("reactivate_item", "Can reactivate item"),
        ]
        constraints = [
            models.UniqueConstraint(
                models.F("category"),
                Lower("name"),
                name="item_category_name_ci_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="item_quantity_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(reorder_level__gte=0),
                name="item_reorder_level_gte_0",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.quantity != 0:
                raise ValidationError(
                    ItemQuerySet.quantity_error_message
                )
        else:
            update_fields = kwargs.get("update_fields")
            quantity_will_be_saved = (
                update_fields is None or "quantity" in update_fields
            )
            if quantity_will_be_saved:
                saved_quantity = type(self).objects.only("quantity").get(
                    pk=self.pk
                ).quantity
                if self.quantity != saved_quantity:
                    raise ValidationError(
                        ItemQuerySet.quantity_error_message
                    )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(ItemQuerySet.deletion_error_message)

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level


class ImmutableTransactionQuerySet(models.QuerySet):
    error_message = "Transaction history cannot be modified."

    def update(self, **kwargs):
        raise ValidationError(self.error_message)

    def delete(self):
        raise ValidationError("Transaction history cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError(self.error_message)

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        if update_conflicts:
            raise ValidationError(self.error_message)

        return super().bulk_create(
            objs,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )


class TransactionHistory(models.Model):
    class TransactionType(models.TextChoices):
        STOCK_IN = "IN", "Stock in"
        STOCK_OUT = "OUT", "Stock out"

    objects = ImmutableTransactionQuerySet.as_manager()

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_transactions",
    )
    transaction_type = models.CharField(
        max_length=3,
        choices=TransactionType.choices,
    )
    quantity_moved = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp", "-id"]
        verbose_name_plural = "transaction history"
        indexes = [
            models.Index(
                fields=["item", "-timestamp"],
                name="txn_item_timestamp_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_moved__gt=0),
                name="transaction_quantity_moved_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(transaction_type__in=["IN", "OUT"]),
                name="transaction_type_valid",
            ),
        ]

    def __str__(self):
        transaction_label = self.TransactionType(
            self.transaction_type
        ).label

        return (
            f"{self.item.name} - "
            f"{transaction_label} "
            f"({self.quantity_moved})"
        )

    def save(self, *args, **kwargs):
        if (
            self.pk is not None
            and type(self).objects.filter(pk=self.pk).exists()
        ):
            raise ValidationError("Transaction history cannot be modified.")

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Transaction history cannot be deleted.")
