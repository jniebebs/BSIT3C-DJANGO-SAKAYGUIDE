"""URL routes for the SakayGuide account portals.

SakayGuide has two separate sign-in experiences:

``/admin/login/``
    Administrator portal. Staff accounts only.

``/commuter/login/`` and ``/commuter/register/``
    Commuter portal. Ordinary accounts only; self-registration always
    creates a commuter.

``/`` stays a shared entry point that routes each role to its own dashboard.
"""
from django.urls import include, path

from . import commuter_views, password_views, views

urlpatterns = [
    # Shared entry point (routes each role to its own dashboard)
    path('', views.login_view, name='login'),

    # Administrator portal. The path deliberately avoids /admin/, which is
    # owned by the Django administration site.
    path(
        'administrator/login/',
        views.admin_login_view,
        name='admin_login',
    ),
    path(
        'administrator/password-reset/',
        password_views.AdminPasswordResetView.as_view(),
        name='admin_password_reset',
    ),
    path(
        'administrator/password-reset/done/',
        password_views.AdminPasswordResetDoneView.as_view(),
        name='admin_password_reset_done',
    ),
    path(
        'administrator/password-reset/complete/',
        password_views.AdminPasswordResetCompleteView.as_view(),
        name='admin_password_reset_complete',
    ),
    path(
        'administrator/password-reset/<uidb64>/<token>/',
        password_views.AdminPasswordResetConfirmView.as_view(),
        name='admin_password_reset_confirm',
    ),

    # Commuter portal
    path(
        'commuter/login/',
        views.commuter_login_view,
        name='commuter_login',
    ),
    path(
        'commuter/register/',
        views.register_view,
        name='commuter_register',
    ),
    path(
        'commuter/password-reset/',
        password_views.CommuterPasswordResetView.as_view(),
        name='commuter_password_reset',
    ),
    path(
        'commuter/password-reset/done/',
        password_views.CommuterPasswordResetDoneView.as_view(),
        name='commuter_password_reset_done',
    ),
    path(
        'commuter/password-reset/complete/',
        password_views.CommuterPasswordResetCompleteView.as_view(),
        name='commuter_password_reset_complete',
    ),
    path(
        'commuter/password-reset/<uidb64>/<token>/',
        password_views.CommuterPasswordResetConfirmView.as_view(),
        name='commuter_password_reset_confirm',
    ),

    # Commuter dashboard and account area
    path(
        'commuter/',
        commuter_views.dashboard,
        name='commuter_dashboard',
    ),
    path(
        'commuter/searches/',
        commuter_views.recent_searches,
        name='commuter_recent_searches',
    ),
    path(
        'commuter/profile/',
        commuter_views.profile,
        name='commuter_profile',
    ),
    path(
        'commuter/password/',
        commuter_views.password_change,
        name='commuter_password_change',
    ),

    # Administrator monitoring console
    path('home/', views.home, name='dashboard'),
    path('home/activity/', views.activity, name='dashboard_activity'),
    path('home/routes/', views.active_routes, name='dashboard_routes'),
    path('home/locations/', views.active_locations, name='dashboard_locations'),
    path('home/transfers/', views.transfer_links, name='dashboard_transfers'),
    path('home/commuters/', views.commuters, name='dashboard_commuters'),

    # Session
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # Administrator management console
    path('management/', include('apps.core.management_urls')),
]
