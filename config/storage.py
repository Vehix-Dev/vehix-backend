from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class FallbackManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Fall back to the original static path when the manifest is missing an entry."""

    def stored_name(self, name, content=None, force=False):
        try:
            return super().stored_name(name, content=content, force=force)
        except ValueError:
            return name
