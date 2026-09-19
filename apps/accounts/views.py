from apps.core.utils.geo_device import get_client_ip, parse_device_info, resolve_ip_country
from apps.dashboard.models import log_staff_action
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView, FormView
from django.contrib.auth import login, logout
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import KodafriqLoginForm, TalentRegistrationForm, EmployerRegistrationForm
from .models import User

def get_role_redirect_url(user):
    """Determine dashboard destination based on user role."""
    if user.is_kodafriq_staff:
        return reverse('dashboard:staff')
    elif user.is_employer:
        return reverse('dashboard:employer')
    else:
        return reverse('dashboard:candidate')


class RoleSelectionView(TemplateView):
    template_name = 'accounts/role_select.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))
        return super().dispatch(request, *args, **kwargs)


class TalentRegistrationView(FormView):
    template_name = 'accounts/register_talent.html'
    form_class = TalentRegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        ip = get_client_ip(self.request)
        geo = resolve_ip_country(ip, self.request)
        device_info = parse_device_info(self.request.META.get('HTTP_USER_AGENT', ''))
        initial['country'] = geo['country']
        initial['detected_country'] = geo['country']
        initial['detected_device'] = device_info['summary']
        return initial

    def form_valid(self, form):
        user = form.save()
        ip = get_client_ip(self.request)
        user.registration_ip = ip
        user.last_login_ip = ip
        user.save(update_fields=['registration_ip', 'last_login_ip'])
        
        # Log registration audit
        log_staff_action(user, 'Candidate Account Registered', action_category='AUTH', target_user=user, request=self.request)

        login(self.request, user)
        messages.success(self.request, f"Welcome to Kodafriq, {user.first_name or user.username}! Your talent profile has been initialized.")
        return redirect('dashboard:candidate')


class EmployerRegistrationView(FormView):
    template_name = 'accounts/register_employer.html'
    form_class = EmployerRegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        ip = get_client_ip(self.request)
        geo = resolve_ip_country(ip, self.request)
        device_info = parse_device_info(self.request.META.get('HTTP_USER_AGENT', ''))
        initial['country'] = geo['country']
        initial['detected_country'] = geo['country']
        initial['detected_device'] = device_info['summary']
        return initial

    def form_valid(self, form):
        user = form.save()
        ip = get_client_ip(self.request)
        user.registration_ip = ip
        user.last_login_ip = ip
        user.save(update_fields=['registration_ip', 'last_login_ip'])

        # Log registration audit
        log_staff_action(user, 'Employer Account Registered', action_category='AUTH', target_user=user, request=self.request)

        login(self.request, user)
        messages.success(self.request, f"Welcome to Kodafriq! Your organization profile for {form.cleaned_data.get('company_name')} is registered.")
        return redirect('dashboard:employer')


class KodafriqLoginView(FormView):
    template_name = 'accounts/login.html'
    form_class = KodafriqLoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        ip = get_client_ip(self.request)
        device_info = parse_device_info(self.request.META.get('HTTP_USER_AGENT', ''))
        user.last_login_ip = ip
        user.detected_device = device_info['summary']
        user.save(update_fields=['last_login_ip', 'detected_device'])

        # Audit log login
        log_staff_action(user, 'User Login Success', action_category='AUTH', target_user=user, request=self.request)

        login(self.request, user)

        # Handle remember me session duration
        if not form.cleaned_data.get('remember_me'):
            self.request.session.set_expiry(0) # Session expires on browser close
        else:
            self.request.session.set_expiry(1209600) # 2 weeks

        messages.success(self.request, f"Welcome back, {user.get_full_name() or user.username}!")

        # Check next URL if safe
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return redirect(next_url)

        return redirect(get_role_redirect_url(user))


class KodafriqLogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.info(request, "You have been successfully signed out.")
        return redirect('/')

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


class SuspendedAccountView(TemplateView):
    template_name = 'accounts/suspended.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reason'] = self.request.session.get(
            'suspension_reason',
            'Your account has been placed under administrative suspension for policy or security review.'
        )
        return context
