import json
from django.views import View
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db import models

from .models import NotificationBroadcast, BroadcastDeliveryLog
from .forms import BroadcastComposeForm
from .services import NotificationService

User = get_user_model()


class StaffOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Ensures only Kodafriq administrators and staff members can access broadcast tools."""
    def test_func(self):
        user = self.request.user
        return bool(user and user.is_authenticated and (
            getattr(user, 'is_kodafriq_staff', False) or user.is_staff or user.is_superuser
        ))

    def handle_no_permission(self):
        messages.error(self.request, "Access restricted to platform administrators.")
        return redirect('dashboard:index')


class AdminBroadcastCenterView(StaffOnlyMixin, View):
    template_name = 'notifications/admin_broadcast.html'

    def get_context_data(self, form=None):
        recent_broadcasts = NotificationBroadcast.objects.all().select_related('sender', 'target_group')[:20]
        groups = Group.objects.all().order_by('name')
        
        # Audience counts for quick badge hints
        stats = {
            'total_users': User.objects.filter(is_active=True, is_suspended=False).count(),
            'employers_count': User.objects.filter(role='EMPLOYER', is_active=True, is_suspended=False).count(),
            'candidates_count': User.objects.filter(role='CANDIDATE', is_active=True, is_suspended=False).count(),
            'admins_count': User.objects.filter(
                models.Q(role__in=['STAFF', 'ADMIN']) | models.Q(is_staff=True) | models.Q(is_superuser=True),
                is_active=True
            ).distinct().count(),
            'groups_count': groups.count(),
        }

        # Active users for the selector dropdown
        users_qs = User.objects.filter(is_active=True).order_by('username')

        return {
            'form': form or BroadcastComposeForm(),
            'recent_broadcasts': recent_broadcasts,
            'groups': groups,
            'stats': stats,
            'all_users': users_qs,
        }

    def get(self, request):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request):
        form = BroadcastComposeForm(request.POST)
        if form.is_valid():
            broadcast = form.save(commit=False)
            broadcast.sender = request.user
            broadcast.status = NotificationBroadcast.Status.DRAFT
            broadcast.save()

            # Handle specific user assignments
            target_type = broadcast.target_type
            if target_type == NotificationBroadcast.TargetType.SINGLE_USER:
                single_user = form.cleaned_data.get('target_single_user')
                if single_user:
                    broadcast.target_users.set([single_user])
            elif target_type == NotificationBroadcast.TargetType.MULTIPLE_USERS:
                multi_users = form.cleaned_data.get('target_multiple_users')
                if multi_users:
                    broadcast.target_users.set(multi_users)

            # Dispatch broadcast through NotificationService
            results = NotificationService.dispatch_broadcast(broadcast)

            messages.success(
                request,
                f"Broadcast '{broadcast.title}' sent successfully! Delivered to {results['success_count']} recipients "
                f"({results['failure_count']} failed/skipped)."
            )
            return redirect('notifications:admin_broadcast')

        # Form has errors
        messages.error(request, "Please review and correct the errors below.")
        return render(request, self.template_name, self.get_context_data(form=form))


class AdminBroadcastDetailView(StaffOnlyMixin, DetailView):
    model = NotificationBroadcast
    template_name = 'notifications/broadcast_detail.html'
    context_object_name = 'broadcast'
    pk_url_kwarg = 'pk'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        delivery_logs = self.object.delivery_logs.all().select_related('recipient')
        
        # Simple search/filter for deliveries
        status_filter = self.request.GET.get('status')
        if status_filter:
            delivery_logs = delivery_logs.filter(status=status_filter)

        paginator = Paginator(delivery_logs, 25)
        page_num = self.request.GET.get('page')
        context['page_obj'] = paginator.get_page(page_num)
        context['current_status_filter'] = status_filter
        return context


class AdminAudienceEstimateApiView(StaffOnlyMixin, View):
    """
    Returns live recipient estimate count and preview usernames for a given target_type.
    """
    def get(self, request):
        target_type = request.GET.get('target_type', 'ALL_USERS')
        group_id = request.GET.get('group_id')
        user_ids = request.GET.getlist('user_ids[]') or request.GET.getlist('user_ids')

        # Create temporary dummy broadcast to reuse resolution logic
        dummy = NotificationBroadcast(target_type=target_type)
        if group_id:
            dummy.target_group_id = group_id

        if target_type == NotificationBroadcast.TargetType.SINGLE_USER:
            single_id = request.GET.get('single_user_id')
            if single_id:
                count = User.objects.filter(id=single_id, is_active=True).count()
                return JsonResponse({'count': count, 'label': '1 specific recipient'})
            return JsonResponse({'count': 0, 'label': 'No user selected'})

        elif target_type == NotificationBroadcast.TargetType.MULTIPLE_USERS:
            count = len(user_ids)
            return JsonResponse({'count': count, 'label': f"{count} specific recipient(s)"})

        recipients = NotificationService.resolve_recipients(dummy)
        count = recipients.count()
        sample = list(recipients.values('username', 'email')[:4])

        return JsonResponse({
            'count': count,
            'label': f"{count} active recipient(s)",
            'sample': sample,
        })
