from django.contrib import admin
from django.urls import path, include
from dashboard.views import home, k8s

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("k8s", k8s, name="k8s"),
    path("accounts/", include("allauth.urls")),  
    path('financial/', include('financial.urls')), 
]
