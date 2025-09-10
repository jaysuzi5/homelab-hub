from django.conf import settings
from django.shortcuts import redirect

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow unauthenticated users to access login, signup, logout, and social login URLs
        exempt_urls = [
            settings.LOGIN_URL,
            "/accounts/signup/",
            "/accounts/logout/",
            "/admin/",
            "/accounts/google/login/", 
            "/accounts/google/login/callback/",
        ]

        if not request.user.is_authenticated and not any(request.path.startswith(url) for url in exempt_urls):
            return redirect(settings.LOGIN_URL)

        return self.get_response(request)
