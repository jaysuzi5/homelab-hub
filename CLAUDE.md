# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Homelab-Hub is a Django 5.2 application serving as a central hub for monitoring and managing home lab activities and personal finance. It aggregates data from multiple external systems (Kubernetes, Splunk, solar panels, energy usage, NAS, weather) into a real-time dashboard, and includes a Monte Carlo-based retirement planning calculator.

**Key Technologies:** Django 5.2, PostgreSQL, Kubernetes, Docker, Tailwind CSS, Chart.js, django-allauth

## Common Development Commands

```bash
# Local development server (with auto-reload)
uv run manage.py runserver

# Database migrations
uv run manage.py migrate

# Collect static files for production
uv run manage.py collectstatic

# Django interactive shell
uv run manage.py shell

# Compile dependencies
uv pip compile -o requirements.txt pyproject.toml

# Build Docker image for multiple platforms
uv pip compile -o requirements.txt pyproject.toml
docker buildx build --platform linux/amd64,linux/arm64 -t jaysuzi5/homelab-hub:latest --push .
```

**Package Manager:** uv (ultra-fast Python installer). Never use pip directly; use `uv pip` instead.

## Architecture Overview

### Application Structure

**Core Apps:**

- **dashboard** - Real-time monitoring dashboard aggregating data from 8+ services
  - Views: `home()` (async), `k8s()` - collect data from external APIs in parallel
  - Services (in `dashboard/services/`):
    - `k8s.py` - Kubernetes metrics via API
    - `emporia.py` - Energy usage
    - `enphase.py` - Solar production
    - `synology.py` - NAS metrics
    - `network.py`, `darts.py`, `splunk.py`, `weather.py` - Various home lab integrations
  - Templates: `home.html` (525 lines, main dashboard), `k8s.html`
  - Features: Parallel async data collection, graceful error handling, auto-refresh

- **financial** - Retirement planning calculator
  - `calculator.py` - Monte Carlo simulation engine (GBM-based portfolio modeling)
  - `forms.py` - Retirement form with Social Security presets
  - Key functions: `monte_carlo_simulation()`, `find_max_withdrawal()`, `generate_balance_constant_return()`
  - Supports stochastic portfolio modeling with configurable withdrawal strategies

- **config** - Key-value configuration store
  - Single model: `HubConfig(key, value)`
  - `get_config()` utility - checks environment variables first, then database, then default
  - Stores: API endpoints, Social Security benefits, retirement parameters, cost per kWh

- **hub** - Django project root
  - `settings.py` - 13 installed apps, 9 middleware layers
  - `middleware.py` - `LoginRequiredMiddleware` enforces authentication for all views except `/accounts/*` and `/admin/`
  - `urls.py` - Root URL routing

### Data Flow Architecture

```
External APIs (K8s, Splunk, home APIs)
    ↓
Service Collectors (dashboard/services/*.py)
    ↓ (parallel async gather)
View Functions (async home() view)
    ↓
Template Context
    ↓
Template Rendering (base.html + page-specific templates)
    ↓
HTML Response
```

### Database Design

**Minimal ORM usage** - Application is primarily read-only with minimal data modeling:
- Only 1 model: `HubConfig` for configuration
- Services fetch from external APIs, not database
- Dashboard and Financial apps have no models
- PostgreSQL backend configured via environment variables

### Authentication & Authorization

- **System:** django-allauth with Google OAuth support
- **Flow:** All content requires authentication (enforced by `LoginRequiredMiddleware`)
- **Exempt URLs:** `/accounts/*`, `/admin/`, social login callbacks
- **Session-based:** Standard Django session authentication

## Important Configuration Details

### Environment Variables Required

Database credentials, API endpoints, and calculation parameters are configured via environment variables:

