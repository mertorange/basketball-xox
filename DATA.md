# Hoop Grid — Veri Belgesi

Oyunun kullandığı oyuncu verisinin nereden geldiği, nasıl üretildiği, hangi kurallarla
birleştirildiği ve bilinen eksikleri. Son güncelleme: 28 Ekim 2026.

---

## 1. Özet

| | NBA | EuroLeague |
|---|---|---|
| Dosya | `backend/data/nba_data.json` | `backend/data/euroleague_data.json` |
| Oyuncu | 4.756 | 2.372 |
| Kriter takımı | 30 franchise | 23 kulüp |
| Ülke | 89 | 81 |
| Ülkesi boş oyuncu | 23 | 13 |
| Oyuncu başına takım (ortalama) | 2,71 | 1,83 |
| Kriter takımı başına oyuncu | 265 – 575 | 25 – 259 |

İki dosya da `backend/scripts/build_databases.py` ile üretilir. Elle düzenlenmez; düzeltme
gerekiyorsa betikteki tablolara (alias, override) eklenir ve dosyalar yeniden üretilir.

---

## 2. Dosya şeması

```json
{
  "league": "NBA",
  "teams": ["Los Angeles Lakers", "..."],
  "countries": ["Argentina", "..."],
  "players": [
    { "name": "Andrei Kirilenko", "country": "Russia",
      "teams": ["Brooklyn Nets", "Minnesota Timberwolves", "Utah Jazz"] }
  ]
}
```

- `teams`: ızgara kriteri olabilecek takımlar. Tahta yalnızca bunlardan seçilir.
- `countries`: oyuncularda geçen boş olmayan ülkeler; ülke kriterleri buradan seçilir.
- `players[].teams`: oyuncunun oynadığı **franchise/kulüpler** (güncel adlarıyla). EuroLeague'de
  kriter listesinde olmayan eski kulüpler de durur (Unicaja, Darüşşafaka, Cibona…); bilgi
  amaçlıdır, kriter olmazlar.
- `players[].country`: **doğum ülkesi** (bkz. §5.1). Bilinmiyorsa `""`; böyle oyuncular hiçbir
  ülke kriterine uymaz.
- İsimler ASCII'dir (`Luka Doncic`, `Drazen Petrovic`); arama küçük harf alt dize eşleşmesidir.

Oyun motoru (`backend/game_engine.py`) bir oyuncuyu kabul ederken takım için
`teams` içinde birebir ad, ülke için `country` eşitliği arar. Aynı adı taşıyan iki oyuncu varsa
(NBA: Mike James, Reggie Williams; EL: Marko Simonovic, Pape Sow) kareye uyan kabul edilir.

---

## 3. Kaynaklar

### NBA

