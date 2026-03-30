from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.BuildingListView.as_view(), name='building_list'),
    path('create/', views.BuildingCreateView.as_view(), name='building_create'),
    # Safety guard: redirect bogus IDs like "None" or "null" back to list instead of erroring
    path('update/None/', views.redirect_building_list, name='building_update_none'),
    path('update/null/', views.redirect_building_list),
    path('update/<str:pk>/', views.BuildingUpdateView.as_view(), name='building_update'),
    path('delete/None/', views.redirect_building_list),
    path('delete/null/', views.redirect_building_list),
    path('delete/<str:pk>/', views.BuildingDeleteView.as_view(), name='building_delete'),
]
