from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name



class Item(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="items",
    )
    name = models.CharField(max_length=150)
    quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_item_name_per_category",
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

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level



class TransactionHistory(models.Model):
    class TransactionType(models.TextChoices):
        STOCK_IN = "IN", "Stock in"
        STOCK_OUT = "OUT", "Stock out"

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