| Kaynak | Ne alınıyor | Kapsam | Lisans |
|---|---|---|---|
| [Basketball GM topluluk rosterları](https://github.com/alexnoob/BasketBall-GM-Rosters) | İsim, doğum yılı, doğum yeri, sezon takımı; 2019-20 sonrası dosyalarda oyuncunun `stats[].tid` takım geçmişi (sezon ortası takaslar dahil) | 1995-96, 2009-10, 2015-16 … 2025-26 | **Belirtilmemiş** (bkz. §7) |
| ESPN kadro uç noktası `site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{id}/roster` | Güncel sezonun (2026-27) kadroları: isim, doğum tarihi, doğum yeri, takım. Topluluk snapshot'ları bir sezon geriden geldiği için yaz transferleri (Marcus Smart → Houston, Temmuz 2026) buradan gelir | Yalnızca güncel sezon | Resmî olmayan, anahtarsız uç nokta; yayımlanmış kullanım şartı yok (bkz. §7) |
| [FiveThirtyEight nba-player-advanced-metrics](https://github.com/fivethirtyeight/nba-player-advanced-metrics) `nba-data-historical.csv` | Oyuncu-sezon-takım satırları, yaş | 1977 – 2020 | CC BY 4.0 (README'de atıf var) |
| [Wikidata](https://query.wikidata.org) SPARQL | Takım üyelikleri (P54 + başlangıç P580), doğum tarihi (P569), doğum yeri ülkesi (P19→P17), koç mesleği (P106) | 1940'lardan bugüne, düzensiz | CC0 |

### EuroLeague

| Kaynak | Ne alınıyor | Kapsam | Lisans |
|---|---|---|---|
| Resmi API `https://api-live.euroleague.net/v2/competitions/E/seasons/E{yıl}/people?personType=J&limit=2000` | Sezon kayıtları: kod, isim, doğum tarihi, doğum ülkesi, uyruk, kulüp (sezon ortası transferler ayrı kayıt) | 2000-01 … 2026-27 | Anahtarsız, yayımlanmış kullanım şartı bulunamadı |

Betiğin tek bağımlılığı Python standart kütüphanesidir.

---

## 4. Üretim hattı

```bash
python backend/scripts/build_databases.py                       # ikisi, backend/data'ya yazar
python backend/scripts/build_databases.py --league nba --out /tmp/x   # deneme çıktısı
```

Çıktıyı `backend/data` üzerine yazmadan önce başka bir klasöre üretip karşılaştırmak önerilir.
Önceki veri dosyası okunur (bkz. "taşınan kayıtlar"), bu yüzden betik eski dosya yerindeyken
çalıştırılmalıdır.

### 4.1 NBA adımları

1. **Roster snapshot'ları** okunur. Her oyuncu için mevcut takım + `stats` geçmişindeki takımlar
   alınır; hiç NBA takımı olmayanlar (draft adayları) atlanır. Bazı dosyalarda sondaki virgül
   hatası vardır, tolere edilir.
2. **2009-10 dosyası bozuktur**: doğum yılları ~9 yıl kaymış, doğum yerlerinin çoğu üniversite
   adıdır. Bu dosyadaki oyuncuların doğum yılı FiveThirtyEight'teki o sezon satırından alınır.
3. **ESPN güncel kadroları** eklenir (30 istek). ESPN'in doğum ülkesi en düşük önceliklidir,
   çünkü bazen milli takımı yazar (New York doğumlu Sandro Mamukelashvili → Georgia). Görünen
   isimde bilinen roster yazılışı kalır (`Ron Holland II`, ESPN'deki `Ronald Holland II` değil);
   ESPN adı yalnızca hiç bilinmeyen yeni oyuncularda görünür.
4. **Kopya birleştirme** (`merge_roster_duplicates`): aynı isim ve doğum yılı farkı ≤ 2;
   Jr./Sr./II/III eki farkı ve doğum yılı farkı ≤ 1; soyadı uzaması (`Timothe Luwawu` →
   `Timothe Luwawu-Cabarrot`) + ortak takım + yıl farkı ≤ 2; kısaltılmış ön ad (`Svi` /
   `Sviatoslav Mykhailiuk`, `Mo` / `Mohamed Bamba`) + aynı soyad + ortak takım + yıl farkı ≤ 1.
   İsim karşılaştırması aksan, nokta, kesme işareti ve aralıklı baş harfleri yok sayar
   (`R.J. Barrett` = `RJ Barrett`, `A. C. Green` = `A.C. Green`).
5. **FiveThirtyEight kariyerleri**: (ek-siz isim, doğum yılı) tek bir oyuncuya denk geliyorsa
   1977–2020 takımları eklenir.
6. **Wikidata eşleşmesi** (isim + doğum yılı ±1, oyuncunun herhangi bir yazılışıyla, tek aday şartı):
   - doğum ülkesi alınır (kurallar §5.1),
   - yalnızca **1977 öncesine ait tarihli** takım üyelikleri eklenir.
7. **Wikidata'dan yeni oyuncular** (snapshot'larda olmayanlar, çoğu 1995 öncesi emekli):
   1977 sonrası takımları FiveThirtyEight'ten, öncesi Wikidata'dan. Tarihsiz Wikidata
   üyelikleri yalnızca koç olmayan kişiler için sayılır.
8. **Taşınan kayıtlar**: önceki veri dosyasında olup hiçbir kaynağın kapsamadığı oyuncular
   korunur (şu an 1 kişi).

### 4.2 EuroLeague adımları

1. 2000'den bugüne her sezonun kayıtları çekilir. API varsayılan olarak 500 kayıt döner
   (2001-02'de 527 var); `limit=2000` gönderilir, `total` daha büyükse uyarı basılır.
2. Kişi anahtarı: normalize isim + doğum tarihi (yoksa tek aynı-isimli kişiye bağlanır).
3. Kulüp adları **birebir** alias tablosuyla (`EUROLEAGUE_CLUB_ALIASES`) normalize edilir.
   Alt dize eşleşmesi bilinçli olarak kullanılmaz: "Ulker" (Ülkerspor) ≠ "Fenerbahce Ulker",
   "Skipper Bologna" (Fortitudo) ≠ Virtus.
4. En az bir kriter kulübünde oynamış oyuncular alınır.
5. Önceki veri dosyasındaki elle girilmiş efsaneler (2000 öncesi) korunur; aynı kişi API'de
   varsa 2000 öncesi kulüpleri birleştirilir.

---

## 5. Kurallar ve kararlar

### 5.1 Ülke = doğum ülkesi
Her iki ligde ülke, **doğduğu ülke**dir (Kyrie Irving → Australia, Domantas Sabonis → USA,
Nikola Vučević → Switzerland). Kurallar penceresinde ve README'de yazılıdır.

- EuroLeague API'sinde `birthCountry` önce, yoksa `country` kullanılır. `country` çoğu zaman
  ikinci pasaporttur (Ginóbili İtalyan, Scola İspanyol görünür).
- NBA öncelik sırası:
  1. `NBA_COUNTRY_OVERRIDES` (elle, her şeyi ezer),
  2. roster doğum yeri; Wikidata farklı **yabancı** ülke diyorsa Wikidata (Pekovic: Montenegro),
     roster boşsa Wikidata,
  3. roster "USA" ↔ Wikidata yabancı ülke çatışmasında roster kalır ve build çıktısında
     listelenir. Sebep: Wikidata bazı ABD doğumluları aynı adlı yabancı kasabaya bağlıyor
     (Kendall Gill → Paisley/İskoçya, Matt Carroll → Horsham/Avustralya). Doğruluğu bilinen
     tersi vakalar override tablosundadır (Ben Gordon → UK, Carlos Boozer → Germany).
  4. Yedekler: EuroLeague doğum ülkesi → önceki veri (USA/Georgia hariç) → roster'da
     üniversite adı varsa USA → boş.
- Wikidata Porto Riko ve ABD Virjin Adaları'nı USA'ya bağlar; roster bu bölgeleri
  söylüyorsa roster kalır (Tim Duncan → U.S. Virgin Islands).
- Ülke adları tek biçime çekilir (`COUNTRY_ALIASES`): United States → USA, England/United
  Kingdom → UK, Türkiye → Turkey, Russian Federation → Russia, Macedonia → North Macedonia…

### 5.2 Takım = franchise soyu
- Eski adlar bugünkü franchise'a sayılır: Seattle SuperSonics → Oklahoma City Thunder,
  Vancouver → Memphis, New Jersey Nets → Brooklyn, Washington/Baltimore Bullets → Wizards,
  Buffalo Braves / San Diego Clippers → LA Clippers, Cincinnati/Kansas City Kings → Sacramento,
  Syracuse Nationals → 76ers, Philadelphia Warriors → Golden State, St. Louis Hawks → Atlanta.
- 1988–2002 Charlotte Hornets → **Charlotte Hornets** (NBA'in 2014'teki tarih devrine uygun);
  2002–2013 New Orleans Hornets → New Orleans Pelicans.
- Wikidata pre-1977 kayıtlarında ABA dönemi de franchise'a sayılır (Dr. J'nin Nets yılları
  gibi), çünkü Wikidata bunları aynı takım öğesine bağlar.
- Roster `stats` geçmişi, takasla gelip hiç oynamadan ayrılan oyuncuları da içerebilir.

### 5.3 EuroLeague kriter kulüpleri
20 köklü kulüp + 2026-27'de ligde olan Beşiktaş, Dubai Basketball, Hapoel Tel Aviv. Görünen
adlar eski sürümle uyum için korunmuştur (ör. "EA7 Emporio Armani Milan", "Virtus Segafredo
Bologna").

---

## 6. Bilinen eksikler

- **2021 sonrası sezon ortası takaslar** yalnızca roster `stats` geçmişi kadar doğrudur. Güncel
  sezonda ESPN kadrosu çekildiği andaki durumu yansıtır; sezon içi takaslar için betik yeniden
  çalıştırılmalıdır.
- **Wikidata'dan gelen 2.646 oyuncunun ülkesi** çapraz kontrol edilmedi; yanlış kasaba
  bağlama hatası kalmış olabilir.
- **Oyuncu-koçlar**: Wikidata'da oyunculuk dönemi tarihsiz kayıtlıysa (Pat Riley) veri dışında
  kalırlar, çünkü tarihsiz kayıtlar koçluk görevleriyle karışık.
- **1977 öncesi takım geçmişi** Wikidata'nın tarihli kayıtları kadardır; eksik olabilir.
- **EuroLeague isimleri** resmi kayıt adıdır ("Emanuel Ginobili"); arama "ginobili" ile bulur.
- EuroLeague 2000-01'de oyuncuların ~%32'sinin doğum ülkesi API'de boş; 13 oyuncunun ülkesi yok.
- Aynı kişinin isim değiştirdiği durumlar ayrı kayıt olabilir (Bobby Dixon / Ali Muhammed).

---

## 7. Lisans durumu

- **Wikidata**: CC0, serbest.
- **FiveThirtyEight**: CC BY 4.0, kaynak gösterilmeli (README "Data Sources" bölümünde).
- **EuroLeague API**: yayımlanmış kullanım şartı bulunamadı; ticari kullanımdan önce
  kontrol edilmeli.
- **ESPN kadro uç noktası**: resmî olarak belgelenmemiş, anahtarsız bir uç nokta; yalnızca
  oyuncu-takım-doğum yeri gerçekleri alınıyor. ESPN'in genel kullanım şartları otomatik
  erişimi kısıtlayabilir; projeyi yayımlamadan önce kontrol edilmeli.
- **Basketball GM rosterları**: lisans belirtilmemiş ve büyük olasılıkla ZenGM'in gerçek oyuncu
  verisinden türetilmiş. ZenGM'in [lisansı](https://raw.githubusercontent.com/zengm-games/zengm/master/LICENSE.md)
  "This project is not open source!" der ve dağıtımı kısıtlar. Projeyi yayımlamadan önce
  güncel oyuncular için temiz bir kaynağa (nba_api) geçmek ya da izin almak gerekir.

---

## 8. Değerlendirilen diğer NBA kaynakları

| Kaynak | Artı | Eksi |
|---|---|---|
| nba_api / stats.nba.com | Draft, ödüller, kariyer istatistikleri; 1946'dan beri (doğrulanmadı) | Bot kontrolü ve bulut IP engeli; oyuncu başına çağrı (~1,5 saat); `COUNTRY` alanının doğum mu uyruk mu olduğu doğrulanmadı; veri NBA.com şartlarına tabi |
| ZenGM real-player-data | En tam veri (1947+, doğum yeri, ödüller, şampiyonluklar) | Lisans dağıtımı yasaklıyor |
| Basketball-Reference | Referans kalitesi | Kullanım şartları otomatik erişimi yasaklıyor |
| balldontlie | Kolay API | Anahtar zorunlu, ücretsiz planda dakikada 5 istek, ödül verisi belirsiz |
| Kaggle "NBA Database" (wyattowalsh) | nba_api'den üretilmiş hazır tablolar | Ödül tablosu yok, lisans/güncellik doğrulanmadı |

---

## 9. EuroLeague API'sinin sunduğu diğer veriler (gelecek kriterler için)

Hepsi anahtarsız GET; resmi doküman yok, swagger boş.

| Veri | Uç nokta | Kapsam | Kriter fikri |
|---|---|---|---|
| Oyuncu kariyeri | `/v2/competitions/E/people/{kod}` | oyuncu başı | kulüp geçmişi doğrulama |
| Kariyer toplamları (tek çağrı, ~3.075 oyuncu) | `/v3/competitions/E/statistics/players/traditional?SeasonMode=Range&FromSeasonCode=E2000&ToSeasonCode=E2025&statisticMode=Accumulated&limit=3100` | 2000–2025 | "Kariyerde 2.000+ sayı" |
| Sezon istatistikleri, lider tabloları | `.../traditional?SeasonMode=Single&SeasonCode=E{yıl}&statisticMode=Accumulated`, `/v2/competitions/E/stats/players/leaders` | 2000– | sezon lideri |
| Maç listesi (faz: RS/PO/PI/FF, skor, hakemler) | `/v2/competitions/E/seasons/E{yıl}/games` | 2000– | Final Four oynamış |
| Maç bazında oyuncu istatistiği | `/v3/competitions/E/seasons/E{yıl}/games/{kod}/stats` | 2000– | "Maçta 30+ sayı" |
| Şampiyon | `/v2/competitions/E/seasons/E{yıl}` → `winner` | 2000–2025 (2019-20 iptal) | EuroLeague şampiyonu |
| Koçlar, hakemler | `.../people?personType=E`, `/referees` | sezon bazında | koç kriteri |
| Sayı sayı akış, şut koordinatları | `https://live.euroleague.net/api/PlaybyPlay`, `/Points` | 2007– | — |
| EuroCup | aynı uç noktalar, yarışma kodu `U` | 2002– | ikinci mod |

API'de **ödül** (MVP, Final Four MVP, All-EuroLeague) uç noktası yok; bunlar için dış kaynak
gerekir.
