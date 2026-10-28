
from django import forms

from coupons.models import Coupon


class CouponForm(forms.ModelForm):
    discount_type = forms.ChoiceField(
        choices=[
            ("percentage", "Percentage"),
            ("fixed", "Fixed Amount"),
        ],
    )

    status = forms.ChoiceField(
        choices=[
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
    )

    class Meta:
        model = Coupon
        fields = [
            "code",
            "coupon_name",
            "discount_type",
            "discount_value",
            "minimum_spend",
            "maximum_discount",
            "usage_limit",
            "start_date",
            "expiry_date",
            "status",
        ]

        widgets = {
            "start_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "expiry_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "discount_value": forms.NumberInput(
                attrs={"min": "0.01", "step": "0.01"},
            ),
            "minimum_spend": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"},
            ),
            "maximum_discount": forms.NumberInput(
                attrs={"min": "0", "step": "1"},
            ),
            "usage_limit": forms.NumberInput(
                attrs={"min": "1", "step": "1"},
            ),
        }

        labels = {
            "code": "Coupon Code",
            "coupon_name": "Coupon Name",
            "discount_value": "Discount Value",
            "minimum_spend": "Minimum Spend",
            "maximum_discount": "Maximum Discount",
            "usage_limit": "Usage Limit",
            "start_date": "Start Date and Time",
            "expiry_date": "Expiry Date and Time",
        }

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()

        if not code:
            raise forms.ValidationError(
                "Coupon code is required."
            )

        # Coupon lookup is case-insensitive, so prevent duplicates.
        existing_coupons = Coupon.objects.filter(
            code__iexact=code
        )
        #ignore the coupon I am currently editing. Check whether any other coupon uses this code.
        if self.instance.pk:
            existing_coupons = existing_coupons.exclude(
                pk=self.instance.pk
            )

        if existing_coupons.exists():
            raise forms.ValidationError(
                "A coupon with this code already exists."
            )

        return code

    def clean(self):
        cleaned_data = super().clean()

        discount_type = cleaned_data.get("discount_type")
        discount_value = cleaned_data.get("discount_value")
        minimum_spend = cleaned_data.get("minimum_spend")
        maximum_discount = cleaned_data.get("maximum_discount")
        usage_limit = cleaned_data.get("usage_limit")
        start_date = cleaned_data.get("start_date")
        expiry_date = cleaned_data.get("expiry_date")

        if discount_value is not None and discount_value <= 0:
            self.add_error(
                "discount_value",
                "Discount value must be greater than zero.",
            )

        if (
            discount_type == "percentage"
            and discount_value is not None
            and discount_value > 100
        ):
            self.add_error(
                "discount_value",
                "Percentage discount cannot exceed 100%.",
            )

        if minimum_spend is not None and minimum_spend < 0:
            self.add_error(
                "minimum_spend",
                "Minimum spend cannot be negative.",
            )

        if maximum_discount is not None and maximum_discount < 0:
            self.add_error(
                "maximum_discount",
                "Maximum discount cannot be negative.",
            )

        if usage_limit is not None and usage_limit < 1:
            self.add_error(
                "usage_limit",
                "Usage limit must be at least 1.",
            )

        if (
            start_date is not None
            and expiry_date is not None
            and expiry_date <= start_date
        ):
            self.add_error(
                "expiry_date",
                "Expiry date must be later than the start date.",
            )

        return cleaned_data
