import os
import sys

wsgi_dir = os.path.dirname(os.path.abspath(__file__))
inner_config_dir = os.path.dirname(wsgi_dir)
project_root = os.path.dirname(inner_config_dir)

sys.path.insert(0, project_root)
sys.path.insert(0, inner_config_dir)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# CRITICAL: Deep purge 'requests' from module cache to prevent shadowing.
import sys
_old_mods = {k: v for k, v in sys.modules.items() if k == 'requests' or k.startswith('requests.')}
for mod_name in list(_old_mods.keys()):
    del sys.modules[mod_name]

application = get_wsgi_application()