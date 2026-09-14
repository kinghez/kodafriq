from django.shortcuts import render
from apps.skills.models import Skill, SkillCategory

def home(request):
    categories = SkillCategory.objects.prefetch_related('skills').all()
    context = {
        'categories': categories,
    }
    return render(request, 'core/home.html', context)
