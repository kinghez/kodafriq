from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q

from apps.accounts.models import User, CandidateProfile, EmployerProfile
from apps.employers.models import Job
from apps.dashboard.models import Conversation, DirectMessage, Notification, send_notification, log_staff_action, AuditLog


class ConversationInboxView(LoginRequiredMixin, View):
    """
    Unified messaging inbox for both Employers and Healthcare Candidates.
    Employers see their candidate discussions; candidates see threads initiated by employers.
    """
    template_name = 'dashboard/messages.html'

    def get(self, request, pk=None, *args, **kwargs):
        user = request.user
        is_employer = (user.role == User.Role.EMPLOYER) or (user.is_kodafriq_staff)
        is_candidate = (user.role == User.Role.CANDIDATE) and not is_employer

        if is_employer:
            employer_profile = getattr(user, 'employer_profile', None)
            if not employer_profile:
                employer_profile, _ = EmployerProfile.objects.get_or_create(
                    user=user,
                    defaults={'company_name': f"{user.get_full_name() or user.username} Healthcare"}
                )
            threads = Conversation.objects.filter(employer=employer_profile).select_related(
                'candidate', 'candidate__user', 'job'
            ).prefetch_related('messages')
        elif is_candidate:
            candidate_profile = getattr(user, 'candidate_profile', None)
            if not candidate_profile:
                messages.warning(request, "Please complete your clinical profile to access direct messages.")
                return redirect('dashboard:candidate_profile_edit')
            threads = Conversation.objects.filter(candidate=candidate_profile).select_related(
                'employer', 'employer__user', 'job'
            ).prefetch_related('messages')
        else:
            threads = Conversation.objects.none()

        # Search query in threads
        q = request.GET.get('q', '').strip()
        if q:
            threads = threads.filter(
                Q(subject__icontains=q) |
                Q(candidate__user__first_name__icontains=q) |
                Q(candidate__user__last_name__icontains=q) |
                Q(employer__company_name__icontains=q) |
                Q(messages__body__icontains=q)
            ).distinct()

        # Selected conversation thread
        active_thread = None
        if pk:
            active_thread = threads.filter(pk=pk).first()
        elif threads.exists():
            active_thread = threads.first()

        # If active thread exists, mark incoming messages as read
        if active_thread:
            active_thread.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)

        context = {
            'threads': threads,
            'active_thread': active_thread,
            'is_employer': is_employer,
            'is_candidate': is_candidate,
            'search_q': q,
        }
        return render(request, self.template_name, context)


class StartConversationView(LoginRequiredMixin, View):
    """
    CRITICAL POLICY: Strictly restricted to Employers (or Staff).
    Candidates can NEVER initiate an unsolicited message thread with an employer.
    """
    def post(self, request, candidate_id, *args, **kwargs):
        user = request.user
        is_employer = (user.role == User.Role.EMPLOYER) or (user.is_kodafriq_staff)
        
        if not is_employer:
            # Policy violation: candidate attempting to initiate conversation
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
                return JsonResponse({
                    'success': False,
                    'error': 'Candidates cannot initiate unsolicited messages. Only verified employers may start candidate conversations.'
                }, status=403)
            raise PermissionDenied("Healthcare candidates cannot initiate direct messages to employers.")

        employer_profile = getattr(user, 'employer_profile', None)
        if not employer_profile:
            employer_profile, _ = EmployerProfile.objects.get_or_create(
                user=user,
                defaults={'company_name': f"{user.get_full_name() or user.username} Healthcare"}
            )

        candidate = get_object_or_404(CandidateProfile, pk=candidate_id)
        subject = request.POST.get('subject', '').strip() or f"Direct Inquiry from {employer_profile.company_name}"
        message_body = request.POST.get('body', '').strip() or request.POST.get('message', '').strip()
        job_id = request.POST.get('job_id')
        job = Job.objects.filter(pk=job_id, employer=employer_profile).first() if job_id else None

        if not message_body:
            messages.error(request, "Please provide a message body to start the conversation.")
            return redirect(request.META.get('HTTP_REFERER', reverse('employers:talent_search')))

        # Check if an open conversation already exists between employer and candidate
        conversation = Conversation.objects.filter(
            employer=employer_profile,
            candidate=candidate,
            status=Conversation.Status.OPEN
        ).first()

        if not conversation:
            conversation = Conversation.objects.create(
                employer=employer_profile,
                candidate=candidate,
                job=job,
                subject=subject,
                status=Conversation.Status.OPEN
            )

        # Create the initial message
        msg = DirectMessage.objects.create(
            conversation=conversation,
            sender=user,
            body=message_body
        )

        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])

        # Notify candidate in-app
        send_notification(
            recipient=candidate.user,
            title=f"New Message from {employer_profile.company_name}",
            message=f"{employer_profile.company_name} started a direct conversation regarding '{subject}'.",
            notification_type=Notification.NotificationType.JOB_MATCH,
            link=reverse('dashboard:messages_thread', kwargs={'pk': conversation.pk})
        )

        log_staff_action(
            actor=user,
            action=f"Started conversation #{conversation.id} with candidate {candidate.full_name}",
            action_category=AuditLog.Category.STAFF_ACTION,
            target_user=candidate.user,
            target_entity='Conversation',
            target_id=conversation.id,
            request=request
        )

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json'
        if is_ajax:
            return JsonResponse({
                'success': True,
                'conversation_id': conversation.id,
                'redirect_url': reverse('dashboard:messages_thread', kwargs={'pk': conversation.pk}),
                'message': f"Message sent to {candidate.full_name}!"
            })

        messages.success(request, f"Message sent to {candidate.full_name}! View and continue discussion here.")
        return redirect('dashboard:messages_thread', pk=conversation.pk)


