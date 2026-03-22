"""
Представления корзины.
"""
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from catalog.models import ProductVariant

from .models import CartItem
from .utils import get_or_create_cart

MAX_QUANTITY_PER_ITEM = 10


@require_http_methods(["GET", "POST"])
def cart_detail(request):
    """
    Единая страница корзины и оформления заказа (/cart).
    Для гостей: корзина и приглашение войти/зарегистрироваться.
    Для авторизованных с непустой корзиной: корзина и форма оформления.
    Неактивные товары удаляются из корзины; их названия передаются в шаблон
    для показа модального окна.
    """
    cart = get_or_create_cart(request)
    items = list(
        cart.items.select_related("variant__product")
        .prefetch_related("variant__images")
        .order_by("id")
    )

    removed_product_names = []
    inactive_items = [
        it for it in items if not it.variant.is_active
        or not it.variant.product.is_active
    ]
    if inactive_items:
        for it in inactive_items:
            removed_product_names.append(it.variant.product.name)
            it.delete()
        items = list(
            cart.items.select_related("variant__product")
            .prefetch_related("variant__images")
            .order_by("id")
        )

    checkout_context = None
    if request.user.is_authenticated and items:
        from orders.views import _get_checkout_context

        redirect_response, checkout_context = _get_checkout_context(
            request, cart, items, cart.total_price
        )
        if redirect_response is not None:
            return redirect_response

    return render(
        request,
        "cart/detail.html",
        {
            "cart": cart,
            "items": items,
            "checkout_context": checkout_context,
            "removed_product_names": removed_product_names,
        },
    )


@require_POST
def cart_add(request, variant_id):
    """Добавить вариант товара в корзину (POST)."""
    variant = get_object_or_404(
        ProductVariant.objects.filter(
            is_active=True,
            product__is_active=True,
        ).select_related("product"),
        pk=variant_id,
    )
    cart = get_or_create_cart(request)
    quantity = int(request.POST.get("quantity", 1))
    if quantity < 1:
        quantity = 1
    quantity = min(quantity, MAX_QUANTITY_PER_ITEM)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={"quantity": quantity},
    )
    if not created:
        item.quantity = min(
            item.quantity + quantity,
            MAX_QUANTITY_PER_ITEM,
        )
        item.save(update_fields=["quantity"])

    redirect_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or variant.product.get_absolute_url()
    )
    return redirect(redirect_url)


@require_POST
def cart_update(request, variant_id):
    """Изменить количество товара в корзине (POST)."""
    cart = get_or_create_cart(request)
    item = get_object_or_404(
        CartItem.objects.filter(cart=cart, variant_id=variant_id)
    )
    quantity = int(request.POST.get("quantity", 1))
    if quantity < 1:
        item.delete()
    else:
        item.quantity = min(quantity, MAX_QUANTITY_PER_ITEM)
        item.save(update_fields=["quantity"])
    return redirect("cart:detail")


@require_POST
def cart_remove(request, variant_id):
    """Удалить позицию из корзины (POST)."""
    cart = get_or_create_cart(request)
    item = get_object_or_404(
        CartItem.objects.filter(cart=cart, variant_id=variant_id)
    )
    item.delete()
    return redirect("cart:detail")


@require_POST
def cart_clear(request):
    """Очистить корзину (POST)."""
    cart = get_or_create_cart(request)
    cart.items.all().delete()
    return redirect("cart:detail")
