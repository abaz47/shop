import uuid

from django.db import models
from django.urls import reverse


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
    """
    Базовый товар (модель).
    Одна страница каталога; варианты (цвет, цена, фото) — в ProductVariant.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    slug = models.SlugField(
        "Slug",
        max_length=300,
        unique=True,
        null=True,
        blank=True,
        help_text="ЧПУ для URL; если пусто — используется id",
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
    description = models.TextField("Описание", blank=True)

    # Габариты и вес (для доставки), общие для всех вариантов
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

    def get_absolute_url(self):
        """URL страницы товара: по slug, если задан, иначе по pk."""
        if self.slug:
            return reverse(
                "catalog:product_detail",
                kwargs={"slug_or_pk": self.slug},
            )
        return reverse(
            "catalog:product_detail",
            kwargs={"slug_or_pk": str(self.pk)},
        )

    def get_main_image(self):
        """Основное фото: первое фото первого варианта с изображениями."""
        variant = self.variants.filter(is_active=True).first()
        if variant:
            return variant.get_main_image()
        return None


class ProductVariant(models.Model):
    """Вариант товара (цвет и т.п.): своя цена, артикул, фото."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name="Товар",
    )
    color = models.CharField(
        "Цвет / исполнение",
        max_length=100,
        blank=True,
        help_text="Например: красный, синий",
    )
    sku = models.CharField(
        "Артикул",
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Внутренний артикул варианта",
    )
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
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Показывать", default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Вариант товара"
        verbose_name_plural = "Варианты товара"

    def __str__(self):
        if self.color:
            return f"{self.product.name} — {self.color}"
        return f"{self.product.name} (арт. {self.sku})"

    @property
    def discounted_price(self):
        """Цена со скидкой (или обычная цена, если скидки нет)."""
        from decimal import Decimal

        if self.discount_percent and self.discount_percent > 0:
            value = self.price * (
                Decimal("1") - self.discount_percent / 100
            )
            return value.quantize(Decimal("0.01"))
        return self.price

    @property
    def has_discount(self):
        return self.discount_percent and self.discount_percent > 0

    def get_main_image(self):
        """Основное фото варианта (is_primary или первое)."""
        img = self.images.filter(is_primary=True).first()
        if img:
            return img
        return self.images.first()


class ProductImage(models.Model):
    """Фотография варианта товара."""

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Вариант товара",
    )
    image = models.ImageField("Файл", upload_to="catalog/products/%Y/%m/")
    is_primary = models.BooleanField("Основное фото", default=False)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["-is_primary", "order", "id"]
        verbose_name = "Фото варианта"
        verbose_name_plural = "Фото вариантов"

    def __str__(self):
        return f"{self.variant} — фото"
