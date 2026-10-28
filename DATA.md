# Hoop Grid — Veri Belgesi

Oyunun kullandığı oyuncu verisinin nereden geldiği, nasıl üretildiği, ızgara kriterlerine nasıl
dönüştüğü, hangi kurallarla birleştirildiği ve bilinen eksikleri. Son güncelleme: 29 Ekim 2026.

---

## 1. Özet

| | NBA | EuroLeague |
|---|---|---|
| Dosya | `backend/data/nba_data.json` | `backend/data/euroleague_data.json` |
| Oyuncu | 4.918 | 2.372 |
| Kriter takımı | 30 franchise | 23 kulüp |
| Ülke | 88 | 81 |
| Ülkesi boş oyuncu | 171 | 13 |
| Oyuncu başına takım (ortalama) | 2,67 | 1,83 |
| Ödüllü oyuncu | şampiyon 461, All-NBA 227, ROY 73, MIP 40, MVP 37, Finals MVP 36, 6MOY 35, DPOY 26 | şampiyon 308, Final Four 752 |
| Draft bilgisi / kolej / sezon aralığı | 2.112 / 1.920 / 4.193 | — / — / 2.348 |
| Kariyer istatistiği | — | 2.027 |

İki dosya da `backend/scripts/build_databases.py` ile üretilir. Elle düzenlenmez; düzeltme
gerekiyorsa builder'daki tablolara (alias, override) eklenir ve dosyalar yeniden üretilir.

---

## 2. Dosya şeması

```json
{
  "league": "NBA",
  "teams": ["Los Angeles Lakers", "..."],
  "countries": ["Argentina", "..."],
  "players": [
    {
      "name": "Kareem Abdul-Jabbar",
      "country": "USA",
      "teams": ["Los Angeles Lakers", "Milwaukee Bucks"],
      "seasons": [1970, 1989],
      "awards": ["all_nba", "champion", "finals_mvp", "mvp", "roy"],
      "draft": {"round": 1, "pick": 1},
      "college": "UCLA"
    }
  ]
}
```

Yalnızca `name`, `country`, `teams` her oyuncuda vardır; diğer alanlar bilinmiyorsa yazılmaz.

