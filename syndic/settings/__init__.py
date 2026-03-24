"""Settings loader.

Selects settings module from DJANGO_ENV:
- dev (default)
- prod
"""

import os

DJANGO_ENV = os.getenv("DJANGO_ENV", "dev").strip().lower()

if DJANGO_ENV == "prod":
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
