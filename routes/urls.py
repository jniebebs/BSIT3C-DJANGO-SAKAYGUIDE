from django.urls import path

from . import views

app_name = 'routes'

urlpatterns = [
    path('', views.route_search, name='route_search'),
    path('save/', views.save_route, name='save_route'),
]
