"""Read-mostly admin registration for the SakayGuide tables.

The schema is owned by the SQL scripts, so adding/deleting records from the
Django admin is disabled. Superusers may still inspect the data.
"""
from django.contrib import admin

from .models import (
    AdminActivityLog,
    Barangay,
    FareType,
    Location,
    Municipality,
    Route,
    RouteFare,
    RouteLandmark,
    RouteStop,
    RouteTransfer,
    SakayUser,
    SavedRoute,
    SearchHistory,
    TransportationType,
)


class SakayGuideReadOnlyAdmin(admin.ModelAdmin):
    """View-only: the SQL scripts own this schema, so nothing is editable."""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


admin.site.register(Municipality, SakayGuideReadOnlyAdmin)
admin.site.register(Barangay, SakayGuideReadOnlyAdmin)
admin.site.register(Location, SakayGuideReadOnlyAdmin)
admin.site.register(TransportationType, SakayGuideReadOnlyAdmin)
admin.site.register(FareType, SakayGuideReadOnlyAdmin)
admin.site.register(SakayUser, SakayGuideReadOnlyAdmin)
admin.site.register(Route, SakayGuideReadOnlyAdmin)
admin.site.register(RouteStop, SakayGuideReadOnlyAdmin)
admin.site.register(RouteFare, SakayGuideReadOnlyAdmin)
admin.site.register(RouteTransfer, SakayGuideReadOnlyAdmin)
admin.site.register(SavedRoute, SakayGuideReadOnlyAdmin)
admin.site.register(SearchHistory, SakayGuideReadOnlyAdmin)
admin.site.register(RouteLandmark, SakayGuideReadOnlyAdmin)
admin.site.register(AdminActivityLog, SakayGuideReadOnlyAdmin)
