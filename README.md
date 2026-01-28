# HorecaMark Price Intelligence - Coolify Deployment Guide

## 📋 İçindekiler
- [Konteyner Başlatma Sorunu Çözümü](#konteyner-başlatma-sorunu-çözümü)
- [Environment Variables Yapılandırması](#environment-variables-yapılandırması)
- [Supabase Database Entegrasyonu](#supabase-database-entegrasyonu)
- [Sağlık Kontrolü](#sağlık-kontrolü)
- [Test Komutları](#test-komutları)

---

## 🔧 Konteyner Başlatma Sorunu Çözümü

### Tespit Edilen Sorunlar

#### 1. Migrations Klasörü Kopyalanmamış
**Sorun:** `database/migrations` klasörü Dockerfile'da kopyalanmamıştı.
**Çözüm:** Dockerfile'a migrations klasörünü kopyalayan satır eklendi.

```dockerfile
# Copy database migrations
COPY database/migrations /app/migrations
```

#### 2. Playwright Kurulum Hatası
**Sorun:** Debian Trixie kullanılıyordu ve Playwright bu sürümü resmi olarak desteklemiyordu.
**Çözüm:** Dockerfile'da Debian sürümü Bookworm (stable) olarak değiştirildi.

```dockerfile
FROM python:3.11-bookworm
```

#### 3. Veritabanı Bağlantı Hatası
**Sorun:** Scraper konteyneri `db` hostname'ini çözemiyordu.
**Çözüm:** Supabase database kullanılarak external database bağlantısı sağlandı.

---

## 🔑 Environment Variables Yapılandırması

### Coolify'da Environment Variables

Coolify panelinde **Application** → **Environment Variables** sekmesine gidin ve şu değerleri girin:

| Değişken | Değer | Açıklama |
|----------|-------|------------|
| `DATABASE_URL` | `postgresql://postgres:oKyh9Ml0EERnI1TZ@db.rfwwntmaktyunbbqdtkq.supabase.co:5432/postgres` | Tam database bağlantı string'i |
| `DB_HOST` | `db.rfwwntmaktyunbbqdtkq.supabase.co` | Database host adresi |
| `DB_PORT` | `5432` | Database portu |
| `DB_NAME` | `postgres` | Database adı |
| `DB_USER` | `postgres` | Database kullanıcı adı |
| `DB_PASSWORD` | `oKyh9Ml0EERnI1TZ` | Database şifresi |

### Email Yapılandırması (Opsiyonel)

| Değişken | Değer | Açıklama |
|----------|-------|------------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP sunucusu |
| `SMTP_PORT` | `587` | SMTP portu |
| `SMTP_USER` | `email@example.com` | Email kullanıcı adı |
| `SMTP_PASSWORD` | `uygulama_şifresi` | Email şifresi |
| `EMAIL_FROM` | `noreply@example.com` | Gönderen email |
| `EMAIL_TO` | `rapor@example.com` | Alıcı email |

### Diğer Yapılandırmalar (Opsiyonel)

| Değişken | Varsayılan | Açıklama |
|----------|------------|------------|
| `SCRAPE_TIME` | `08:00` | Tarama saati |
| `SCHEDULER_ENABLED` | `true` | Zamanlayıcı açık |
| `LOG_LEVEL` | `INFO` | Log seviyesi |

---

## 🗄️ Supabase Database Entegrasyonu

### Supabase Connection String Alma

1. Supabase paneline gidin: https://supabase.com
2. Projenizi seçin
3. **Settings** → **Database** sekmesine gidin
4. **Connection string** → **Copy** butonuna tıklayın

### Tam Connection String

```
postgresql://postgres:oKyh9Ml0EERnI1TZ@db.rfwwntmaktyunbbqdtkq.supabase.co:5432/postgres
```

---

## 🏥 Sağlık Kontrolü

### Konteyner İçinde Sağlık Kontrolü

VPS terminalinde:

```bash
# Konteyner ID'sini bul
docker ps

# Sağlık kontrolü
docker exec <konteyner_id> python -m scraper.main health
```

### Beklenen Çıktı

```
=== HorecaMark Sistem Durumu ===

Zaman damgasi:  2026-01-28T19:01:25.825094
Veritabani:     ok
Son scraping:   2026-01-28T18:00:00.000000
Toplam urun:    1000

Siteler:
  - CafeMarkt: configured
  - AriGastro: configured
  - HorecaMarkt: configured
  - KariyerMutfak: configured
  - Mutbex: configured
  - HorecaMark: configured
```

---

## 🧪 Test Komutları

### Email Testi

```bash
docker exec <konteyner_id> python -m scraper.main test-email
```

### Tek Site Testi (Dry-Run)

```bash
docker exec <konteyner_id> python -m scraper.main scrape --site cafemarkt --dry-run
```

### Tam İş Akışı

```bash
docker exec <konteyner_id> python -m scraper.main run
```

### Konteyner Loglarını İzleme

```bash
docker logs -f <konteyner_id>
```

### Environment Variables Kontrolü

```bash
docker exec <konteyner_id> env | grep DB_
```

---

## 📝 Yapılan Değişiklikler

### Dockerfile
- ✅ Debian sürümü Trixie'den Bookworm'a değiştirildi
- ✅ `database/migrations` klasörü kopyalama eklendi
- ✅ Playwright için gerekli sistem kütüphaneleri eklendi

### Environment Variables
- ✅ Supabase database bağlantı bilgileri eklendi
- ✅ Email konfigürasyonu hazırlandı

---

## 🚀 Deployment Adımları

1. **Dockerfile** güncellendi (migrations + Playwright düzeltmeleri)
2. **Coolify'da Environment Variables** ayarlandı (Supabase database)
3. **Application → Redeploy** ile konteyner yeniden başlatıldı
4. **Sağlık kontrolü** ile sistem durumu doğrulandı

---

## 📞 Destek

Sorun yaşarsanız:
1. Konteyner loglarını kontrol edin: `docker logs -f <konteyner_id>`
2. Sağlık kontrolü yapın: `docker exec <konteyner_id> python -m scraper.main health`
3. Environment variables'ları doğrulayın: `docker exec <konteyner_id> env | grep DB_`
