"""
Модели заказов: заказ и позиции заказа.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


def _unpaid_expiry_hours():
    """Число часов, после которых неоплаченный заказ считается просроченным."""
    return 6


class OrderQuerySet(models.QuerySet):
    """QuerySet заказов с фильтром видимости в личном кабинете."""

    def visible_in_cabinet(self):
        """
        Заказы, которые показываются в личном кабинете.
        Неоплаченные старше 6 часов исключаются.
        """
        from datetime import timedelta
        threshold = timezone.now() - timedelta(hours=_unpaid_expiry_hours())
        return self.exclude(
            status=self.model.Status.UNPAID,
            created_at__lt=threshold,
        )


class OrderManager(models.Manager):
    """Менеджер заказов с поддержкой visible_in_cabinet."""

    def get_queryset(self):
        return OrderQuerySet(self.model, using=self._db)

    def visible_in_cabinet(self):
        return self.get_queryset().visible_in_cabinet()

    def unpaid_expired(self):
        """Неоплаченные заказы старше 6 часов (для удаления)."""
        from datetime import timedelta
        threshold = timezone.now() - timedelta(hours=_unpaid_expiry_hours())
        return self.filter(
            status=self.model.Status.UNPAID,
            created_at__lt=threshold,
        )


class Order(models.Model):
    """Заказ пользователя."""

    class Status(models.TextChoices):
        UNPAID = "new", "Не оплачен"
        PAID = "confirmed", "Оплачен"
        IN_DELIVERY = "in_delivery", "Передан в доставку"
        DELIVERED = "delivered", "Доставлен"
        CANCELLED = "cancelled", "Отменён"
        REFUNDED = "refunded", "Возврат"

    class DeliveryMethod(models.TextChoices):
        CDEK = "cdek", "СДЭК"

    class DeliveryType(models.TextChoices):
        PICKUP = "pickup", "Пункт выдачи СДЭК"
        COURIER = "courier", "Курьер СДЭК"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Пользователь",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.UNPAID,
        db_index=True,
    )
    delivery_method = models.CharField(
        "Способ доставки",
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.CDEK,
    )
    delivery_type = models.CharField(
        "Тип доставки СДЭК",
        max_length=20,
        choices=DeliveryType.choices,
        default=DeliveryType.PICKUP,
    )
    delivery_tariff_code = models.PositiveIntegerField(
        "Код тарифа СДЭК",
        null=True,
        blank=True,
        help_text="Код тарифа на момент оформления "
        "(136, 137, 138, 233 и т.д.)",
    )
    cdek_order_uuid = models.CharField(
        "UUID заказа в СДЭК",
        max_length=50,
        blank=True,
        help_text="UUID, присвоенный СДЭК при регистрации заказа через API",
    )
    # Сумма товаров (на момент оформления)
    products_total = models.DecimalField(
        "Сумма товаров",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    delivery_cost = models.DecimalField(
        "Стоимость доставки",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
    )
    total = models.DecimalField(
        "Итого",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    # Данные получателя (дублируем для истории)
    recipient_name = models.CharField(
        "ФИО получателя",
        max_length=300,
    )
    recipient_phone = models.CharField(
        "Телефон получателя",
        max_length=20,
    )
    recipient_email = models.EmailField(
        "Email получателя",
        blank=True,
    )
    # Адрес: для СДЭК может быть код города + адрес или код ПВЗ
    city_code = models.PositiveIntegerField(
        "Код города СДЭК",
        null=True,
        blank=True,
    )
    delivery_address = models.TextField(
        "Адрес доставки",
        blank=True,
        help_text="Полный адрес для курьерской доставки",
    )
    pvz_code = models.CharField(
        "Код ПВЗ СДЭК",
        max_length=50,
        blank=True,
        help_text="При доставке в пункт выдачи",
    )
    # Идентификатор платежа T‑Банка, необходим для отмены через /v2/Cancel.
    # Сохраняется при инициации платежа и при получении уведомления.
    tbank_payment_id = models.CharField(
        "PaymentId T‑Банка",
        max_length=50,
        blank=True,
        db_index=True,
    )
    comment = models.TextField("Комментарий к заказу", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    objects = OrderManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "заказ"
        verbose_name_plural = "заказы"

    def __str__(self):
        return f"Заказ #{self.pk} от {self.created_at.strftime('%d.%m.%Y')}"

    def recalc_totals(self):
        """Пересчитывает products_total по позициям и total."""
        self.products_total = sum(
            item.line_total for item in self.items.select_related("variant")
        )
        self.total = self.products_total + self.delivery_cost
        self.save(update_fields=["products_total", "total", "updated_at"])


class OrderItem(models.Model):
    """Позиция в заказе (вариант товара)."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заказ",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="Вариант товара",
    )
    price = models.DecimalField(
        "Цена за единицу",
        max_digits=12,
        decimal_places=2,
        help_text="Цена на момент оформления",
    )
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "позиция заказа"
        verbose_name_plural = "позиции заказа"

    def __str__(self):
        return f"{self.variant.product.name} × {self.quantity}"

    @property
    def line_total(self):
        """Сумма по позиции."""
        from decimal import Decimal
        return (self.price or Decimal("0")) * self.quantity
