"""
Формы оформления заказа.
"""
from django import forms


class CheckoutForm(forms.Form):
    """Форма оформления заказа (получатель и доставка)."""

    recipient_name = forms.CharField(
        label="ФИО получателя",
        max_length=300,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Иванов Иван Иванович",
                "autocomplete": "name",
            }
        ),
    )
    recipient_phone = forms.CharField(
        label="Телефон",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "+7 (999) 123-45-67",
                "autocomplete": "tel",
            }
        ),
    )
    recipient_email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "email@example.com",
                "autocomplete": "email",
            }
        ),
    )
    delivery_tariff = forms.IntegerField(
        label="Тариф доставки СДЭК",
        min_value=1,
        widget=forms.HiddenInput(
            attrs={
                "id": "id_delivery_tariff",
            }
        ),
    )
    delivery_mode = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_delivery_mode"}),
    )
    city_code = forms.IntegerField(
        label="Город доставки",
        widget=forms.HiddenInput(attrs={"id": "id_city_code"}),
    )
    delivery_address = forms.CharField(
        label="Адрес доставки",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Улица, дом, квартира",
                "autocomplete": "street-address",
            }
        ),
    )
    pvz_code = forms.CharField(
        label="Код ПВЗ / постамата",
        required=False,
        max_length=50,
        widget=forms.HiddenInput(attrs={"id": "id_pvz_code"}),
    )
    comment = forms.CharField(
        label="Комментарий к заказу",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Пожелания по доставке",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            profile = getattr(self.user, "profile", None)
            if profile and not self.initial:
                self.initial.setdefault(
                    "recipient_name",
                    " ".join(
                        filter(
                            None,
                            [self.user.last_name, self.user.first_name],
                        )
                    ).strip()
                    or self.user.get_full_name(),
                )
                self.initial.setdefault(
                    "recipient_phone",
                    profile.phone or ""
                )
                self.initial.setdefault(
                    "recipient_email",
                    self.user.email or ""
                )
                self.initial.setdefault(
                    "delivery_address",
                    profile.address or ""
                )

    def clean(self):
        cleaned_data = super().clean()
        mode = (cleaned_data.get("delivery_mode") or "").strip()
        address = (cleaned_data.get("delivery_address") or "").strip()
        if mode == "door" and not address:
            self.add_error(
                "delivery_address",
                "Для доставки до двери укажите адрес доставки.",
            )
        return cleaned_data
