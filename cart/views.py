"""
Представления корзины.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from catalog.models import Product

from .models import CartItem
from .utils import get_or_create_cart


def cart_detail(request):
    """Страница корзины."""
    cart = get_or_create_cart(request)
    items = (
        cart.items.select_related("product")
        .prefetch_related("product__images")
        .order_by("id")
    )
    return render(
        request,
        "cart/detail.html",
        {"cart": cart, "items": items},
    )


@require_POST
def cart_add(request, product_id):
    """Добавить товар в корзину (POST)."""
    product = get_object_or_404(
        Product.objects.filter(is_active=True),
        pk=product_id
    )
    cart = get_or_create_cart(request)
    quantity = int(request.POST.get("quantity", 1))
    if quantity < 1:
        quantity = 1

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": quantity},
    )
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity"])

    messages.success(request, f"Товар «{product.name}» добавлен в корзину.")
    redirect_url = request.POST.get(
        "next"
    ) or request.GET.get(
        "next"
    ) or reverse(
        "catalog:product_detail", kwargs={"pk": product.pk}
    )
    return redirect(redirect_url)


@require_POST
def cart_update(request, product_id):
    """Изменить количество товара в корзине (POST)."""
    cart = get_or_create_cart(request)
    item = get_object_or_404(
        CartItem.objects.filter(cart=cart, product_id=product_id)
    )
    quantity = int(request.POST.get("quantity", 1))
    if quantity < 1:
        item.delete()
        messages.success(request, "Позиция удалена из корзины.")
    else:
        item.quantity = quantity
        item.save(update_fields=["quantity"])
        messages.success(request, "Количество обновлено.")
    return redirect("cart:detail")


@require_POST
def cart_remove(request, product_id):
    """Удалить позицию из корзины (POST)."""
    cart = get_or_create_cart(request)
    item = get_object_or_404(
        CartItem.objects.filter(cart=cart, product_id=product_id)
    )
    item.delete()
    messages.success(request, "Позиция удалена из корзины.")
    return redirect("cart:detail")
