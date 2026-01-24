from django.apps import AppConfig


class RequestsConfig(AppConfig):
    name = 'requests'

    def ready(self):
        import requests.signals
