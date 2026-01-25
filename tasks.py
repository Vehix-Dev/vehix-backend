raise RuntimeError(
    "Local file config/tasks.py is present and may shadow Celery task discovery.\n"
    "Remove or rename this file; tasks are defined under config/config/tasks.py"
)
