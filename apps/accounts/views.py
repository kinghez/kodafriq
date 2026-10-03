from django.contrib.auth import views as auth_views
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse_lazy
from apps.core.services.email_service import EmailService
from django.http import JsonResponse
from apps.core.utils.geo_device import get_client_ip, parse_device_info, resolve_ip_country
from apps.dashboard.models import log_staff_action, send_notification, Notification
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ip = get_client_ip(self.request)
        context['detected_geo'] = resolve_ip_country(ip, self.request)
        return context

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
        # Dispatch automated email verification & in-app notification
        EmailService.send_onboarding_email(user)
        EmailService.send_verification_email(user, request=self.request)
        send_notification(
            recipient=user,
            title="Welcome to Kodafriq",
            message="Welcome to Kodafriq! Complete your profile credentials and start discovering healthcare opportunities.",
            notification_type=Notification.NotificationType.SYSTEM,
            link="/dashboard/candidate/"
        )
        messages.success(self.request, f"Welcome to Kodafriq, {user.first_name or user.username}! A verification email has been sent to {user.email}.")
        return redirect('dashboard:candidate')


class EmployerRegistrationView(FormView):
    template_name = 'accounts/register_employer.html'
    form_class = EmployerRegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(get_role_redirect_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ip = get_client_ip(self.request)
        context['detected_geo'] = resolve_ip_country(ip, self.request)
        return context

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
        # Dispatch automated email verification & in-app notification
        EmailService.send_onboarding_email(user)
        EmailService.send_verification_email(user, request=self.request)
        send_notification(
            recipient=user,
            title="Welcome to Kodafriq",
            message="Welcome to the Kodafriq Healthcare Platform! Complete your company profile to start hiring top clinical talent.",
            notification_type=Notification.NotificationType.SYSTEM,
            link="/dashboard/employer/"
        )
        messages.success(self.request, f"Welcome to Kodafriq! A verification email has been sent to {user.email}.")
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


class GeoDetectionAPIView(View):
    """Dynamic API endpoint resolving real client IP geolocation."""
    def get(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        geo = resolve_ip_country(ip, request)
        return JsonResponse({
            'status': 'success',
            'ip': ip,
            'country': geo.get('country', 'Nigeria'),
            'country_code': geo.get('country_code', 'NG'),
            'city': geo.get('city', 'Lagos'),
            'calling_code': geo.get('calling_code', '234'),
        })


# ==============================================================================
# Email Verification & Password Reset Workflows
# ==============================================================================

class EmailVerificationView(View):
    def get(self, request, uidb64, token, *args, **kwargs):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])
            log_staff_action(user, "Email Address Verified", action_category='AUTH', target_user=user, details="User completed token verification.", request=request)
            send_notification(
                recipient=user,
                title="Email Verified",
                message="Your email address has been successfully verified.",
                notification_type=Notification.NotificationType.SECURITY,
                link="/dashboard/"
            )
            messages.success(request, "Your email address has been successfully verified!")
            return render(request, 'accounts/email_verified.html', {'success': True, 'user': user})
        else:
            return render(request, 'accounts/email_verified.html', {'success': False})


class ResendVerificationEmailView(View):
    def post(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None
        email = request.POST.get('email', '').strip()

        if user:
            if not user.is_email_verified:
                EmailService.send_verification_email(user, request=request)
                messages.success(request, f"A fresh verification email was dispatched to {user.email}.")
            else:
                messages.info(request, "Your email address is already verified.")
            return redirect('dashboard:index')

        if email:
            target_user = User.objects.filter(email__iexact=email, is_active=True).first()
            if target_user:
                if not target_user.is_email_verified:
                    EmailService.send_verification_email(target_user, request=request)
                messages.success(request, f"If an account exists with {email}, a fresh verification link has been dispatched.")
            else:
                messages.success(request, f"If an account exists with {email}, a fresh verification link has been dispatched.")
            return redirect('accounts:login')

        messages.warning(request, "Please provide an email address.")
        return redirect('accounts:login')


class KodafriqPasswordResetView(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'emails/password_reset_email.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        # We can also use EmailService directly for consistent branding
        email = form.cleaned_data.get('email')
        for user in form.get_users(email):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = self.request.build_absolute_uri(
                reverse_lazy('accounts:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            )
            EmailService.send_password_reset_email(user, reset_url)
        return redirect(self.success_url)


class KodafriqPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class KodafriqPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class KodafriqPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
