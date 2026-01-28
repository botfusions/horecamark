# HorecaMark Price Intelligence System - Implementation Plan

## Overview

Build a Price Intelligence Scraper & Analytics System.

## Project Type

**BACKEND/SCRAPING** - Python-based web scraping with PostgreSQL.

## Success Criteria

- [ ] All 6 sites scraped daily at 08:00
- [ ] Products matched >85% accuracy
- [ ] Price changes >5% detected
- [ ] Excel reports generated
- [ ] Email notifications sent
- [ ] System runs on Windows with Docker

## Tech Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Backend | Python 3.11+ | Async support |
| Scraping | Playwright | Browser automation |
| Database | PostgreSQL | Price history |
| ORM | SQLAlchemy | Type-safe |
| Matching | thefuzz | Fuzzy matching |
| Container | Docker + Compose | Windows compatible |
| Scheduler | n8n/Python | Flexible timing |
| Reporting | openpyxl + smtplib | Excel + Email |

## File Structure

horecemark/
|-- docker-compose.yml
|-- scraper/
|   |-- Dockerfile
|   |-- requirements.txt
|   |-- config.py
|   |-- database.py
|   |-- main.py
|   |-- sites/
|   |   |-- __init__.py
|   |   |-- base.py
|   |   |-- cafemarkt.py
|   |   |-- arigastro.py
|   |   |-- horecamarkt.py
|   |   |-- kariyermutfak.py
|   |   |-- mutbex.py
|   |   |-- horecamark.py
|   |-- utils/
|       |-- __init__.py
|       |-- matcher.py
|       |-- notifier.py
|       |-- reporter.py
|       |-- normalizer.py
|-- database/
|   |-- migrations/
|   |-- seeds/
|-- n8n-workflows/
|-- tests/
|-- logs/
|-- reports/

## Target Sites

| Site | Platform | Strategy | Difficulty |
|------|----------|----------|------------|
| CafeMarkt | Custom .NET/PHP | Infinite scroll | Hard |
| AriGastro | WooCommerce | API first | Medium |
| HorecaMarkt | Shopify/Custom | products.json | Medium |
| KariyerMutfak | Custom Turkish | Sitemap | Medium |
| Mutbex | Shopify | products.json | Easy |
| HorecaMark | WooCommerce | CSV/API | Easy |

## Phase -1: Context Check (COMPLETE)

- [x] OS: Windows
- [x] Database: PostgreSQL
- [x] Reporting: Excel + Email
- [x] Sites: 6 e-commerce platforms
- [x] Schedule: Daily 08:00
- [x] Container: Docker + Compose

## Phase 0: Prerequisites

Agent: backend-specialist | Complexity: Easy | Dependencies: None

Tasks:
- [ ] Task 1: Create project directory structure
- [ ] Task 2: Create requirements.txt
- [ ] Task 3: Create .env.example

Verify:
- dir scraper/sites
- dir scraper/utils
- type requirements.txt

## Phase 1: Foundation

Agent: database-architect | Complexity: Medium | Dependencies: Phase 0

Tasks:
- [ ] Task 1: Create Docker Compose (docker-compose.yml)
- [ ] Task 2: Create database schema (database.py with SQLAlchemy)
- [ ] Task 3: Create migration script (database/migrations/001_initial.sql)
- [ ] Task 4: Create Dockerfile (scraper/Dockerfile)

Verify:
- docker-compose config
- docker build -t horeca-scraper scraper/

## Phase 2: Base Scraper Framework

Agent: backend-specialist | Complexity: Medium | Dependencies: Phase 1

Tasks:
- [ ] Task 1: Create base scraper class (sites/base.py)
- [ ] Task 2: Create config module (config.py with SITE_CONFIGS)
- [ ] Task 3: Create text normalizer (utils/normalizer.py)
- [ ] Task 4: Create DB connection utility (database.py)

Verify:
- python -c "from sites.base import BaseScraper; print(OK)"

## Phase 3: Site Scrapers (Parallel)

Agent: backend-specialist | Complexity: Hard | Dependencies: Phase 2

Tasks:
- [ ] Task 1: Create CafeMarkt scraper (sites/cafemarkt.py) - Hardest
- [ ] Task 2: Create AriGastro scraper (sites/arigastro.py)
- [ ] Task 3: Create HorecaMarkt scraper (sites/horecamarkt.py)
- [ ] Task 4: Create KariyerMutfak scraper (sites/kariyermutfak.py)
- [ ] Task 5: Create Mutbex scraper (sites/mutbex.py)
- [ ] Task 6: Create HorecaMark scraper (sites/horecamark.py)

Verify:
- python -m pytest tests/test_scrapers.py -v

## Phase 4: Product Matching

