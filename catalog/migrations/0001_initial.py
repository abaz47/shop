# Generated manually for catalog app

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="Название")),
                ("slug", models.SlugField(unique=True, max_length=200, verbose_name="Slug")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")),
            ],
            options={
                "verbose_name": "Категория",
                "verbose_name_plural": "Категории",
                "ordering": ["order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=300, verbose_name="Название")),
                ("price", models.DecimalField(decimal_places=2, help_text="Цена в рублях", max_digits=12, verbose_name="Цена")),
                ("discount_percent", models.DecimalField(blank=True, decimal_places=2, default=0, help_text="Процент скидки (0 — без скидки)", max_digits=5, verbose_name="Размер скидки, %")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("length_mm", models.PositiveIntegerField(blank=True, null=True, verbose_name="Длина упаковки, мм")),
                ("width_mm", models.PositiveIntegerField(blank=True, null=True, verbose_name="Ширина упаковки, мм")),
                ("height_mm", models.PositiveIntegerField(blank=True, null=True, verbose_name="Высота упаковки, мм")),
                ("weight_g", models.PositiveIntegerField(blank=True, null=True, verbose_name="Вес с упаковкой, г")),
                ("is_active", models.BooleanField(default=True, verbose_name="Показывать в каталоге")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата обновления")),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="products", to="catalog.category", verbose_name="Категория")),
            ],
            options={
                "verbose_name": "Товар",
                "verbose_name_plural": "Товары",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="catalog/products/%Y/%m/", verbose_name="Файл")),
                ("is_primary", models.BooleanField(default=False, verbose_name="Основное фото")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="catalog.product", verbose_name="Товар")),
            ],
            options={
                "verbose_name": "Фото товара",
                "verbose_name_plural": "Фото товаров",
                "ordering": ["-is_primary", "order", "id"],
            },
        ),
    ]
