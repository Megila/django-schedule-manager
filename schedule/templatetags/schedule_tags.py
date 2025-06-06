from django import template

register = template.Library()

@register.filter
def to(value, end):
    """Возвращает range от value до end (не включая end)"""
    return range(value, end)

@register.filter
def dict_get(dictionary, key):
    """Получение значения из словаря по ключу"""
    try:
        return dictionary[key]
    except KeyError:
        return None  # или можно вернуть значение по умолчанию