```
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
SECRET_KEY
DJANGO_DEBUG
SPLUNK_HOST, SPLUNK_PORT, SPLUNK_USER, SPLUNK_PASSWORD
NETWORK_URL, ENPHASE_API_SEARCH_URL, EMPORIA_API_SEARCH_URL
DARTS_URL, SYNOLOGY_URL, WEATHER_URL, FORECAST_URL
COST_PER_KWH
SS_BENEFITS_62, SS_BENEFITS_65, SS_BENEFITS_67, SS_BENEFITS_70
RETIREMENT_AGE, PORTFOLIO_BALANCE, SS_AGE
```

### Static Files & Frontend

- **CSS Framework:** Tailwind CSS (Django integration via django-tailwind)
- **JavaScript:** Vanilla JS + Chart.js for visualization
- **Static Files:** Served via WhiteNoise in production (configured in settings.py)
- **Static Root:** `./staticfiles/` directory (auto-collected during build)

### Deployment

**Development:** `uv run manage.py runserver` (SQLite-compatible for quick testing)

**Production:**
- **Container:** Docker with Python 3.11-slim-bookworm base
- **WSGI Server:** Gunicorn (exposed on port 8000)
- **Database:** PostgreSQL (IP-based connection)
- **Kubernetes:** Auto-loads in-cluster config with fallback to local kubeconfig

## Key Implementation Patterns

### Async Data Collection (dashboard/views.py)

The `home()` view uses `asyncio.gather()` to parallelize service calls:

```python
@sync_to_async
def home(request):
    # Parallel collection of data from 8+ services
    results = asyncio.gather(
        service1.fetch_data(),
        service2.fetch_data(),
        ...
    )
```

Services gracefully handle failures with try/except blocks and provide fallback values.

### Unit Conversion in Services

Services parse Kubernetes resource units (CPU: m/n, Memory: Ki/Mi/Gi/Ti) and normalize them for display. Check `dashboard/services/k8s.py` for examples.

### Configuration Precedence

The `get_config()` function in `config/utils.py` implements: **Environment Variable → Database → Default**. Use this pattern for all configuration lookups.

### Financial Calculations

The retirement calculator uses Geometric Brownian Motion (GBM) for portfolio modeling:
- `monte_carlo_simulation()` - Runs N simulations with stochastic returns
- `find_max_withdrawal()` - Binary search to find maximum sustainable withdrawal rate
- Integrates Social Security claiming age strategy (62, 65, 67, 70 with different benefit amounts)
- Returns success rates, balance percentiles, and maximum withdrawal amounts

## Testing & Quality

**Current Status:**
- Empty test files exist in config, dashboard, financial apps
- No test framework configured
- No CI/CD pipeline configured

**For Future Implementation:**
- Use pytest (Django-compatible)
- Test the service integrations with mock API responses
- Test async data collection and error handling
- Validate Monte Carlo simulation output

## Known Quirks & Gotchas

1. **K8s Integration:** Auto-detects if running in-cluster vs. local. Ensure kubeconfig is properly set for local development.

2. **Parallel API Calls:** Services must handle individual failures without blocking the entire dashboard. Always wrap external API calls in try/except.

3. **Database Connection:** PostgreSQL at IP-based address (192.168.86.200:30002). Ensure network access for development.

4. **Static Files:** Remember to run `collectstatic` before deploying. WhiteNoise handles serving in production.

5. **Tailwind CSS:** Changes to CSS classes require template changes to reflect in tailwind output. Check django-tailwind configuration if styles aren't appearing.

6. **Social Security Configuration:** Benefits are stored in database/env and referenced by claiming age (62, 65, 67, 70). The form has quick-select buttons for these ages.

## File Navigation Reference

- **Dashboard configuration:** `hub/settings.py` (INSTALLED_APPS, MIDDLEWARE, database)
- **Main dashboard template:** `dashboard/templates/home.html` (525 lines)
- **Service examples:** `dashboard/services/k8s.py`, `emporia.py`
- **Retirement calculator logic:** `financial/calculator.py`
- **Authentication setup:** `hub/middleware.py`, `hub/settings.py` (AUTHENTICATION_BACKENDS)
- **URL routing:** `hub/urls.py`, `financial/urls.py`
- **Configuration model:** `config/models.py`, `config/utils.py`
