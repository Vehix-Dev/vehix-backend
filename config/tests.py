from django.test import SimpleTestCase


class FallbackManifestStorageTests(SimpleTestCase):
    def test_missing_manifest_entry_falls_back_to_original_path(self):
        from config.storage import FallbackManifestStaticFilesStorage

        storage = FallbackManifestStaticFilesStorage()

        self.assertEqual(storage.stored_name('admin/css/base.css'), 'admin/css/base.css')
