from django.apps import AppConfig


class GrowthOSConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.growth_os'
    verbose_name = 'Kodafriq GrowthOS'

    def ready(self):
        import apps.growth_os.signals  # noqa
