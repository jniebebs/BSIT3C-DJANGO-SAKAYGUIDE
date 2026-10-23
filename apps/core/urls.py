from django.urls import path

from apps.sakay import views as sakay_views
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('saved-routes/', sakay_views.saved_routes_page, name='saved_routes'),
    path(
        'sakay/save-route/',
        sakay_views.save_route_ajax,
        name='sakay_save_route',
    ),
    path(
        'sakay/unsave-route/<int:pk>/',
        sakay_views.unsave_route_ajax,
        name='sakay_unsave_route',
    ),
    path(
        'sakay/record-search/',
        sakay_views.record_search_ajax,
        name='sakay_record_search',
    ),
]