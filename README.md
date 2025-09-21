# Homelab-Hub
This is a Django application used for vaious viewing or management of my home lab activities



### K8s Deployment
1. Get packages ready for Docker
```bash
uv export -f requirements.txt > requirements.txt
```

2. Collect static files
```bash
python manage.py collectstatic --noinput
```

3. 
