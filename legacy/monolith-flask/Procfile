# Procfile for Railway deployment
web: gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class gthread --timeout 120