class SendMessageView(LoginRequiredMixin, View):
    """
    Post a message in an existing conversation thread.
    RULES:
    1. User must be either the employer or the candidate of this conversation.
    2. If conversation status is CLOSED, replies are LOCKED and rejected.
    """
    def post(self, request, pk, *args, **kwargs):
        user = request.user
        conversation = get_object_or_404(Conversation, pk=pk)

        # Verify access
        is_emp_owner = hasattr(user, 'employer_profile') and conversation.employer == user.employer_profile
        is_cand_owner = hasattr(user, 'candidate_profile') and conversation.candidate == user.candidate_profile
        is_staff = user.is_kodafriq_staff

        if not (is_emp_owner or is_cand_owner or is_staff):
            raise PermissionDenied("You do not have access to this conversation.")

        # ENFORCE CLOSURE RULE: Cannot reply if closed!
        if conversation.status == Conversation.Status.CLOSED:
            err_msg = "This conversation has been closed by the healthcare employer. No further replies can be posted."
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
                return JsonResponse({'success': False, 'error': err_msg}, status=403)
            messages.error(request, err_msg)
            return redirect('dashboard:messages_thread', pk=conversation.pk)

        body = request.POST.get('body', '').strip()
        if not body:
            messages.error(request, "Message cannot be blank.")
            return redirect('dashboard:messages_thread', pk=conversation.pk)

        msg = DirectMessage.objects.create(
            conversation=conversation,
            sender=user,
            body=body
        )
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])

        # Notify the other party
        recipient_user = conversation.candidate.user if is_emp_owner else conversation.employer.user
        sender_label = conversation.employer.company_name if is_emp_owner else conversation.candidate.full_name

        send_notification(
            recipient=recipient_user,
            title=f"New reply from {sender_label}",
            message=f"{body[:120]}...",
            notification_type=Notification.NotificationType.JOB_MATCH,
            link=reverse('dashboard:messages_thread', kwargs={'pk': conversation.pk}),
            send_email=False
        )

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json'
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message_id': msg.id,
                'sender': user.get_full_name() or user.username,
                'body': msg.body,
                'created_at': msg.created_at.strftime('%b %d, %Y %I:%M %p')
            })

        return redirect('dashboard:messages_thread', pk=conversation.pk)


class CloseConversationView(LoginRequiredMixin, View):
    """
    CRITICAL POLICY: Only Employers (or staff/admin) can close a conversation thread.
    Once closed, the professional/candidate can no longer reply.
    """
    def post(self, request, pk, *args, **kwargs):
        user = request.user
        conversation = get_object_or_404(Conversation, pk=pk)

        is_emp_owner = (user.role == User.Role.EMPLOYER and hasattr(user, 'employer_profile') and conversation.employer == user.employer_profile)
        is_staff = user.is_kodafriq_staff

        if not (is_emp_owner or is_staff):
            raise PermissionDenied("Only the healthcare employer can close a conversation thread.")

        conversation.status = Conversation.Status.CLOSED
        conversation.closed_at = timezone.now()
        conversation.closed_by = user
        conversation.save(update_fields=['status', 'closed_at', 'closed_by'])

        # Notify candidate that employer closed the thread
        send_notification(
            recipient=conversation.candidate.user,
            title=f"Conversation Closed by {conversation.employer.company_name}",
            message=f"{conversation.employer.company_name} has concluded and closed the direct message thread '{conversation.subject}'.",
            notification_type=Notification.NotificationType.SYSTEM,
            link=reverse('dashboard:messages_thread', kwargs={'pk': conversation.pk}),
            send_email=False
        )

        log_staff_action(
            actor=user,
            action=f"Closed conversation thread #{conversation.id}",
            action_category=AuditLog.Category.STAFF_ACTION,
            target_user=conversation.candidate.user,
            target_entity='Conversation',
            target_id=conversation.id,
            request=request
        )

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json'
        if is_ajax:
            return JsonResponse({
                'success': True,
                'status': 'CLOSED',
                'message': 'Conversation has been closed. Candidate replies are now locked.'
            })

        messages.info(request, "This conversation has been closed. The candidate can no longer reply.")
        return redirect('dashboard:messages_thread', pk=conversation.pk)


class ReopenConversationView(LoginRequiredMixin, View):
    """Allows employer to reopen a closed conversation thread if desired."""
    def post(self, request, pk, *args, **kwargs):
        user = request.user
        conversation = get_object_or_404(Conversation, pk=pk)

        is_emp_owner = (user.role == User.Role.EMPLOYER and hasattr(user, 'employer_profile') and conversation.employer == user.employer_profile)
        is_staff = user.is_kodafriq_staff

        if not (is_emp_owner or is_staff):
            raise PermissionDenied("Only the healthcare employer can reopen a conversation thread.")

        conversation.status = Conversation.Status.OPEN
        conversation.closed_at = None
        conversation.closed_by = None
        conversation.save(update_fields=['status', 'closed_at', 'closed_by'])

        send_notification(
            recipient=conversation.candidate.user,
            title=f"Conversation Reopened by {conversation.employer.company_name}",
            message=f"{conversation.employer.company_name} reopened the discussion thread '{conversation.subject}'. You may now reply.",
            notification_type=Notification.NotificationType.SYSTEM,
            link=reverse('dashboard:messages_thread', kwargs={'pk': conversation.pk}),
            send_email=False
        )

        messages.success(request, "Conversation reopened! The candidate can now reply.")
        return redirect('dashboard:messages_thread', pk=conversation.pk)
