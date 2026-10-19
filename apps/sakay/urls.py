from django.urls import path

from . import views

app_name = 'sakay'

urlpatterns = [
    path('csrf/', views.csrf_token_view, name='csrf_token'),
    path('terminals/search/', views.terminal_search, name='terminal_search'),
    path('terminals/<int:pk>/', views.terminal_detail, name='terminal_detail'),
    path('terminals/<int:pk>/routes/', views.terminal_routes, name='terminal_routes'),
    path('routes/', views.route_list, name='route_list'),
    path('routes/<int:pk>/', views.route_detail, name='route_detail'),
    path('routes/<int:pk>/fare-matrix/', views.route_fare_matrix, name='route_fare_matrix'),
    path('route-plan/', views.route_plan, name='route_plan'),
    path('advisories/', views.advisory_list, name='advisory_list'),
    path('advisories/create/', views.advisory_create, name='advisory_create'),
    path('advisories/<int:pk>/upvote/', views.advisory_upvote, name='advisory_upvote'),
    path('advisories/<int:pk>/resolve/', views.advisory_resolve, name='advisory_resolve'),
]
