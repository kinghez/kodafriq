from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import redirect
from functools import wraps


def staff_has_dashboard_perm(user, perm_codename):
    """
    Check if a user is a superuser or possesses the given dashboard permission.
    Non-staff users always evaluate to False.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not getattr(user, 'is_kodafriq_staff', False) and not user.is_staff:
        return False
    
    codename = perm_codename if perm_codename.startswith('dashboard.') else f"dashboard.{perm_codename}"
    return user.has_perm(codename)


class StaffDashboardPermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    CBV Mixin to restrict administrative dashboard pages.
    Superusers have unconditional access.
    Staff members require the explicitly assigned permission (e.g. 'dashboard.access_payments').
    """
    required_dashboard_perm = None
    permission_denied_message = "You do not have administrative permission to access this section. Please contact a superuser."

    def get_required_perm(self):
        if not self.required_dashboard_perm:
            return None
        perm = self.required_dashboard_perm
        return perm if perm.startswith('dashboard.') else f"dashboard.{perm}"

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if not getattr(user, 'is_kodafriq_staff', False) and not user.is_staff:
            return False
        required = self.get_required_perm()
        if not required:
            return True
        return user.has_perm(required)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, self.permission_denied_message)
        if getattr(self.request.user, 'is_kodafriq_staff', False):
            return redirect('dashboard:staff')
        return redirect('dashboard:index')


def staff_dashboard_permission_required(perm_name, message=None):
    """
    Decorator for function views requiring a specific dashboard permission.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if not getattr(request.user, 'is_kodafriq_staff', False) and not request.user.is_staff:
                messages.error(request, "Access restricted to platform administrative staff.")
                return redirect('dashboard:index')

            full_perm = perm_name if perm_name.startswith('dashboard.') else f"dashboard.{perm_name}"
            if not request.user.has_perm(full_perm):
                msg = message or "You do not have administrative permission to access this section."
                messages.error(request, msg)
                return redirect('dashboard:staff')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
