import os

os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('FLASK_CONFIG', 'production')

from run import app  # noqa: E402,F401

