# HorecaMark Price Intelligence

Python tabanlı web scraping sistemi - Türk hospitallite endüstrisi için 6 e-ticaret sitesinde fiyat takibi.

## Özellikler

| Özellik | Açıklama |
|---------|----------|
| **Otomatik Tarama** | Günlük 08:00'de 6 siteyi tarar |
| **Ürün Eşleştirme** | Fuzzy matching ile aynı ürünleri bulur |
| **Fiyat Geçmişi** | PostgreSQL'de geçmiş fiyatları saklar |
| **Değişim Tespiti** | %5+ değişiklikleri algılar |
| **Aksiyon Önerileri** | "Fiyat düşür", "Stok fırsatı" gibi tavsiyeler |
| **Excel Rapor** | Çok sayfalı günlük rapor |
| **E-posta Bildirim** | Değişiklikleri e-posta ile gönderir |

## Hedef Siteler

| Site | Platform | Zorluk |
|------|----------|--------|
| CafeMarkt | cafemarkt.com | Custom .NET/PHP | Zor |
| AriGastro | arigastro.com | WooCommerce | Orta |
| HorecaMarkt | horecamarkt.com.tr | Shopify | Orta |
| KariyerMutfak | kariyermutfak.com | Custom Turkish | Orta |
| Mutbex | mutbex.com | Shopify | Kolay |
| HorecaMark | horecamark.com | WooCommerce (Referans) | Kolay |

## Proje Yapısı

```
horecemark/
|-- docker-compose.yml          # PostgreSQL + Python containers
|-- scraper/
|   |-- Dockerfile              # Python container image
|   |-- main.py                 # Ana giriş noktası
|   |-- database.py             # SQLAlchemy modelleri
|   |-- requirements.txt        # Python bağımlılıkları
|   |-- .env.example            # Environment şablonu
|   |-- sites/                  # Site scraper'ları
|   |   |-- base.py             # BaseScraper abstract class
|   |   |-- cafemarkt.py        # CafeMarkt scraper
|   |   |-- arigastro.py        # AriGastro scraper
|   |   |-- horecamarkt.py      # HorecaMarkt scraper
|   |   |-- kariyermutfak.py    # KariyerMutfak scraper
|   |   |-- mutbex.py           # Mutbex scraper
|   |   '-- horecamark.py       # HorecaMark (referans)
|   '-- utils/                  # Yardımcı modüller
|       |-- config.py           # Site konfigürasyonları
|       |-- matcher.py          # Fuzzy matching algoritması
|       |-- normalizer.py       # Metin normalizasyonu
|       |-- analyzer.py         # Fiyat değişim analizi
|       |-- reporter.py         # Excel rapor üreteci
|       |-- notifier.py         # E-posta bildirimleri
|       |-- scheduler.py        # Zamanlayıcı
|       '-- logger.py           # Log sistemi
|-- database/
|   '-- migrations/
|       '-- 001_initial.sql     # İlk database şeması
|-- n8n-workflows/              # n8n otomasyon workflow'ları
|-- scripts/                    # Shell script'ler
|-- tests/                      # Test dosyaları
|-- logs/                       # Uygulama logları
|-- reports/                    # Excel raporları
|-- docs/
|   '-- PLAN-horeca-mark.md     # Implementasyon planı
|-- AGENT.md                    # Proje spesifikasyonu
|-- AUTOMATION.md               # Otomasyon rehberi
'-- README.md                   # Bu dosya
```

## Hızlı Başlangıç

### Docker ile (Önerilen)

```bash
# 1. Environment kopyala
cp scraper/.env.example scraper/.env

# 2. .env dosyasını düzenle (DB şifresi, SMTP ayarları)

# 3. Container'ları başlat
docker-compose up -d

# 4. Database migrasyonunu çalıştır
docker-compose exec scraper python -c "
from scraper.database import engine
from scraper.database import Base
Base.metadata.create_all(engine)
"

# 5. Manuel tarama test
docker-compose exec scraper python -m scraper.main scrape --dry-run
```

### Yerel Geliştirme

