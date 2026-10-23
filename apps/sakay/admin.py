from django.contrib import admin

from .models import (
    Advisory,
    Route,
    RouteStop,
    SavedRoute,
    SearchHistory,
    Terminal,
    TransportMode,
)


@admin.register(TransportMode)
class TransportModeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'color', 'avg_speed_kmh')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1
    ordering = ('sequence',)
    fields = ('sequence', 'terminal', 'distance_from_origin_km',
              'cumulative_fare', 'cumulative_time_minutes')
    readonly_fields = ('cumulative_fare', 'cumulative_time_minutes')


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'transport_mode', 'origin_terminal',
                    'destination_terminal', 'base_fare', 'fare_per_km', 'is_active')
    list_filter = ('is_active', 'transport_mode')
    search_fields = ('code', 'name')
    inlines = [RouteStopInline]


@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ('name', 'municipality', 'province', 'landmark', 'latitude', 'longitude')
    list_filter = ('municipality', 'transport_modes')
    search_fields = ('name', 'municipality', 'landmark')
    filter_horizontal = ('transport_modes',)


@admin.register(Advisory)
class AdvisoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'severity', 'status', 'terminal',
                    'reported_by', 'upvotes', 'created_at')
    list_filter = ('status', 'severity', 'category')
    search_fields = ('title', 'message', 'reported_by')
    filter_horizontal = ('routes',)


@admin.register(SavedRoute)
class SavedRouteAdmin(admin.ModelAdmin):
    list_display = ('user', 'origin_terminal', 'destination_terminal', 'name', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'origin_terminal__name', 'destination_terminal__name', 'name')
    raw_id_fields = ('user', 'origin_terminal', 'destination_terminal')


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'origin_terminal', 'destination_terminal', 'searched_at')
    list_filter = ('searched_at',)
    search_fields = ('user__username', 'origin_terminal__name', 'destination_terminal__name')
    raw_id_fields = ('user', 'origin_terminal', 'destination_terminal')
    date_hierarchy = 'searched_at'
