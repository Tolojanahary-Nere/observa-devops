# Observa — Portfolio DevOps/Fullstack

> Stack de production complète : **FastAPI async** · **PostgreSQL** · **Redis** · **Celery** · **Nginx** · **Prometheus** · **Grafana** · **GitHub Actions CI/CD**

[![CI/CD Pipeline](https://github.com/yourusername/observa/actions/workflows/deploy.yml/badge.svg)](https://github.com/yourusername/observa/actions/workflows/deploy.yml)
[![codecov](https://codecov.io/gh/yourusername/observa/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/observa)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg)](https://docs.docker.com/compose/)

---

## 🏗️ Architecture

```
                          ┌─────────────────────────────────────────┐
                          │              NGINX (Reverse Proxy)       │
                          │  Rate Limiting · Security Headers · Gzip │
                          └────────────┬────────────────┬────────────┘
                                       │ /api/          │ /grafana/
                    ┌──────────────────▼──┐      ┌──────▼───────────┐
                    │   FastAPI (async)    │      │     Grafana       │
                    │  /metrics /health   │      │  Dashboards       │
                    │  /api/v1/tasks/     │      └──────┬────────────┘
                    └──┬──────────────┬──┘             │
                       │              │          ┌──────▼────────────┐
               ┌───────▼──┐    ┌──────▼────┐    │    Prometheus     │
               │PostgreSQL│    │   Redis   │◄───│  Scrape /metrics  │
               │  (async) │    │  Broker   │    └───────────────────┘
               └──────────┘    └─────┬─────┘
                                     │
                              ┌──────▼────────┐
                              │ Celery Worker  │
                              │ (async tasks) │
                              └───────────────┘
```

---

## ✨ Fonctionnalités

| Domaine | Technologie | Détail |
|---|---|---|
| **API** | FastAPI 0.111 | Async, OpenAPI auto, validation Pydantic v2 |
| **Base de données** | PostgreSQL 16 | SQLAlchemy async + asyncpg, pool de connexions |
| **Cache / Broker** | Redis 7 | Broker Celery + cache applicatif |
| **Workers** | Celery 5.4 | At-least-once, retry exponentiel, time limits |
| **Reverse Proxy** | Nginx 1.25 | Rate limiting, security headers, gzip |
| **Métriques** | Prometheus | Latence P50/P95/P99, throughput, erreurs |
| **Dashboards** | Grafana | Auto-provisioning, dashboard FastAPI pré-configuré |
| **CI/CD** | GitHub Actions | Tests → Build GHCR → Deploy SSH |
| **Conteneurs** | Docker Compose | 7 services, networks isolés, health checks |

---

## 🚀 Démarrage rapide

### Prérequis
- Docker Engine 24+ et Docker Compose v2
- Make (optionnel)

### 1. Clone et configuration

```bash
git clone https://github.com/yourusername/observa.git
cd observa

# Copier et configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (SECRET_KEY, POSTGRES_PASSWORD, etc.)
```

### 2. Générer les secrets

```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# POSTGRES_PASSWORD et REDIS_PASSWORD
openssl rand -base64 24
```

### 3. Lancer la stack complète

```bash
# Dev local (avec hot-reload, ports exposés)
docker compose up -d

# Production (sans l'override de dev)
docker compose -f docker-compose.yml up -d
```

### 4. Vérification

```bash
# Health check
curl http://localhost/health

# API Docs
open http://localhost/api/docs

# Grafana (admin / votre GRAFANA_PASSWORD)
open http://monitoring.localhost/grafana/

# Prometheus
open http://localhost:9090   # uniquement en dev
```

---

## 📊 Métriques exposées

L'endpoint `/metrics` expose au format Prometheus :

| Métrique | Type | Description |
|---|---|---|
| `http_requests_total` | Counter | Requêtes par méthode/endpoint/status |
| `http_request_duration_seconds` | Histogram | Latence P50/P95/P99 par endpoint |
| `http_requests_in_progress` | Gauge | Requêtes en cours (détecte les leaks) |
| `http_request_exceptions_total` | Counter | Exceptions non gérées par type |

> **Note sécurité** : `/metrics` est bloqué par Nginx (`deny all`). Prometheus scrape directement le service `api:8000` via le réseau Docker interne.

---

## 🧪 Tests

```bash
# Installer les dépendances de test
pip install -r requirements.txt pytest-mock aiosqlite

# Lancer les tests avec coverage
pytest --cov=app --cov-report=term-missing -v

# Lancer un test spécifique
pytest tests/test_api.py::test_create_task_returns_202 -v
```

Les tests utilisent **SQLite en mémoire** → zéro infrastructure requise.

---

## 🔄 CI/CD Pipeline

```
┌─────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Push   │───►│  JOB 1: test     │───►│  JOB 2: build       │
│  main   │    │  • Ruff lint     │    │  • Multi-tag GHCR   │
└─────────┘    │  • pytest        │    │  • Cache GHA        │
               │  • coverage ≥70% │    │  • SBOM provenance  │
               └──────────────────┘    └──────────┬──────────┘
                                                  │
                                       ┌──────────▼──────────┐
                                       │  JOB 3: deploy      │
                                       │  • SSH + git pull   │
                                       │  • docker compose   │
                                       │  • health check     │
                                       │  • auto rollback    │
                                       └─────────────────────┘
```

### Secrets GitHub requis

Configurer dans **Settings → Secrets and variables → Actions** :

| Secret | Description |
|---|---|
| `GHCR_TOKEN` | PAT GitHub avec scope `packages:write` |
| `DEPLOY_HOST` | IP ou hostname du serveur de prod |
| `DEPLOY_USER` | Utilisateur SSH (`ubuntu`, `deploy`...) |
| `DEPLOY_SSH_KEY` | Clé SSH privée (ED25519 recommandé) |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL |
| `REDIS_PASSWORD` | Mot de passe Redis |
| `SECRET_KEY` | Clé secrète FastAPI |
| `GRAFANA_PASSWORD` | Mot de passe admin Grafana |

---

## 📁 Structure du projet

```
observa/
├── .github/workflows/deploy.yml    # Pipeline CI/CD 3 jobs
├── app/
│   ├── main.py                     # Entrypoint FastAPI + lifespan
│   ├── config.py                   # Settings via pydantic-settings
│   ├── database.py                 # SQLAlchemy async engine
│   ├── models.py                   # Modèles ORM
│   ├── middleware/
│   │   └── prometheus.py           # Instrumentation Prometheus
│   ├── routers/
│   │   ├── health.py               # /health + /metrics
│   │   └── tasks.py                # CRUD tâches asynchrones
│   └── workers/
│       ├── celery_app.py           # Config Celery
│       └── tasks.py                # Définition des tâches
├── nginx/
│   ├── nginx.conf                  # Config principale
│   └── conf.d/
│       ├── api.conf                # VHost API + rate limiting
│       └── grafana.conf            # VHost Grafana
├── monitoring/
│   ├── prometheus.yml              # Config scrape
│   └── grafana/
│       ├── provisioning/           # Auto-config Grafana
│       └── dashboards/fastapi.json # Dashboard pré-configuré
├── tests/
│   ├── conftest.py                 # Fixtures pytest
│   └── test_api.py                 # Tests d'intégration
├── docker-compose.yml              # Stack production
├── docker-compose.override.yml     # Overrides dev local
├── Dockerfile                      # Image multi-stage
└── pytest.ini                      # Config pytest
```

---

## 🔒 Bonnes pratiques de sécurité

- ✅ **Utilisateur non-root** dans le container Docker (uid 1001)
- ✅ **Secrets via variables d'environnement** (jamais hardcodés)
- ✅ **/metrics bloqué** par Nginx (`deny all`)
- ✅ **Security headers** sur toutes les réponses Nginx
- ✅ **Rate limiting** 10 req/s par IP
- ✅ **Images multi-stage** (réduisent la surface d'attaque)
- ✅ **SBOM + provenance** sur les images Docker (supply-chain security)
- ✅ **Networks Docker isolés** (frontend/backend)

---

## 📚 Choix techniques justifiés

**FastAPI vs Django/Flask** : Performances async natives, validation Pydantic v2 intégrée, OpenAPI généré automatiquement.

**asyncpg vs psycopg2** : Driver natif async pour PostgreSQL, 3-5x plus rapide que psycopg2 en mode async.

**Celery vs RQ** : Mature, riche en fonctionnalités (retry, scheduling, routing), meilleur support des time limits.

**Prometheus + Grafana vs Datadog** : Open-source, self-hosted, zéro coût, standard industrie pour Kubernetes.

**pydantic-settings** : Validation des configs au démarrage (fail-fast), typage fort, support `.env`.

---

*Projet de portfolio DevOps/Fullstack — Construit avec ❤️ pour démontrer les meilleures pratiques de production.*
