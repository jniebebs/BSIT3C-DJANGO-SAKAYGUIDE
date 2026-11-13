"""Small template helpers used by the management dashboard."""
from django import template
from django.http import QueryDict

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """Return the current query string with selected keys replaced.

    ``{% querystring page=2 %}`` keeps the active search/filter values and
    avoids duplicating the page parameter in pagination links.
    """
    request = context.get('request')
    query = request.GET.copy() if request is not None else QueryDict(
        mutable=True
    )
    for key, value in kwargs.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f'?{encoded}' if encoded else ''


@register.simple_tag(takes_context=True)
def page_query(context, number, param='page'):
    """Build a pagination URL with a configurable page parameter name."""
    request = context.get('request')
    query = request.GET.copy() if request is not None else QueryDict(
        mutable=True
    )
    query[param or 'page'] = number
    encoded = query.urlencode()
    return f'?{encoded}' if encoded else ''


@register.filter
def bar_percent(value, maximum):
    """Scale a count to 0-100 for the CSS search-activity bars."""
    try:
        value = float(value or 0)
        maximum = float(maximum or 0)
    except (TypeError, ValueError):
        return 0
    if maximum <= 0:
        return 0
    return max(3, min(100, round(value * 100 / maximum)))


@register.filter
def action_class(action_type):
    """Map an audit action to a Tabler badge colour."""
    return {
        'CREATE': 'bg-green-lt',
        'UPDATE': 'bg-blue-lt',
        'DELETE': 'bg-red-lt',
        'ACTIVATE': 'bg-teal-lt',
        'DEACTIVATE': 'bg-orange-lt',
        'LOGIN': 'bg-azure-lt',
        'LOGOUT': 'bg-secondary-lt',
    }.get((action_type or '').upper(), 'bg-secondary-lt')


@register.filter
def status_class(status):
    """Badge colour for an active/inactive/expired status value."""
    return {
        'active': 'bg-green-lt',
        'inactive': 'bg-secondary-lt',
        'expired': 'bg-orange-lt',
    }.get((status or '').lower(), 'bg-secondary-lt')


@register.filter
def role_class(role):
    """Badge colour for a dashboard role key.

    SakayGuide has two roles only: administrator and commuter.
    """
    return {
        'administrator': 'bg-blue-lt',
        'commuter': 'bg-teal-lt',
    }.get((role or '').lower(), 'bg-secondary-lt')
