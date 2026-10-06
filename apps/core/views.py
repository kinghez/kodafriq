from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from apps.skills.models import Skill, SkillCategory
from .models import ContactInquiry


def home(request):
    categories = SkillCategory.objects.prefetch_related('skills').all()
    context = {
        'categories': categories,
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


def custom_permission_denied_view(request, exception=None):
    return render(request, '403.html', {'exception': exception, 'path': request.path}, status=403)
