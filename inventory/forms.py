from django import forms
from django.contrib.auth import get_user_model

from .models import Category, Item, TransactionHistory
from .selectors import (
    STOCK_STATUS_HEALTHY,
    STOCK_STATUS_LOW,
    STOCK_STATUS_OUT,
)


class ItemSearchForm(forms.Form):
    query = forms.CharField(
        label="Item name",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Search items"}),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.order_by("name"),
        required=False,
        empty_label="All categories",
    )
    stock_status = forms.ChoiceField(
        choices=(
            ("", "All stock statuses"),
            (STOCK_STATUS_LOW, "Low stock"),
            (STOCK_STATUS_OUT, "Out of stock"),
            (STOCK_STATUS_HEALTHY, "Healthy"),
        ),
        required=False,
    )
    include_inactive = forms.BooleanField(required=False)


class TransactionHistoryFilterForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=Item.objects.order_by("name"),
        required=False,
        empty_label="All items",
    )
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.order_by(get_user_model().USERNAME_FIELD),
        required=False,
        empty_label="All users",
    )
    transaction_type = forms.ChoiceField(
        choices=(("", "All transaction types"),)
        + tuple(TransactionHistory.TransactionType.choices),
        required=False,
    )
    start = forms.DateField(
        label="From",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end = forms.DateField(
        label="To",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")

        if start is not None and end is not None and start > end:
            raise forms.ValidationError(
                "The start date must be before or equal to the end date."
            )

        return cleaned_data
