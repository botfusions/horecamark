# HorecaMark - Coolify Deploy Talimatları

Coolify'da HorecaMark Price Intelligence sistemini çalıştırma rehberi.

## 🚀 Hızlı Deploy

### 1. GitHub'a Push Et

```bash
git init
git add .
git commit -m "Initial commit: HorecaMark Price Intelligence"
git remote add origin https://github.com/KULLANICI/horecemark.git
git push -u origin main
```

### 2. Coolify'da Proje Oluştur

1. **Coolify paneline git** → `New Project` → `From Git`
2. **Repository seç** → GitHub/horecemark
3. **Build type**: Docker Compose
4. **Compose file**: `coolify.yaml`

### 3. Environment Variables Ekle

Coolify'da projenin ayarlarından şu environment variables'ı ekle:

```
# Database
DB_NAME=horecemark
DB_USER=horeca
DB_PASSWORD=your_strong_password_here

# Email (Gmail örneği)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=recipient@example.com

# Scheduler
SCRAPE_TIME=08:00
SCHEDULER_ENABLED=true

# Logging
LOG_LEVEL=INFO
```

### 4. Deploy Et

**Deploy** butonuna tıkla. Coolify otomatik olarak:
- PostgreSQL container'ı başlatır
- Scraper container'ı build eder
- Volumes oluşturur
- Health check yapar

## 📊 Coolify Özellikleri

| Özellik | Nasıl Kullanılır |
|---------|------------------|
| **Logs görüntüle** | Proje → Logs (canlı log akışı) |
| **Console** | Proje → Execute Console → bash |
| **Restart** | Proje → Restart butonu |
| **Environment** | Proje → Variables → Edit |
| **Resource usage** | Proje → Resources (CPU/RAM) |

## 🛠️ Manuel Komutlar (Coolify Console)

Coolify'da **Execute Console** ile bash'e girip:

```bash
# İlk migrasyon
python -c "
from scraper.database import engine, Base
Base.metadata.create_all(engine)
"

# Manuel tarama test
python -m scraper.main scrape --dry-run

# Sağlık kontrolü
python -m scraper.main health

# E-posta test
python -m scraper.main test-email
```

## 🔄 Otomatik Yeniden Deploy

GitHub'da `main` branch'ine push yaparsan Coolify otomatik deploy eder.

```bash
git add .
git commit -m "Update scraper"
git push
# Coolify otomatik rebuild + redeploy
```

## 📈 Monitoring

### Coolify Resources Sekmesi

- **CPU usage** - Scraper çalışırken CPU tüketimi
- **RAM usage** - Python + Playwright bellek kullanımı
- **Disk** - PostgreSQL data büyüklüğü

### Log Kontrolü

Coolify'da **Logs** sekmesinden:
- Günlük tarama sonuçlarını gör
- Hata mesajlarını kontrol et
- Email gönderim durumunu takip et

## 🌒 Domain + SSL (Opsiyonel)

Eğer web dashboard eklersen:

1. Proje → Domains → Add Domain
2. `horecemark.senindomain.com` ekle
3. Coolify otomatik Let's Encrypt SSL alır

## 💾 Backup

Coolify'da **Volumes** sekmesinden:
- `db_data` volume'unu yedekle
- PostgreSQL export al:

```bash
# Console'da
pg_dump -U horeca horecemark > backup.sql
```

## 🐛 Troubleshooting

| Sorun | Çözüm |
|-------|-------|
| Deploy hatası | Logs sekmesinden detayları gör |
| DB bağlanamıyor | Environment variables'ı kontrol et |
| Email gitmiyor | SMTP_PASSWORD'ü (App Password) kontrol et |
| Scraper çalışmıyor | Logs'ta Playwright hatası var mı? |

## 📦 Proje Yapısı (Coolify)

```
horecemark/
├── coolify.yaml          # Coolify konfigürasyonu
├── scraper/
│   ├── Dockerfile        # Python container build
│   ├── main.py           # Ana uygulama
│   └── requirements.txt  # Bağımlılıklar
└── README.md
```

## 🎯 Sonraki Adımlar

1. ✅ GitHub'a push
2. ✅ Coolify'da proje oluştur
3. ✅ Environment variables ekle
4. ✅ Deploy et
5. 📧 İlk e-posta test et
6. 🌙 Scheduler 08:00'de çalışsın

---

**Not:** Bu proje şu an **arka plan servisi** olarak çalışıyor (web UI yok). İleri fazda web dashboard eklenebilir.
