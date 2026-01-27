from django.contrib import admin
from django.urls import path, include
from dashboard.views import home, k8s, energy, networking

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("k8s", k8s, name="k8s"),
    path("energy/", energy, name="energy"),
    path("networking/", networking, name="networking"),
    path("accounts/", include("allauth.urls")),
    path('financial/', include('financial.urls')),
]
