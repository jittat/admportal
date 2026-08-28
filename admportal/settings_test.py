"""Settings for running the test suite.

settings.py ends by importing settings_local.py, which in practice points at the
per-year MySQL database — an account that cannot create the test database.  Run
tests against SQLite instead:

    ./manage.py test --settings=admportal.settings_test
"""

from admportal.settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