```bash
# 1. Python sanal ortam oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. Bağımlılıkları yükle
pip install -r scraper/requirements.txt

# 3. Playwright browser'ları yükle
playwright install chromium

# 4. Environment ayarla
cp scraper/.env.example scraper/.env
# .env dosyasını düzenle

# 5. PostgreSQL başlat
docker-compose up -d db

# 6. Tarama yap
python -m scraper.main scrape
```

## CLI Komutları

```bash
# Tüm siteleri tara
python -m scraper.main scrape

# Belirli bir siteyi tara
python -m scraper.main scrape --site cafemarkt

# Test modu (DB'ye yazmaz)
python -m scraper.main scrape --dry-run

# Detaylı log
python -m scraper.main scrape --verbose

# Tam workflow (tara + analiz et + rapor)
python -m scraper.main run

# Raporu e-posta ile gönder
python -m scraper.main run --email

# Sadece rapor üret
python -m scraper.main report

# Belirli tarih için rapor
python -m scraper.main report --date 2025-01-27

# Scheduler daemon'ı başlat
python -m scraper.main schedule

# Sistem sağlık kontrolü
python -m scraper.main health

# E-posta ayarlarını test et
python -m scraper.main test-email

# Eski raporları temizle
python -m scraper.main cleanup --days 30
```

## Environment Değişkenleri

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=horecemark
DB_USER=horeca
DB_PASSWORD=your_password

# E-posta (Gmail örneği)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=recipient@example.com

# Zamanlama
SCRAPE_TIME=08:00
SCHEDULER_ENABLED=true
```

## Excel Rapor İçeriği

Günlük rapor 5 sayfa içerir:

| Sayfa | İçerik |
|-------|--------|
| **Özet** | Toplam ürün, değişim sayıları, aksiyonlar |
| **Fiyat Değişiklikleri** | Ürün, site, eski/yeni fiyat, değişim %, aksiyon |
| **Stok Değişiklikleri** | Ürün, site, eski/yeni durum, mesaj |
| **Fiyat Karşılaştırma** | 6 site yan yana fiyat karşılaştırması |
| **Yeni Ürünler** | Keşfedilen yeni ürünler |

## Ürün Eşleştirme Algoritması

Multi-factor matching stratejisi:

| Faktör | Ağırlık | Açıklama |
|--------|---------|----------|
| Fuzzy Match | 60% | thefuzz ile string benzerliği |
| Brand Match | 25% | Marka eşleşmesi (+30 puan) |
| SKU Match | 10% | Model numarası (regex) |
| Capacity Match | 5% | Kapasite (4 gözlü, 900mm) |

**Eşik değiri:** 85% üzeri eşleşme kabul edilir.

## Otomasyon Seçenekleri

### 1. Docker Scheduler (Önerilen)

```bash
# .env dosyasında
SCHEDULER_ENABLED=true
SCRAPE_TIME=08:00

# Servisi başlat
docker-compose up -d
```

### 2. n8n Workflow

`n8n-workflows/daily-scrape.json` dosyasını n8n'e import edin.

### 3. Cron Job

```bash
# crontab -e
0 8 * * * cd /path/to/horecemark && ./scripts/start-scraper.sh
```

## Geliştirme

### Test Çalıştırma

```bash
pytest tests/
```

### Yeni Site Ekleme

1. `scraper/sites/new_site.py` oluştur
2. `BaseScraper` sınıfından inherit et
3. `parse_product()` ve `get_products()` metodlarını implement et
4. `scraper/utils/config.py`'e site config'i ekle

### Docker Build

```bash
docker-compose build
```

## Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| DB bağlanamıyor | `docker-compose up -d db` ile DB'yi başlat |
| Browser hatası | `playwright install chromium` komutunu çalıştır |
| E-posta gitmiyor | Gmail App Password oluştur |
| Site cevap vermiyor | Rate limit'i artır veya proxy kullan |

## Dokümantasyon

- [`AGENT.md`](AGENT.md) - Proje spesifikasyonu
- [`AUTOMATION.md`](AUTOMATION.md) - Otomasyon rehberi
- [`docs/PLAN-horeca-mark.md`](docs/PLAN-horeca-mark.md) - Implementasyon planı
- [`n8n-workflows/README.md`](n8n-workflows/README.md) - n8n kurulumu

## Lisans

MIT License