Agent: backend-specialist | Complexity: Hard | Dependencies: Phase 3

Tasks:
- [ ] Task 1: Create fuzzy matching algorithm (utils/matcher.py)
- [ ] Task 2: Add multi-factor scoring (brand, SKU, capacity)
- [ ] Task 3: Create brand extractor function
- [ ] Task 4: Create SKU extractor with regex
- [ ] Task 5: Create manual mapping table for overrides

Verify:
- python -m pytest tests/test_matcher.py -v

## Phase 5: Analytics & Change Detection

Agent: backend-specialist | Complexity: Medium | Dependencies: Phase 4

Tasks:
- [ ] Task 1: Create price change detector (utils/analyzer.py)
- [ ] Task 2: Create action recommendation engine
- [ ] Task 3: Create stock status monitor
- [ ] Task 4: Create new product detector

Verify:
- python -c "from utils.analyzer import detect_changes; print(OK)"

## Phase 6: Reporting

Agent: backend-specialist | Complexity: Medium | Dependencies: Phase 5

Tasks:
- [ ] Task 1: Create Excel report generator (utils/reporter.py)
- [ ] Task 2: Create email notifier (utils/notifier.py)
- [ ] Task 3: Create report templates with formatting
- [ ] Task 4: Create daily report scheduler for 08:00

Verify:
- python -c "from utils.reporter import generate_excel; print(OK)"

## Phase 7: Main Orchestration

Agent: backend-specialist | Complexity: Medium | Dependencies: Phase 6

Tasks:
- [ ] Task 1: Create main orchestration loop (main.py)
- [ ] Task 2: Add error handling and retry logic
- [ ] Task 3: Add logging system (logs/ folder)
- [ ] Task 4: Create health check endpoint

Verify:
- python main.py --dry-run

## Phase 8: Automation

Agent: devops-engineer | Complexity: Medium | Dependencies: Phase 7

Tasks:
- [ ] Task 1: Create n8n workflow (n8n-workflows/daily-scrape.json)
- [ ] Task 2: Add Python scheduler fallback
- [ ] Task 3: Create Docker startup scripts
- [ ] Task 4: Add monitoring alerts on failure

Verify:
- docker-compose up -d

## Future: Web Dashboard (Phase 2)

**Not**: İlk aşamada Excel + Email raporlama kullanılacak. Web dashboard'u sonraki fazda eklenecek.

Olası özellikler:
- [ ] Fiyat geçmişi grafikleri
- [ ] Canlı ürün karşılaştırma
- [ ] Alert yönetim paneli
- [ ] Manuel eşleştirme arayüzü

## Phase X: Verification (MANDATORY)

Pre-Build:
- [ ] Lint: ruff check scraper/
- [ ] Type check: mypy scraper/
- [ ] Security: pip-audit

Build:
- docker-compose build
- docker-compose ps

Runtime:
- docker-compose up -d
- docker-compose exec db psql -U horeca -d horecemark -c "SELECT COUNT(*) FROM products;"
- docker-compose exec scraper python main.py --site cafemarkt --dry-run
- docker-compose logs -f scraper

Integration:
- [ ] All 6 sites scrape successfully
- [ ] Products matched across sites
- [ ] Price changes detected correctly
- [ ] Excel report generated
- [ ] Email sent successfully
- [ ] Scheduler triggers at 08:00

## Agent Assignments

| Phase | Agent | Tasks |
|-------|-------|-------|
| 0 | backend-specialist | Structure, deps |
| 1 | database-architect | Docker, DB |
| 2 | backend-specialist | Framework |
| 3 | backend-specialist | Scrapers |
| 4 | backend-specialist | Matching |
| 5 | backend-specialist | Analytics |
| 6 | backend-specialist | Reporting |
| 7 | backend-specialist | Orchestration |
| 8 | devops-engineer | Automation |
| X | All agents | Verification |

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Site blocks scraper | High | Rotate UA, delays, proxies |
| Matching fails | High | Manual override, threshold tuning |
| DB corruption | Medium | Backups, migrations |
| Scheduler fails | Medium | Email alerts, manual trigger |
| Calculation errors | High | Unit tests, manual verify |

## Rollback Strategy

Each phase independently reversible:

1. Database: Drop and recreate from migrations
2. Scrapers: Git revert to previous version
3. Docker: docker-compose down && docker-compose up --build
4. Code: Each commit represents one phase completion


```

PHASE X COMPLETE:

- [x] All 6 scrapers working
- [x] Product matching >85% accuracy
- [x] Price changes detected
- [x] Excel reports generated
- [x] Email notifications sent
- [x] Scheduler running at 08:00
- [x] Docker containerized
- [x] Verification scripts passed

Date: [COMPLETION DATE]
```
