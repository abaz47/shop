"""
Представления заказов: оформление заказа и список заказов.
"""
import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from cart.utils import get_or_create_cart
from cdek.services import (
    calculate_delivery,
    calculate_tarifflist,
    cart_items_to_packages,
    delivery_sum_to_decimal,
    search_cities,
)

from .forms import CheckoutForm
from .models import Order, OrderItem
from .services import create_cdek_order


def _parse_tariffs_request_payload(request):
    """
    Разбирает JSON body запроса checkout_tariffs.
    Возвращает (mode, point_type, to_city_code, city_name)
    или (None, None, None, "") при ошибке.
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None, None, None, ""
    mode = (payload.get("mode") or "").strip()
    point_type = (payload.get("point_type") or "").strip().upper()
    to_city_code = payload.get("city_code")
    city_name = (payload.get("city") or "").strip()
    try:
        to_city_code = int(to_city_code)
    except (TypeError, ValueError):
        to_city_code = None
    return mode, point_type, to_city_code, city_name


def _is_allowed_tariff_family(name: str) -> bool:
    """Только тарифы «Посылка» (включая экономичную) и «Экспресс»."""
    n = (name or "").lower().strip()
    return (
        n.startswith("посылка ")
        or n == "посылка"
        or n.startswith("экономичная посылка ")
        or n.startswith("экспресс ")
    )


def _tariff_kind_by_name(name: str) -> str | None:
    """
    Классификация тарифа по названию: только отправка из ПВЗ
    (склад → склад/постамат/дверь). Возвращает office|pickup|door|None.
    """
    title = (name or "").lower().replace(" ", " ").strip()
    normalized = title.replace(" - ", "-").replace(" – ", "-")
    if not normalized:
        return None
    if "дверь-дверь" in normalized or "дверь дверь" in normalized:
        return None
    if "дверь-склад" in normalized or "дверь склад" in normalized:
        return None
    if "дверь-постамат" in normalized or "дверь постамат" in normalized:
        return None
    if "склад-склад" in normalized or "склад - склад" in title:
        return "office"
    has_postamat = "склад-постамат" in normalized or (
        "постамат" in normalized and "склад" in normalized
    )
    if has_postamat:
        return "pickup"
    if (
        "склад-двер" in normalized
        or "до двери" in normalized
        or "курьер" in normalized
    ):
        return "door"
    return None


def _filter_tariffs_for_response(raw_tariffs, mode: str, point_type: str):
    """Фильтрует и сортирует тарифы по mode и point_type."""
    allowed = {"office", "pickup"}
    if mode == "office":
        allowed = {"pickup"} if point_type == "POSTAMAT" else {"office"}

    filtered = []
    for t in raw_tariffs:
        name_str = str(t.get("tariff_name") or "")
        if not _is_allowed_tariff_family(name_str):
            continue
        kind = _tariff_kind_by_name(name_str)
        if not kind:
            continue
        if mode == "office" and kind not in allowed:
            continue
        if mode == "door" and kind != "door":
            continue
        filtered.append({
            "tariff_code": t.get("tariff_code"),
            "tariff_name": t.get("tariff_name"),
            "tariff_description": t.get("tariff_description"),
            "delivery_mode": t.get("delivery_mode"),
            "period_min": t.get("period_min"),
            "period_max": t.get("period_max"),
            "delivery_sum": t.get("delivery_sum"),
        })

    filtered.sort(key=lambda x: (x.get("delivery_sum") or 0))
    return filtered


def _process_place_order(request, form, cart, items, products_total):
    """
    Обрабатывает действие «Оформить заказ». Возвращает redirect при успехе
    или None (тогда вызывающий продолжит рендер формы).
    """
    tariff_code = form.cleaned_data["delivery_tariff"]
    to_city_code = form.cleaned_data["city_code"]
    from_city_code = getattr(settings, "CDEK_FROM_CITY_CODE", 137)

    packages = cart_items_to_packages(cart.items.select_related("product"))
    result = calculate_delivery(
        from_city_code=from_city_code,
        to_city_code=to_city_code,
        packages=packages,
        tariff_code=tariff_code,
    )
    if not result:
        messages.error(
            request,
            "Не удалось подтвердить стоимость доставки при "
            "оформлении заказа. Попробуйте ещё раз.",
        )
        return None

    delivery_cost = delivery_sum_to_decimal(result)
    delivery_type = (
        Order.DeliveryType.COURIER
        if form.cleaned_data.get("delivery_mode") == "door"
        else Order.DeliveryType.PICKUP
    )

    order = Order.objects.create(
        user=request.user,
        status=Order.Status.NEW,
        delivery_method=Order.DeliveryMethod.CDEK,
        delivery_type=delivery_type,
        delivery_tariff_code=tariff_code,
        products_total=products_total,
        delivery_cost=delivery_cost,
        total=products_total + delivery_cost,
        recipient_name=form.cleaned_data["recipient_name"],
        recipient_phone=form.cleaned_data["recipient_phone"],
        recipient_email=form.cleaned_data.get("recipient_email") or "",
        city_code=to_city_code,
        delivery_address=form.cleaned_data.get("delivery_address") or "",
        pvz_code=form.cleaned_data.get("pvz_code") or "",
        comment=form.cleaned_data.get("comment") or "",
    )
    for item in items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            price=item.product.discounted_price,
            quantity=item.quantity,
        )
    cart.items.all().delete()

    cdek_uuid = create_cdek_order(order)
    if cdek_uuid:
        order.cdek_order_uuid = cdek_uuid
        order.save(update_fields=["cdek_order_uuid"])
        messages.success(
            request,
            f"Заказ #{order.pk} оформлен и зарегистрирован в СДЭК. "
            f"Итого: {order.total:.0f} ₽.",
        )
    else:
        messages.warning(
            request,
            f"Заказ #{order.pk} сохранён, но не удалось зарегистрировать "
            f"его в СДЭК автоматически. Пожалуйста, свяжитесь с нами — "
            f"мы оформим доставку вручную. Итого: {order.total:.0f} ₽.",
        )
    return redirect("orders:success", order_id=order.pk)


def _get_checkout_context(request, cart, items, products_total):
    """
    Обрабатывает форму оформления заказа (GET/POST).
    Возвращает (redirect_response, context_dict).
    Если redirect_response не None — редирект после успешного place_order.
    Иначе context_dict содержит form, delivery_cost, total, cdek_service_url...
    """
    delivery_cost = None
    delivery_period_min = None
    delivery_period_max = None
    form = CheckoutForm(request.POST or None, user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "calculate")

        if form.is_valid():
            tariff_code = form.cleaned_data["delivery_tariff"]
            to_city_code = form.cleaned_data["city_code"]
            from_city_code = getattr(settings, "CDEK_FROM_CITY_CODE", 137)

            if action == "calculate":
                packages = cart_items_to_packages(
                    cart.items.select_related("product")
                )
                result = calculate_delivery(
                    from_city_code=from_city_code,
                    to_city_code=to_city_code,
                    packages=packages,
                    tariff_code=tariff_code,
                )
                if result:
                    delivery_cost = delivery_sum_to_decimal(result)
                    delivery_period_min = result.get("period_min")
                    delivery_period_max = result.get("period_max")
                else:
                    messages.warning(
                        request,
                        "Не удалось рассчитать доставку. "
                        "Проверьте город или попробуйте позже.",
                    )
            elif action == "place_order":
                redirect_response = _process_place_order(
                    request, form, cart, items, products_total
                )
                if redirect_response is not None:
                    return redirect_response, None
        else:
            if action == "place_order":
                messages.error(
                    request,
                    "Исправьте ошибки в форме и нажмите "
                    "«Оформить заказ» снова.",
                )

    total = products_total + (delivery_cost or Decimal("0"))
    cdek_service_url = request.build_absolute_uri("/service.php")
    yandex_key = getattr(settings, "YANDEX_MAPS_API_KEY", "") or ""
    context = {
        "form": form,
        "products_total": products_total,
        "delivery_cost": delivery_cost,
        "delivery_period_min": delivery_period_min,
        "delivery_period_max": delivery_period_max,
        "total": total,
        "cdek_service_url": cdek_service_url,
        "yandex_maps_api_key": yandex_key,
    }
    return None, context


@require_http_methods(["GET", "POST"])
def checkout_view(request):
    """
    Редирект на единую страницу корзины/оформления.
    Оставлен для обратной совместимости ссылок.
    """
    if not request.user.is_authenticated:
        return redirect("cart:detail")
    cart = get_or_create_cart(request)
    if not cart.items.exists():
        messages.info(
            request,
            "Корзина пуста. Добавьте товары для оформления заказа.",
        )
        return redirect("cart:detail")
    return redirect("cart:detail")


@login_required
def checkout_success(request, order_id):
    """Страница успешного оформления заказа."""
    order = Order.objects.filter(
        user=request.user,
        pk=order_id,
    ).first()
    if not order:
        messages.warning(request, "Заказ не найден.")
        return redirect("orders:list")
    return render(
        request,
        "orders/checkout_success.html",
        {"order": order},
    )


@require_GET
def checkout_cities(request):
    """API: список городов СДЭК для автодополнения (GET ?q=...)."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"cities": []})
    cities = search_cities(q, limit=30)
    return JsonResponse({"cities": cities})


