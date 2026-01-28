# Horeca Price Intelligence Agent

Sen bir fiyat istihbarat ve otomasyon uzmanısın. Endüstriyel mutfak ekipmanları sektöründe çalışıyorsun ve 6 farklı e-ticaret sitesinden (5 rakip + 1 ana firma) günlük fiyat verisi toplayıp analiz eden bir sistem geliştiriyorsun.

## 🎯 Proje Hedefi
- 6 siteyi (CafeMarkt, AriGastro, HorecaMarkt, KariyerMutfak, Mutbex, HorecaMark) her gün 08:00'de tara
- Aynı ürünleri farklı sitelerde eşleştir (fuzzy matching)
- Fiyat değişikliklerini tespit et (geçmiş veriyle karşılaştır)
- "Fiyat düşür", "Stok fırsatı", "Rakip yok" gibi aksiyon önerileri üret
- Excel + Email raporu oluştur

## 🏗️ Teknik Mimari

### Stack
- **Scraping**: Python + Playwright (async)
- **Database**: PostgreSQL (fiyat geçmişi için)
- **Scheduler**: n8n veya Python schedule
- **Matching**: thefuzz (Levenshtein distance)
- **Container**: Docker + Docker Compose
- **Monitoring**: Basit loglama (ilk aşamada)

### Database Şeması (.sql olarak düşün)

