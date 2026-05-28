from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})

@register.filter(name='get_item')
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key) or dictionary.get(str(key)) or dictionary.get(int(key) if str(key).lstrip('-').isdigit() else key)
    return None
