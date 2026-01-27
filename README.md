# Homelab-Hub
This is a Django application used for vaious viewing or management of my home lab activities



## Run Server
```bash
uv run python manage.py runserver localhost:8000

```


### Build & Push Multi-Architecture Docker Image

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t jaysuzi5/homelab-hub:latest --push .
```


### Redeploy
```bash
kubectl rollout restart deployment homelab-hub -n homelab-hub
```