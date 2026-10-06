from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib import messages
from apps.skills.models import Skill, SkillCategory
from .models import ContactInquiry, FAQItem, LegalPage


def home(request):
    categories = SkillCategory.objects.prefetch_related('skills').all()
    faqs = FAQItem.objects.filter(is_active=True).order_by('display_order', 'id')
    context = {
        'categories': categories,
        'faqs': faqs,
    }
    return render(request, 'core/home.html', context)


def contact_submit(request):
    """
    Handles inquiries submitted from the website Contact Us section.
    Supports both asynchronous AJAX/fetch requests and standard form submissions.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        inquiry_type = request.POST.get('inquiry_type', 'employer').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            request.POST.get('format') == 'json' or
            request.content_type == 'application/json'
        )

        if not name or not email or not message:
            error_msg = "Please provide your full name, work email address, and inquiry message."
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('/#contact')

        inquiry = ContactInquiry.objects.create(
            name=name,
            email=email,
            phone=phone,
            inquiry_type=inquiry_type,
            subject=subject or 'Website Inquiry',
            message=message
        )

        success_msg = "Thank you for contacting Kodafriq! Your inquiry has been safely received, and our team will get in touch shortly."
        if is_ajax:
            return JsonResponse({'success': True, 'message': success_msg})

        messages.success(request, success_msg)
        return redirect('/#contact')

    return redirect('core:home')


def privacy_policy(request):
    """
    Renders the platform Privacy Policy, dynamically modifiable via Django Admin.
    """
    legal_page = LegalPage.objects.filter(page_type='privacy', is_published=True).first()
    context = {
        'legal_page': legal_page,
        'doc_type': 'privacy',
        'default_title': 'Privacy Policy',
    }
    return render(request, 'core/legal_page.html', context)


def terms_of_service(request):
    """
    Renders the platform Terms of Service, dynamically modifiable via Django Admin.
    """
    legal_page = LegalPage.objects.filter(page_type='terms', is_published=True).first()
    context = {
        'legal_page': legal_page,
        'doc_type': 'terms',
        'default_title': 'Terms of Service',
    }
    return render(request, 'core/legal_page.html', context)


def custom_permission_denied_view(request, exception=None):
    return render(request, '403.html', {'exception': exception, 'path': request.path}, status=403)
