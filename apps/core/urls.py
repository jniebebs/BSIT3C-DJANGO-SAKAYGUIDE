from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home, name='dashboard'),
    path('home/activity/', views.activity, name='dashboard_activity'),
    path('home/routes/', views.active_routes, name='dashboard_routes'),
    path('home/locations/', views.active_locations, name='dashboard_locations'),
    path('home/transfers/', views.transfer_links, name='dashboard_transfers'),
    path('home/commuters/', views.commuters, name='dashboard_commuters'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
]