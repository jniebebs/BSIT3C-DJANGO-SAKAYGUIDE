"""Package marker for the SakayGuide Django applications.

Making ``apps`` a regular package lets Django's default test discovery find
``apps/*/tests.py`` when running ``python manage.py test`` from the project
root. Application imports (``apps.core``, ``apps.users``, ``apps.info``) are
unchanged.
"""
