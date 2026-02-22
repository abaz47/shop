"""
Модели корзины: корзина и позиции корзины.
"""
from django.conf import settings
from django.db import models


class Cart(models.Model):
    """Корзина покупок."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
        verbose_name="Пользователь",
    )
    session_key = models.CharField(
        "Ключ сессии",
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Для анонимных пользователей",
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "корзина"
        verbose_name_plural = "корзины"
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                condition=models.Q(session_key__isnull=False)
                & ~models.Q(session_key=""),
                name="cart_unique_session_key",
            ),
        ]

    def __str__(self):
        if self.user_id:
            return f"Корзина пользователя {self.user_id}"
        return f"Корзина (сессия {self.session_key[:8]}…)"

    @property
    def total_quantity(self):
        """Общее количество товаров в корзине."""
        return sum(
            item.quantity for item in self.items.select_related("product")
        )

    @property
    def total_price(self):
        """Сумма по корзине (с учётом скидок на товары)."""
        from decimal import Decimal

        total = Decimal("0")
        for item in self.items.select_related("product"):
            total += item.line_total
        return total


class CartItem(models.Model):
    """Позиция в корзине."""

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Корзина",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="Товар",
    )
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "позиция корзины"
        verbose_name_plural = "позиции корзины"
        unique_together = [["cart", "product"]]

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"

    @property
    def line_total(self):
        """Сумма по позиции (цена со скидкой × количество)."""
        return self.product.discounted_price * self.quantity
