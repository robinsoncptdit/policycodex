"""
URL configuration for policycodex_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'login/',
        LoginView.as_view(template_name='registration/login.html'),
        name='login',
    ),
    path(
        'logout/',
        LogoutView.as_view(next_page='/login/'),
        name='logout',
    ),
    path('', include('core.urls')),
]
