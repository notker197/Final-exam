from django.contrib import admin
from django.urls import path
from planner import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('results/', views.results, name='results'),
    path('history/', views.history, name='history'),
]
