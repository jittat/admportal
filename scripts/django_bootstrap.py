import os, sys

def bootstrap():
    sys.path.append(os.getcwd())
    sys.path.append(os.path.join(os.getcwd(), '..'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admportal.settings")

    import django
    django.setup()
