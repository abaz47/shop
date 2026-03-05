"""
Представления корзины.
"""
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from catalog.models import Product

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
        cart.items.select_related("product")
        .prefetch_related("product__images")
        .order_by("id")
    )

    removed_product_names = []
    inactive_items = [it for it in items if not it.product.is_active]
    if inactive_items:
        for it in inactive_items:
            removed_product_names.append(it.product.name)
            it.delete()
        items = list(
            cart.items.select_related("product")
            .prefetch_related("product__images")
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
def cart_add(request, product_id):
    """Добавить товар в корзину (POST)."""
    product = get_object_or_404(
        Product.objects.filter(is_active=True), pk=product_id
    )
    cart = get_or_create_cart(request)
    quantity = int(request.POST.get("quantity", 1))
    if quantity < 1:
        quantity = 1
    quantity = min(quantity, MAX_QUANTITY_PER_ITEM)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": quantity},
    )
    if not created:
        item.quantity = min(
            item.quantity + quantity,
            MAX_QUANTITY_PER_ITEM,
        )
        item.save(update_fields=["quantity"])

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
    else:
        item.quantity = min(quantity, MAX_QUANTITY_PER_ITEM)
        item.save(update_fields=["quantity"])
    return redirect("cart:detail")


@require_POST
def cart_remove(request, product_id):
    """Удалить позицию из корзины (POST)."""
    cart = get_or_create_cart(request)
    item = get_object_or_404(
        CartItem.objects.filter(cart=cart, product_id=product_id)
    )
    item.delete()
    return redirect("cart:detail")


@require_POST
def cart_clear(request):
    """Очистить корзину (POST)."""
    cart = get_or_create_cart(request)
    cart.items.all().delete()
    return redirect("cart:detail")
