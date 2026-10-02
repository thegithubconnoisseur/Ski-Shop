from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            "email",
            "full_name",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
        ]
        widgets = {
            "email": forms.EmailInput(
                attrs={"placeholder": "you@example.com", "autocomplete": "email"}
            ),
            "full_name": forms.TextInput(
                attrs={"placeholder": "Full name", "autocomplete": "name"}
            ),
            "phone": forms.TextInput(
                attrs={"placeholder": "+234 800 000 0000", "autocomplete": "tel"}
            ),
            "address_line1": forms.TextInput(
                attrs={"placeholder": "Street address", "autocomplete": "address-line1"}
            ),
            "address_line2": forms.TextInput(
                attrs={
                    "placeholder": "Apartment, suite, etc. (optional)",
                    "autocomplete": "address-line2",
                }
            ),
            "city": forms.TextInput(
                attrs={"placeholder": "City", "autocomplete": "address-level2"}
            ),
            "state": forms.TextInput(
                attrs={"placeholder": "State / Province", "autocomplete": "address-level1"}
            ),
            "postal_code": forms.TextInput(
                attrs={"placeholder": "Postal code", "autocomplete": "postal-code"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} field-input".strip()
        self.fields["country"].empty_label = "Select your country"
        self.fields["address_line2"].required = False
