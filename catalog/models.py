import uuid

from django.db import models


class Category(models.Model):
    """Категория товаров (с поддержкой подкатегорий)."""

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория",
    )
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Slug", max_length=200, unique=True)
    order = models.PositiveIntegerField("Порядок сортировки", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

    def get_descendant_ids(self):
        """Возвращает список id всех подкатегорий (рекурсивно)."""
        ids = []
        for child in Category.objects.filter(parent=self):
            ids.append(child.pk)
            ids.extend(child.get_descendant_ids())
        return ids

    def get_ancestors(self):
        """Возвращает список родительских категорий от корня к родителю."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return list(reversed(ancestors))


class Product(models.Model):
    """Товар."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="Категория",
    )
    name = models.CharField("Название", max_length=300)
    price = models.DecimalField(
        "Цена",
        max_digits=12,
        decimal_places=2,
        help_text="Цена в рублях",
    )
    discount_percent = models.DecimalField(
        "Размер скидки, %",
        max_digits=5,
        decimal_places=2,
        default=0,
        blank=True,
        help_text="Процент скидки (0 — без скидки)",
    )
    description = models.TextField("Описание", blank=True)

    # Габариты и вес (для доставки)
    length_mm = models.PositiveIntegerField(
        "Длина упаковки, мм",
        null=True,
        blank=True
    )
    width_mm = models.PositiveIntegerField(
        "Ширина упаковки, мм",
        null=True,
        blank=True
    )
    height_mm = models.PositiveIntegerField(
        "Высота упаковки, мм",
        null=True,
        blank=True
    )
    weight_g = models.PositiveIntegerField(
        "Вес с упаковкой, г",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField("Показывать в каталоге", default=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self):
        return self.name

    @property
    def discounted_price(self):
        """Цена со скидкой (или обычная цена, если скидки нет)."""
        from decimal import Decimal

        if self.discount_percent and self.discount_percent > 0:
            value = self.price * (Decimal("1") - self.discount_percent / 100)
            return value.quantize(Decimal("0.01"))
        return self.price

    @property
    def has_discount(self):
        return self.discount_percent and self.discount_percent > 0

    def get_main_image(self):
        """Основное фото товара (первое с is_primary или первое по порядку)."""
        img = self.images.filter(is_primary=True).first()
        if img:
            return img
        return self.images.first()


class ProductImage(models.Model):
    """Фотография товара."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Товар",
    )
    image = models.ImageField("Файл", upload_to="catalog/products/%Y/%m/")
    is_primary = models.BooleanField("Основное фото", default=False)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["-is_primary", "order", "id"]
        verbose_name = "Фото товара"
        verbose_name_plural = "Фото товаров"

    def __str__(self):
        return f"{self.product.name} — фото"
