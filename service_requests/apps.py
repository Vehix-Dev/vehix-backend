from django.apps import AppConfig


class RequestsConfig(AppConfig):
    name = 'service_requests'

    def ready(self):
        import service_requests.signals
