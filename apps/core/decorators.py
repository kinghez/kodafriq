from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib.auth.mixins import AccessMixin
from django.contrib import messages

def candidate_required(view_func):
    """Decorator ensuring the authenticated user is a Healthcare Talent (Candidate)."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_talent:
            messages.error(request, "Access restricted to Healthcare Talent accounts.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def employer_required(view_func):
    """Decorator ensuring the authenticated user is a Healthcare Employer."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_employer:
            messages.error(request, "Access restricted to Healthcare Employer accounts.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_required(view_func):
    """Decorator ensuring the authenticated user is Kodafriq Staff or Admin."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_kodafriq_staff:
            messages.error(request, "Administrative privileges required.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


class CandidateRequiredMixin(AccessMixin):
    """CBV mixin verifying user has Candidate/Talent role."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_talent:
            messages.error(request, "Access restricted to Healthcare Talent accounts.")
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)


class EmployerRequiredMixin(AccessMixin):
    """CBV mixin verifying user has Employer role."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_employer:
            messages.error(request, "Access restricted to Healthcare Employer accounts.")
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(AccessMixin):
    """CBV mixin verifying user has Kodafriq Staff or Admin role."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_kodafriq_staff:
            messages.error(request, "Administrative privileges required.")
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)
