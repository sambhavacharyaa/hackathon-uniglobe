from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Look up `key` in a dict from a template, e.g. {{ my_dict|get_item:key }}.

    Tries the key as given, then as a string — JSONField round-trips dict
    keys through JSON, which always turns int keys into strings.
    """
    if mapping is None:
        return None
    if key in mapping:
        return mapping[key]
    return mapping.get(str(key))
