from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('assessments/', include('apps.assessments.urls', namespace='assessments')),
    path('employers/', include('apps.employers.urls', namespace='employers')),
    path('training/', include('apps.training.urls', namespace='training')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('contracts/', include('apps.contracts.urls', namespace='contracts')),
    path('billing/', include('apps.billing.urls', namespace='billing')),
    path('growth-os/', include('apps.growth_os.urls', namespace='growth_os')),
    path('', include('apps.core.urls', namespace='core')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler403 = 'apps.core.views.custom_permission_denied_view'