@login_required
@require_http_methods(["POST"])
def checkout_tariffs(request):
    """
    API: список тарифов СДЭК по выбранному адресу / ПВЗ.

    Принимает JSON: mode (office|door), city_code, city, point_type.
    Возвращает JSON: {"tariffs": [...]}.
    """
    cart = get_or_create_cart(request)
    items = cart.items.select_related("product")
    if not items.exists():
        return JsonResponse({"tariffs": []})

    mode, point_type, to_city_code, city_name = _parse_tariffs_request_payload(
        request
    )
    if mode is None:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)
    if mode not in {"office", "door"}:
        return JsonResponse({"tariffs": []})

    if not to_city_code and city_name:
        matches = search_cities(city_name, limit=1)
        if matches:
            to_city_code = matches[0].get("code")
    if not to_city_code:
        return JsonResponse({"tariffs": []})

    from_city_code = getattr(settings, "CDEK_FROM_CITY_CODE", 137)
    packages = cart_items_to_packages(items)
    raw_tariffs = calculate_tarifflist(
        from_city_code=from_city_code,
        to_city_code=to_city_code,
        packages=packages,
    )
    filtered = _filter_tariffs_for_response(raw_tariffs, mode, point_type)
    response_data = {"tariffs": filtered}
    if to_city_code is not None:
        response_data["city_code"] = to_city_code
    return JsonResponse(response_data)


@login_required
def order_list(request):
    """Список заказов пользователя."""
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(
        request,
        "orders/order_list.html",
        {"orders": orders},
    )
