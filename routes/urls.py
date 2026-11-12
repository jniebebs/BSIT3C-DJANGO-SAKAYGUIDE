from django.urls import path

from . import views

app_name = 'routes'

urlpatterns = [
    path('', views.route_search, name='route_search'),
    path('save/', views.save_route, name='save_route'),
    path('map-data/', views.journey_map_json, name='journey_map_json'),
    path(
        'destinations/', views.destination_summaries_json,
        name='destination_summaries',
    ),
]
