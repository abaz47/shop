"""
Теги шаблонов для работы с изображениями сайта.
"""
from django import template

from core.models import SiteImage

register = template.Library()


@register.simple_tag
def get_site_image(slug):
    """
    Получить изображение по slug.
    """
    try:
        return SiteImage.objects.get(slug=slug)
    except SiteImage.DoesNotExist:
        return None


@register.simple_tag
def get_site_images(category=None):
    """
    Получить список изображений, опционально отфильтрованных по категории.
    """
    queryset = SiteImage.objects.all()
    if category:
        queryset = queryset.filter(category=category)
    return queryset


@register.inclusion_tag('core/site_image.html', takes_context=False)
def site_image(slug, alt=None, css_class=None):
    """Вывести изображение по slug."""
    try:
        img = SiteImage.objects.get(slug=slug)
        return {
            'image': img,
            'alt': alt or img.name,
            'css_class': css_class,
        }
    except SiteImage.DoesNotExist:
        return {
            'image': None,
            'alt': alt or '',
            'css_class': css_class,
        }
