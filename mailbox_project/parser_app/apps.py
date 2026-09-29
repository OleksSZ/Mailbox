from django.apps import AppConfig


class ParserAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parser_app'

    def ready(self):
        import other.Mailbox.mailbox_project.parser_app.signals  # noqa