```sql
-- Ürünler (normalize edilmiş)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    normalized_name VARCHAR(500), -- "4lu endustriyel ocak dogalgazli"
    category VARCHAR(100),
    brand VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Her sitenin ham verisi
CREATE TABLE price_snapshots (
    id SERIAL PRIMARY KEY,
    site_name VARCHAR(50), -- 'cafemarkt', 'arigastro'...
    product_id INTEGER REFERENCES products(id),
    original_name VARCHAR(500), -- Sitedeki orijinal isim
    price DECIMAL(10,2),
    currency VARCHAR(10) DEFAULT 'TRY',
    stock_status VARCHAR(50), -- 'stokta', 'tukendi', 'preorder'
    url TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(site_name, product_id, DATE(scraped_at)) -- Günde bir kayıt
);

-- Fiyat değişiklik alarmı
CREATE TABLE price_changes (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    old_price DECIMAL(10,2),
    new_price DECIMAL(10,2),
    change_percent DECIMAL(5,2),
    site_name VARCHAR(50),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_notified BOOLEAN DEFAULT FALSE
);

🕸️ Siteler ve Stratejiler
1. CafeMarkt (cafemarkt.com)
Tip: Özel yazılım (muhtemelen .NET veya PHP)
URL Pattern: /endustriyel-[kategori], /[urun-adi]-p-[id]
Selectorlar:
Ürün listesi: .product-item, .product-card
İsim: h3.product-name, .product-title
Fiyat: .current-price, span[itemprop="price"]
Sayfalama: Infinite scroll (JavaScript lazy loading)
Taktik: Scroll ile 20-30 ürün yükle, "daha fazla" butonu varsa tıkla
2. AriGastro (arigastro.com)
Tip: WooCommerce (WordPress)
Taktik:
Önce /wp-json/wc/v3/products endpoint'ini dene (API erişimi olabilir)
Yoksa: product.type-product class'larından çek
Kategoriler: /kategori/xxx veya /product-category/xxx
3. HorecaMarkt (horecamarkt.com.tr)
Tip: Shopify veya özel tema
Taktik:
site.com/products.json?limit=250 denenebilir (Shopify trick)
Değilse: grid-item, product-grid-item gibi class'lar ara
Fiyat: .money, .price gibi generic selectorlar
4. KariyerMutfak (kariyermutfak.com)
Tip: Özel yazılım (Türk yapımı)
Taktik:
Sitemap.xml'den kategori URL'leri çek (genelde çalışır)
Sayfalama klasik: ?page=2, ?p=3
Ürün: .product, .urun-kart
5. Mutbex (mutbex.com)
Tip: Shopify (yüksek ihtimal)
Taktik:
/collections/all/products.json dene
Product object'lerini parse et (JSON daha kolay)
6. HorecaMark (Kendi Site - horecamark.com)
Tip: WooCommerce veya özel
Veri Kaynağı:
Admin panelden CSV/XML export alıp import et (scraping yapma, veri zaten senin)
Veya WooCommerce REST API kullan (/wp-json/wc/v3/products)
Strateji: Bu site "referans" olarak kullanılacak. Diğerleri bununla kıyaslanacak.
🔍 Ürün Eşleştirme Algoritması (Kritik!)
Her sitede aynı ürün farklı isimlerde olabilir:
CafeMarkt: "4 Gözlü Endüstriyel Ocak - Doğalgazlı - Çelik"
AriGastro: "Endüstriyel Kuzine 4 Burner - Heavy Duty"
Aynı SKU: Örneğin marka	Model: "Fagor CG9-41" gibi bir SKU olabilir
Eşleştirme Stratejisi:
Özelleştirilmiş Normalize
Python
Copy
def normalize(name):
    # Küçük harf
    # Stop words kaldır: "endüstriyel", "profesyonel", "ticari", "adet"
    # Rakamları koru: "4", "6", "900" (önemli!)
    # Özel karakterleri temizle
    # Marka isimlerini ayır (Fagor, Öztiryakiler, Rational...)
    return keywords
Multi-Factor Matching
Python
Copy
def match_product(candidate_name, existing_products):
    scores = []
    
    # 1. Fuzzy string matching (thefuzz)
    fuzz_score = fuzz.ratio(normalize(candidate), normalize(existing))
    
    # 2. Marka eşleşmesi (varsa +30 puan)
    brand_match = extract_brand(candidate) == extract_brand(existing)
    
    # 3. Model/SKU numarası eşleşmesi (regex ile)
    sku_pattern = r'\b[A-Z]+[-]?\d+\b'  # CG9-41, TL900, etc.
    sku_match = bool(re.search(sku_pattern, candidate))
    
    # 4. Kapasite eşleşmesi (4 gözlü, 900mm, vs)
    capacity_match = extract_numbers(candidate) == extract_numbers(existing)
    
    total_score = weighted_average(...)
    return total_score > 85  # Eşik değer
Manuel Override (İlk kurulumda)
İlk çalıştırmada eşleşmeyenleri listeleyip CSV olarak ver
Kullanıcı (sen) elle eşleştirme yaparsın (product_mappings tablosu)
Sonraki taramalarda bu mapping kullanılır
📊 Değişiklik Tespiti (Diff System)
Sadece rapor değil, ne değişti takibi:
Python
Copy
def detect_changes(new_data):
    for product in new_data:
        # Dünkü fiyatı çek
        yesterday_price = get_last_price(product.id, yesterday)
        
        if yesterday_price:
            change_pct = ((new_price - yesterday_price) / yesterday_price) * 100
            
            if abs(change_pct) > 5:  # %5'ten fazla değişiklik
                log_change(product, old, new, change_pct)
                
                # Aksiyon önerisi
                if change_pct < -10:
                suggestion = "🔴 Rakip fiyatı düşürmüş! Sen de düşür veya farklılaştır."
                elif change_pct > 10:
                suggestion = "🟡 Rakip fiyat artırmış. Sen de yükselt, marjı koru."
🚨 Özel Durumlar (Edge Cases)
Stok Durumu Değişimi:
Dün "Stokta yok" → Bugün "Stokta var" = Fırsat (rakip bitmiş, sen varsin)
Tersi: Uyarı (senin ürün bitmiş)
Yeni Ürün Tespiti:
Sitede yeni eklenen ürünü tespit et (önceki taramada yoktu)
"Yeni ürün eklendi" raporuna koy
Sayfa Hatası / Blok:
403/503 hatası alırsa o siteyi atla, diğerlerine devam et
Log'a yaz, sonraki taramada tekrar dene
Rate limiting: Her site arası 2-5 saniye bekle
📁 Dosya Yapısı (Hedef)
Copy
horeca-price-bot/
├── docker-compose.yml
├── scraper/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py (Sitelerin selectorları)
│   ├── database.py (PostgreSQL bağlantısı)
│   ├── main.py (Ana döngü)
│   ├── sites/ (Her site için ayrı modül)
│   │   ├── cafemarkt.py
│   │   ├── arigastro.py
│   │   ├── horecamarkt.py
│   │   ├── kariyermutfak.py
│   │   ├── mutbex.py
│   │   └── horecamark.py
│   └── utils/
│       ├── matcher.py (Ürün eşleştirme)
│       ├── notifier.py (Email/Slack bildirim)
│       └── reporter.py (Excel rapor)
└── n8n-workflows/ (JSON exportları)
📝 İlk Yapılacaklar (Priorite)
Veritabanını kur (PostgreSQL Docker)
Tek site tara (CafeMarkt ile başla - en zor olanı)
Eşleştirme algoritmasını test et (10-20 ürün üzerinde)
Kendi siteni import et (CSV veya API ile)
Diğer 4 siteyi ekle (paralel)
Raporlama ve diff sistemini ekle
🤖 Şu An Yapmanı İstediğim
Benim için şu dosyayı oluştur:
docker-compose.yml (PostgreSQL + Python scraper container)
database.py (Yukarıdaki SQL şemasını Python SQLAlchemy ile oluşturacak script)
cafemarkt.py (CafeMarkt için temel scraper - tek bir kategori testi)