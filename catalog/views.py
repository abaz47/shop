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
        .prefetch_related("images")
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


def product_detail(request, pk):
    """Страница товара."""
    product = get_object_or_404(
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("images"),
        pk=pk,
    )
    return render(
        request,
        "catalog/product_detail.html",
        {"product": product}
    )
