"""URL routes for the SakayGuide administrator dashboard.

All paths live below ``/management/`` and every view is protected by
``administrator_required``. Keep the URL names stable: navigation, redirects
and the test suite refer to them.
"""
from django.urls import path

from . import admin_views

urlpatterns = [
    # Overview
    path('', admin_views.dashboard, name='management_dashboard'),

    # Locations
    path('locations/', admin_views.location_list, name='management_locations'),
    path(
        'locations/add/', admin_views.location_create,
        name='management_location_create',
    ),
    path(
        'locations/<int:pk>/edit/', admin_views.location_edit,
        name='management_location_edit',
    ),
    path(
        'locations/<int:pk>/delete/', admin_views.location_delete,
        name='management_location_delete',
    ),
    path(
        'locations/<int:pk>/toggle/', admin_views.location_toggle,
        name='management_location_toggle',
    ),

    # Routes
    path('routes/', admin_views.route_list, name='management_routes'),
    path(
        'routes/add/', admin_views.route_create,
        name='management_route_create',
    ),
    path(
        'routes/<int:pk>/', admin_views.route_detail,
        name='management_route_detail',
    ),
    path(
        'routes/<int:pk>/edit/', admin_views.route_edit,
        name='management_route_edit',
    ),
    path(
        'routes/<int:pk>/delete/', admin_views.route_delete,
        name='management_route_delete',
    ),
    path(
        'routes/<int:pk>/toggle/', admin_views.route_toggle,
        name='management_route_toggle',
    ),

    # Stops (boarding / drop-off points)
    path('stops/', admin_views.stop_list, name='management_stops'),
    path('stops/add/', admin_views.stop_create, name='management_stop_create'),
    path(
        'stops/<int:pk>/edit/', admin_views.stop_edit,
        name='management_stop_edit',
    ),
    path(
        'stops/<int:pk>/delete/', admin_views.stop_delete,
        name='management_stop_delete',
    ),

    # Fares
    path('fares/', admin_views.fare_list, name='management_fares'),
    path('fares/add/', admin_views.fare_create, name='management_fare_create'),
    path(
        'fares/<int:pk>/edit/', admin_views.fare_edit,
        name='management_fare_edit',
    ),
    path(
        'fares/<int:pk>/delete/', admin_views.fare_delete,
        name='management_fare_delete',
    ),

    # Transfer connections
    path('transfers/', admin_views.transfer_list, name='management_transfers'),
    path(
        'transfers/add/', admin_views.transfer_create,
        name='management_transfer_create',
    ),
    path(
        'transfers/<int:pk>/edit/', admin_views.transfer_edit,
        name='management_transfer_edit',
    ),
    path(
        'transfers/<int:pk>/delete/', admin_views.transfer_delete,
        name='management_transfer_delete',
    ),

    # Transportation modes
    path(
        'transport-types/', admin_views.transport_type_list,
        name='management_transport_types',
    ),
    path(
        'transport-types/add/', admin_views.transport_type_form,
        name='management_transport_type_create',
    ),
    path(
        'transport-types/<int:pk>/edit/', admin_views.transport_type_form,
        name='management_transport_type_edit',
    ),
    path(
        'transport-types/<int:pk>/delete/', admin_views.transport_type_delete,
        name='management_transport_type_delete',
    ),

    # Fare categories
    path(
        'fare-types/', admin_views.fare_type_list,
        name='management_fare_types',
    ),
    path(
        'fare-types/add/', admin_views.fare_type_form,
        name='management_fare_type_create',
    ),
    path(
        'fare-types/<int:pk>/edit/', admin_views.fare_type_form,
        name='management_fare_type_edit',
    ),
    path(
        'fare-types/<int:pk>/delete/', admin_views.fare_type_delete,
        name='management_fare_type_delete',
    ),

    # Django user accounts
    path('users/', admin_views.user_list, name='management_users'),
    path('users/add/', admin_views.user_create, name='management_user_create'),
    path(
        'users/<int:pk>/edit/', admin_views.user_edit,
        name='management_user_edit',
    ),
    path(
        'users/<int:pk>/toggle/', admin_views.user_toggle,
        name='management_user_toggle',
    ),

    # Map management
    path('map/', admin_views.map_management, name='management_map'),

    # Monitoring
    path('activity/', admin_views.activity, name='management_activity'),
    path(
        'searches/',
        admin_views.search_monitoring,
        name='management_searches',
    ),

    # Reports
    path('reports/', admin_views.reports, name='management_reports'),
]
