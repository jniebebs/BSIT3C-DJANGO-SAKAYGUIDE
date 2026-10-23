from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

from .stats import (
    database_available,
    get_barangay_overview,
    get_mode_breakdown,
    get_recent_activity,
    get_summary_stats,
)


def _is_administrator(user):
    """Only administrators may open the admin dashboard."""
    return user.is_superuser


@login_required(login_url='login')
@user_passes_test(_is_administrator, login_url='dashboard')
def admin_dashboard(request):
    """Render the SakayGuide admin dashboard.

    All database access is read-only and every statistic degrades to an
    "unavailable" state when the configured database or a table is missing.
    """
    summary = get_summary_stats()
    context = {
        'page_title': 'Dashboard',
        'db_available': database_available(),
        'summary': summary,
        'summary_map': {card['key']: card for card in summary},
        'activity': get_recent_activity(),
        'mode_breakdown': get_mode_breakdown(),
        'barangay_overview': get_barangay_overview(),
    }
    return render(request, 'dashboard/dashboard.html', context)