| Alan | Anlamı |
|---|---|
| `teams` | Oynadığı **franchise/kulüpler**, güncel adlarıyla. EuroLeague'de kriter olmayan eski kulüpler de durur (Unicaja, Cibona…). |
| `country` | **Doğum ülkesi** (§6.1). Bilinmiyorsa `""`; o oyuncu hiçbir ülke kriterine uymaz. |
| `seasons` | `[ilk, son]` sezon; sezon bittiği yılla adlandırılır (2024-25 → `2025`). EuroLeague de aynı kurala çevrilir. |
| `awards` | NBA: `champion`, `mvp`, `finals_mvp`, `all_nba`, `roy`, `dpoy`, `sixth_man`, `mip`. EL: `champion`, `final_four`. |
| `draft` | NBA draft'ı: `round` 1/2 ve tur içi `pick`; `round: 0` draft edilmemiş. Yoksa bilinmiyor. |
| `college` | NBA öncesi kolej. Liseden NBA'e gelenlerde yok. |
| `stats` | EuroLeague kariyer toplamları: `games`, `points`, `rebounds`, `assists` (2000-01'den beri). |

İsimler ASCII'dir (`Luka Doncic`, `Aleksandar Dordevic`); arama küçük harf alt dize eşleşmesidir.
Aynı adlı farklı oyuncular ayrı kayıttır (Mike James, Glen Rice…); oyun kareye uyanı kabul eder.

---

## 3. Izgara kriterleri

Kriterler veriden `backend/catalog/criteria.py` içinde üretilir. Her biri bir `CriterionSpec`'tir:
tür, değer, başlık, yanlış cevaptaki açıklama ve oyuncuyu sınayan fonksiyon. Yeni bir kriter türü
için yalnızca bu dosyaya bir builder eklemek yeter; tahta üretici ve oyun yöneticisi türden
habersizdir.

| Tür | NBA | EuroLeague |
|---|---|---|
| `team` | 30 franchise | 23 kulüp |
| `country` | en az 3 oyuncusu olan doğum ülkeleri | aynı |
| `college` | en az 20 oyuncusu olan kolejler (24 tane) | — |
| `draft` | #1 overall, ilk 10, ikinci tur, draft edilmemiş | — |
| `award` | NBA şampiyonu, MVP, Finals MVP, All-NBA, ROY, DPOY, 6MOY, MIP | EL şampiyonu, Final Four oynamış |
| `career` | 5+ franchise | 1.000+ sayı, 150+ maç, 300+ asist, 500+ ribaund, 3+ kulüp |
| `era` | 1960–69 … 2020–29 arasında oynamış | 2000–09, 2010–19, 2020–29 |

- **Tek değerli türler** (ülke, kolej, ikinci tur / draft edilmemiş) karşılıklı satır-sütunda
  buluşamaz; üretici bunları baştan eler.
- **Dönem**: sezonun başladığı yıl sayılır; 1989-90 sezonu 1980'lere girer.
- **Izgara tipi**: *Klasik* yalnızca takım + doğum ülkesi; *Karışık* (varsayılan) sütunları çoğunlukla
  takım tutar, satırlara 2–3 farklı türden kriter koyar (`backend/game/board.py`). Her kutuda en az
  "valid answers per box" kadar cevap aranır; bulunamazsa eşik düşürülür, en son klasiğe dönülür.

---

## 4. Kaynaklar

### NBA

| Kaynak | Ne alınıyor | Kapsam | Lisans |
|---|---|---|---|
| [Basketball GM topluluk rosterları](https://github.com/alexnoob/BasketBall-GM-Rosters) | İsim, doğum yılı, doğum yeri, kolej, draft, sezon takımı; 2019-20 sonrası dosyalarda tüm kariyerin `stats` geçmişi (sezon ortası takaslar, playoff'lar); 2022-23 sonrası dosyalarda 1947'den beri **lig ödülleri** (MVP, Finals MVP, ROY, DPOY, 6MOY, MIP, All-NBA) ve **playoff serileri** | 1995-96, 2009-10, 2015-16 … 2025-26 | **Belirtilmemiş** (§8) |
| ESPN kadro uç noktası `site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{id}/roster` | Güncel sezon kadroları, doğum tarihi/yeri, kolej. Snapshot'lar bir sezon geride olduğu için yaz transferleri buradan gelir (Marcus Smart → Houston, LeBron James → Philadelphia, Temmuz 2026) | Yalnızca güncel sezon | Resmî olmayan, anahtarsız (§8) |
| [FiveThirtyEight nba-player-advanced-metrics](https://github.com/fivethirtyeight/nba-player-advanced-metrics) `nba-data-historical.csv` | Oyuncu-sezon-takım satırları (normal sezon ve playoff ayrı), yaş | 1977 – 2020 | CC BY 4.0 (README'de atıf var) |
| [Wikidata](https://query.wikidata.org) SPARQL | Basketbolcu mesleğindeki (P106) kişilerin takım üyelikleri (P54, başlangıç P580, bitiş P582), doğum tarihi, doğum yeri ülkesi, koç mesleği | 1940'lardan bugüne, düzensiz | CC0 |

### EuroLeague (resmî API, anahtarsız)

| Uç nokta | Ne alınıyor |
|---|---|
| `/v2/competitions/E/seasons/E{yıl}/people?personType=J&limit=2000` | Sezon kayıtları: kod, isim, doğum tarihi/ülkesi, uyruk, kulüp (sezon ortası transferler ayrı kayıt). Varsayılan 500 kayıtta keser; 2001-02'de 527 kayıt var. |
| `/v2/competitions/E/seasons/E{yıl}` | Sezon şampiyonu (`winner`); 2019-20 iptal |
| `/v2/competitions/E/seasons/E{yıl}/games` | Final Four maçları (`phaseType.code == "FF"`) ve kulüpleri |
| `/v3/competitions/E/statistics/players/traditional?SeasonMode=Range&…&statisticMode=Accumulated` | Tek çağrıda tüm oyuncuların 2000'den bu yana kariyer toplamları |

Builder'ın tek bağımlılığı Python standart kütüphanesidir.

---

## 5. Üretim hattı

```bash
python backend/scripts/build_databases.py                             # ikisi, backend/data'ya yazar
python backend/scripts/build_databases.py --league nba --out /tmp/x   # deneme çıktısı
HOOPGRID_DATA_DIR=/tmp/x uvicorn backend.app:app --port 8001          # deneme verisiyle sunucu
```

Önce başka bir klasöre üretip karşılaştırmak önerilir. Oyuncular isme, aynı adlılar takımlarına
göre sıralanır; böylece kaynaklar değişmediyse iki çıktı arasındaki fark gerçek veri farkıdır.

### 5.1 Modüller (`backend/scripts/builder/`)

| Modül | Görev |
|---|---|
| `common.py` | HTTP, isim anahtarları, aksan temizleme, ülke adları, doğum yeri çözümleme, dosya yazımı |
| `nba_teams.py`, `euroleague_clubs.py` | Franchise/kulüp listeleri ve tüm eski adların eşlemesi |
| `sources/bbgm.py`, `espn.py`, `fivethirtyeight.py`, `wikidata.py`, `euroleague_api.py` | Her dış kaynak için bir modül; yalnızca veri çeker ve ayrıştırır |
| `nba.py` | NBA hattı: her gerçek oyuncu için bir `Person` kaydı, kaynaklar sırayla ekleme yapar |
| `euroleague.py` | EuroLeague hattı |

### 5.2 NBA adımları (`nba.py`)

1. **Roster snapshot'ları**: oyuncunun sezon-takım kayıtları (mevcut takım + `stats` geçmişi,
   playoff bayrağıyla), doğum yeri, kolej, draft ve oyuncu bazlı "Won Championship" ödülleri.
   Hiç NBA takımı olmayanlar (draft adayları) atlanır. **2009-10 dosyası bozuktur**: doğum
   yılları ~9 yıl kaymış, doğum yerleri çoğunlukla üniversite adı; doğum yılı FiveThirtyEight'ten
   alınır, draft bilgisi en düşük öncelikli sayılır.
2. **ESPN güncel kadroları** eklenir. ESPN'in doğum ülkesi en düşük önceliklidir (bazen milli
   takımı yazar: New York doğumlu Mamukelashvili → Georgia). Görünen isimde bilinen roster
   yazılışı kalır (`Ron Holland II`, ESPN'in `Ronald Holland II`'si değil).
3. **Kopya birleştirme** (`merge_roster_duplicates`): aynı isim ve doğum yılı farkı ≤ 2;
   Jr./II eki farkı ve yıl farkı ≤ 1; soyadı uzaması (`Timothe Luwawu` → `-Cabarrot`) + ortak takım;
   kısaltılmış ön ad (`Svi` / `Sviatoslav`, `Mo` / `Mohamed Bamba`) + aynı soyad + ortak takım.
   İsim karşılaştırması aksan, nokta, kesme işareti ve aralıklı baş harfleri yok sayar
   (`R.J.` = `RJ`, `A. C. Green` = `A.C. Green`).
4. **FiveThirtyEight kariyerleri**: (eksiz isim, doğum yılı) tek oyuncuya denk geliyorsa 1977–2020
   sezon-takım-playoff kayıtları eklenir.
5. **Wikidata eşleşmesi** (isim + doğum yılı ±1, herhangi bir yazılışla, tek aday): doğum ülkesi,
   1977 öncesi tarihli takımlar ve bitiş yılı bilinen sezon aralıkları.
6. **Doğum ülkesi** çözülür (§6.1).
7. **Yalnızca Wikidata'da olanlar** (çoğu 1995 öncesi emekli): 1977 sonrası takımları
   FiveThirtyEight'ten, öncesi Wikidata'dan. Aynı isimli ve doğum yılı ±3 içindeki bir oyuncu
   zaten varsa aynı kişi sayılıp atlanır.
8. **Yalnızca FiveThirtyEight'te olanlar** (Reggie Jordan gibi, 150 oyuncu): doğum yeri
   bilinmediği için ülkesi boş kalır.
9. **Lig ödülleri**: kazanan isimle eşleşir; aynı isimli birden çok oyuncu varsa ödülü aldığı
   franchise'a göre, isim hiç tutmazsa soyadı + o sezon o franchise'da oynamış olmaya göre
   (`Anfernee` / `Penny Hardaway`).
10. **Şampiyonluk**: playoff serilerinden her sezonun şampiyon franchise'ı çıkarılır; oyuncu o sezon
    o takımda **playoff** kaydı varsa şampiyon sayılır. 1977 öncesinde playoff bayrağı yoktur,
    Wikidata sezon aralığı yeterlidir.

> Önceki sürümdeki "eski veri dosyasından taşıma" adımı NBA'den kaldırıldı: kaynaklar artık
> tam olduğu için yalnızca eski hataları (oyuncu sanılan koçlar) kalıcılaştırıyordu.

### 5.3 EuroLeague adımları (`euroleague.py`)

1. 2000'den bugüne her sezonun kayıtları çekilir; kişi anahtarı normalize isim + doğum tarihi.
2. Kulüp adları **birebir** alias tablosuyla normalize edilir ("Ulker" Ülkerspor'dur,
   "Fenerbahce Ulker" Fenerbahçe'dir; "Skipper Bologna" Fortitudo'dur, Virtus değil).
3. Şampiyonluk ve Final Four: oyuncu o sezon şampiyon / Final Four kulübüne kayıtlıysa.
4. Kariyer toplamları oyuncu koduyla bağlanır (iki koda kayıtlı oyuncularda toplanır).
5. En az bir kriter kulübünde oynamış oyuncular alınır.
6. Önceki dosyadaki elle girilmiş 2000 öncesi efsaneler korunur (24 oyuncu).

---

## 6. Kurallar

### 6.1 Ülke = doğum ülkesi
Her iki ligde ülke **doğduğu ülke**dir (Kyrie Irving → Australia, Domantas Sabonis → USA).
Kurallar penceresinde ve README'de yazılıdır.

- EuroLeague: `birthCountry`, yoksa `country` (uyruk çoğu zaman ikinci pasaporttur: Ginóbili İtalyan,
  Scola İspanyol görünür).
- NBA öncelik sırası:
  1. `NBA_COUNTRY_OVERRIDES` (elle; Wikidata'dan gelenler dahil herkesi ezer),
  2. roster doğum yeri; Wikidata farklı **yabancı** ülke diyorsa Wikidata (Pekovic: Montenegro),
     roster boşsa Wikidata,
  3. roster "USA" ↔ Wikidata yabancı ülke çatışmasında roster kalır, build çıktısında listelenir.
     Wikidata bazı ABD doğumluları aynı adlı yabancı kasabaya bağlıyor (Kendall Gill → Paisley,
     Bobby Jackson → Salisbury/İngiltere, Matt Carroll → Horsham/Avustralya),
  4. yedekler: EuroLeague doğum ülkesi → önceki veri (USA/Georgia hariç) → roster'da üniversite
     adı varsa USA → boş.
- Wikidata Porto Riko ve ABD Virjin Adaları'nı USA'ya bağlar; roster bu bölgeleri söylüyorsa
  roster kalır (Tim Duncan → U.S. Virgin Islands).

### 6.2 Takım = franchise soyu
- Eski adlar bugünkü franchise'a sayılır: Seattle SuperSonics → Oklahoma City, Vancouver → Memphis,
  New Jersey Nets → Brooklyn, Bullets → Wizards, Buffalo Braves / San Diego Clippers → LA Clippers,
  Cincinnati / Kansas City Kings → Sacramento, Syracuse Nationals → 76ers, Philadelphia Warriors →
  Golden State, St. Louis Hawks → Atlanta.
- 1988–2002 Charlotte Hornets → **Charlotte Hornets**; 2002–2013 New Orleans Hornets → Pelicans.
- Kapanmış franchise'lar (1940'ların Baltimore Bullets'ı, Washington Capitols…) kriter değildir;
  şampiyonlukları da hiçbir franchise'a yazılmaz.
- Wikidata'nın 1977 öncesi kayıtlarında ABA dönemi de franchise'a sayılır (Dr. J'nin Nets yılları).

### 6.3 Draft ve kolej
- `pick` tur içi sıradır (Jokić: 2. tur 11. seçim). "İlk 10" = 1. tur, 1–10.
- Draft verisi yalnızca roster snapshot'larında var; yalnızca Wikidata veya FiveThirtyEight'ten
  gelen eski oyuncuların draft'ı bilinmez ve draft kriterlerine uymaz.
- Kolej: roster ve ESPN. Ülke adı yazılmışsa (yabancı oyuncular) veya bir kayıtta lise görünüyorsa
  ("St. Vincent–St. Mary HS") kolej yok sayılır. ESPN/roster ad farkları `COLLEGE_ALIASES` ile
  birleştirilir (UConn → Connecticut, LSU → Louisiana State…).

### 6.4 EuroLeague kriter kulüpleri
20 köklü kulüp + 2026-27'de ligde olan Beşiktaş, Dubai Basketball, Hapoel Tel Aviv. Görünen adlar
eski sürümle uyum için korunmuştur ("EA7 Emporio Armani Milan", "Virtus Segafredo Bologna").

---

## 7. Bilinen eksikler

- **Erken dönem ödülleri**: lig ödül listesindeki 71 kazanan (çoğu 1950'ler: Dolph Schayes, Slater
  Martin…) veride yok ya da tek oyuncuya bağlanamıyor. MVP'lerin 37'si eşleşti.
- **All-Star** kriteri yok: kaynakta yalnızca son yıllarda oynayanların All-Star geçmişi var;
  eski oyuncuları haksız yere reddederdi. Aynı sebeple sayı/ribaund/asist krallığı yok.
- **Maçta 50+ sayı** gibi maç bazlı NBA kriterleri: hiçbir kaynakta NBA maç verisi yok.
- **EuroLeague MVP**: API'de ödül uç noktası yok, Wikidata yalnızca 2014'e kadar.
- **Draft ve kolej** yalnızca roster'larda görünen oyuncular için (draft 2.112, kolej 1.920 oyuncu).
- **Ülkesi boş 171 NBA oyuncusu**: çoğu yalnızca FiveThirtyEight'te olan 1977–2020 oyuncuları.
- **Wikidata'dan gelen ~2.600 oyuncunun ülkesi** çapraz kontrol edilemiyor; yanlış kasaba hatası
  kalmış olabilir (bulunanlar override tablosunda).
- **Oyuncu-koçlar**: Wikidata'da oyunculuk dönemi tarihsizse (Pat Riley) veri dışında kalırlar.
- **Güncel sezon**: ESPN kadrosu çekildiği anı yansıtır; sezon içi takaslar için betik periyodik
  çalıştırılmalı (sunucuya geçince günlük cron planlanıyor).
- **EuroLeague isimleri** resmî kayıt adıdır ("Emanuel Ginobili"); 2000-01'de doğum ülkesi ~%32 boş.
- İsim değiştiren oyuncu ayrı kayıt olabilir (Bobby Dixon / Ali Muhammed).

---

## 8. Lisans durumu

- **Wikidata**: CC0, serbest.
- **FiveThirtyEight**: CC BY 4.0, kaynak gösterilmeli (README "Data Sources").
- **EuroLeague API**: yayımlanmış kullanım şartı bulunamadı; ticari kullanımdan önce kontrol edilmeli.
- **ESPN kadro uç noktası**: belgelenmemiş, anahtarsız; yalnızca oyuncu-takım-doğum yeri gerçekleri
  alınıyor. ESPN'in genel kullanım şartları otomatik erişimi kısıtlayabilir.
- **Basketball GM rosterları**: lisans belirtilmemiş ve büyük olasılıkla ZenGM'in gerçek oyuncu
  verisinden türetilmiş. ZenGM'in [lisansı](https://raw.githubusercontent.com/zengm-games/zengm/master/LICENSE.md)
  "This project is not open source!" der. Ödül ve playoff geçmişi de artık bu kaynaktan geliyor;
  projeyi yayımlamadan önce izin alınmalı ya da temiz bir kaynağa (nba_api) geçilmeli.

---

## 9. Değerlendirilen diğer NBA kaynakları

| Kaynak | Artı | Eksi |
|---|---|---|
| nba_api / stats.nba.com | Draft, ödüller, kariyer istatistikleri | Bot kontrolü ve bulut IP engeli; oyuncu başına çağrı (~1,5 saat); veri NBA.com şartlarına tabi |
| ZenGM real-player-data | En tam veri (1947+) | Lisans dağıtımı yasaklıyor |
| Basketball-Reference | Referans kalitesi | Kullanım şartları otomatik erişimi yasaklıyor |
| balldontlie | Kolay API | Anahtar zorunlu, ücretsiz planda dakikada 5 istek |
| Kaggle "NBA Database" (wyattowalsh) | nba_api'den üretilmiş hazır tablolar | Ödül tablosu yok, lisans/güncellik doğrulanmadı |

---

## 10. EuroLeague API'sinde henüz kullanılmayan veriler

| Veri | Uç nokta | Kriter fikri |
|---|---|---|
| Maç bazında oyuncu istatistiği | `/v3/competitions/E/seasons/E{yıl}/games/{kod}/stats` (2000–) | "Maçta 30+ sayı" (sezon başına ~300 çağrı) |
| Sezon liderleri | `/v2/competitions/E/stats/players/leaders` | sezon sayı kralı |
| Koçlar, hakemler | `.../people?personType=E`, `/referees` | koç kriteri |
| Sayı sayı akış, şut koordinatları | `https://live.euroleague.net/api/PlaybyPlay`, `/Points` (2007–) | — |
| EuroCup | aynı uç noktalar, yarışma kodu `U` (2002–) | ikinci mod |
