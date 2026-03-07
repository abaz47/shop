import uuid

from django.shortcuts import get_object_or_404, render

from .models import Category, Product


def product_list(request, slug=None):
    """Список товаров (каталог), по категории и подкатегориям."""
    root_categories = Category.objects.filter(
        parent__isnull=True,
    ).prefetch_related("children")
    category = None
    products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("variants__images")
    )

    open_accordion_ids = []
    if slug:
        category = get_object_or_404(
            Category.objects.prefetch_related("children"),
            slug=slug,
        )
        category_ids = [category.pk] + category.get_descendant_ids()
        products = products.filter(category_id__in=category_ids)
        ancestors = category.get_ancestors()
        root_pk = (
            ancestors[0].pk if ancestors else category.pk
        )
        open_accordion_ids = [root_pk]

    return render(
        request,
        "catalog/product_list.html",
        {
            "products": products,
            "root_categories": root_categories,
            "current_category": category,
            "open_accordion_ids": open_accordion_ids,
        },
    )


def _is_uuid(value):
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def product_detail(request, slug_or_pk):
    """Страница товара (по slug или uuid)."""
    qs = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("variants__images")
    )
    if _is_uuid(slug_or_pk):
        product = get_object_or_404(qs, pk=uuid.UUID(slug_or_pk))
    else:
        product = get_object_or_404(qs, slug=slug_or_pk)

    variants = list(
        product.variants.filter(is_active=True).order_by("order", "id")
    )
    selected_variant = variants[0] if variants else None

    # Выбор варианта из query-параметра (variant=<id>)
    variant_id = request.GET.get("variant")
    if variant_id and variants:
        try:
            vid = int(variant_id)
            for v in variants:
                if v.pk == vid:
                    selected_variant = v
                    break
        except (ValueError, TypeError):
            pass

    schema_image_url = None
    if selected_variant:
        main_img = selected_variant.get_main_image()
        if main_img and main_img.image:
            schema_image_url = request.build_absolute_uri(
                main_img.image.url
            )

    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "variants": variants,
            "selected_variant": selected_variant,
            "schema_image_url": schema_image_url,
        },
    )
