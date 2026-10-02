import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def get_platform_url():
        return getattr(settings, 'PLATFORM_URL', 'https://kodafriq.com').rstrip('/')

    @classmethod
    def dispatch_email(cls, subject, template_name, context, recipient_list):
        """
        Core dispatcher for branded Kodafriq emails.
        Ensures consistent headers, context, and error logging without emojis.
        """
        if not recipient_list:
            return False

        if isinstance(recipient_list, str):
            recipient_list = [recipient_list]

        platform_url = cls.get_platform_url()
        context.setdefault('platform_name', 'Kodafriq Data Management Solutions')
        context.setdefault('platform_url', platform_url)
        context.setdefault('support_email', 'support@kodafriq.com')
        context.setdefault('company_address', 'Manchester & Lagos • Healthcare Operations Ecosystem')

        try:
            html_message = render_to_string(template_name, context)
            plain_message = strip_tags(html_message)
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Kodafriq Platform <notifications@kodafriq.com>')

            send_mail(
                subject=f"Kodafriq | {subject}",
                message=plain_message,
                from_email=from_email,
                recipient_list=recipient_list,
                html_message=html_message,
                fail_silently=False
            )
            logger.info(f"Successfully sent email '{subject}' to {recipient_list}")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch email '{subject}' to {recipient_list}: {e}")
            return False

    @classmethod
    def send_verification_email(cls, user, request=None):
        """
        Sends an email verification link to a newly registered user.
        """
        if not user.email:
            return False

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verification_path = reverse('accounts:verify_email', kwargs={'uidb64': uid, 'token': token})
        
        if request:
            verification_url = request.build_absolute_uri(verification_path)
        else:
            verification_url = f"{cls.get_platform_url()}{verification_path}"

        context = {
            'user': user,
            'full_name': user.get_full_name() or user.username,
            'verification_url': verification_url,
            'expires_hours': 24,
        }

        return cls.dispatch_email(
            subject="Verify Your Email Address",
            template_name="emails/verify_email.html",
            context=context,
            recipient_list=[user.email]
        )

    @classmethod
    def send_password_reset_email(cls, user, reset_url):
        """
        Dispatches branded password reset instructions.
        """
        if not user.email:
            return False

        context = {
            'user': user,
            'full_name': user.get_full_name() or user.username,
            'reset_url': reset_url,
        }

        return cls.dispatch_email(
            subject="Password Reset Request",
            template_name="emails/password_reset_email.html",
            context=context,
            recipient_list=[user.email]
        )

    @classmethod
    def send_candidate_shortlisted_email(cls, candidate_user, employer_name, notes=None):
        """
        Notifies a healthcare professional that an employer has shortlisted their profile.
        """
        if not candidate_user.email:
            return False

        context = {
            'candidate_name': candidate_user.get_full_name() or candidate_user.username,
            'employer_name': employer_name,
            'notes': notes,
            'portal_url': f"{cls.get_platform_url()}/dashboard/candidate/",
        }

        return cls.dispatch_email(
            subject=f"Profile Shortlisted by {employer_name}",
            template_name="emails/candidate_shortlisted.html",
            context=context,
            recipient_list=[candidate_user.email]
        )

    @classmethod
    def send_interview_invitation_email(cls, candidate_user, employer_name, job_title, interview_details=None):
        """
        Dispatches an interview invitation notice to a candidate.
        """
        if not candidate_user.email:
            return False

        context = {
            'candidate_name': candidate_user.get_full_name() or candidate_user.username,
            'employer_name': employer_name,
            'job_title': job_title,
            'details': interview_details or 'The hiring team will follow up via messages with meeting credentials.',
            'portal_url': f"{cls.get_platform_url()}/dashboard/candidate/",
        }

        return cls.dispatch_email(
            subject=f"Interview Invitation: {job_title} at {employer_name}",
            template_name="emails/interview_invitation.html",
            context=context,
            recipient_list=[candidate_user.email]
        )

    @classmethod
    def send_application_submitted_email(cls, candidate_user, job):
        """
        Confirms receipt of candidate application to a clinical role.
        """
        if not candidate_user.email:
            return False

        context = {
            'candidate_name': candidate_user.get_full_name() or candidate_user.username,
            'job_title': job.title,
            'employer_name': job.employer.company_name,
            'portal_url': f"{cls.get_platform_url()}/dashboard/candidate/",
        }

        return cls.dispatch_email(
            subject=f"Application Received: {job.title}",
            template_name="emails/application_submitted.html",
            context=context,
            recipient_list=[candidate_user.email]
        )

    @classmethod
    def send_employer_application_alert_email(cls, employer_user, job, candidate_user):
        """
        Alerts an employer that a new candidate has applied to their listing.
        """
        if not employer_user.email:
            return False

        context = {
            'employer_name': employer_user.get_full_name() or employer_user.username,
            'job_title': job.title,
            'candidate_name': candidate_user.get_full_name() or candidate_user.username,
            'portal_url': f"{cls.get_platform_url()}/employers/applications/",
        }

        return cls.dispatch_email(
            subject=f"New Candidate Application: {job.title}",
            template_name="emails/employer_application_alert.html",
            context=context,
            recipient_list=[employer_user.email]
        )
