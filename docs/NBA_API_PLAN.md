# NBA verisini nba_api'ye taşıma planı

Durum: plan, uygulanmadı. Hazırlayan: Claude (31 Ekim 2026). Uygulayacak: Mert.
İlgili belgeler: [DATA.md](../DATA.md) §4–§8, `backend/scripts/builder/nba.py`.

---

## 1. Amaç

NBA verisinin ana kaynağını [nba_api](https://github.com/swar/nba_api) (stats.nba.com) yapmak:

- **Lisans:** Basketball GM rosterlarına (ZenGM türevi, dağıtımı kısıtlı), resmî olmayan ESPN
  kadro uç noktasına ve FiveThirtyEight'e bağımlılığı bitirmek.
- **Doğruluk:** Takım geçmişini oynanan maçlardan çıkarmak. Wikidata'nın koçluk kayıtlarının
  oyunculuk sayılması (Alex Hannum: Houston 1970–71, Denver 1972–74) kendiliğinden biter.
- **Kapsam:** 1946'dan bu yana tüm oyuncular, tam kariyerler, sezon ortası takaslar.
- **Yeni kriterler:** All-Star, sayı krallığı, maçta 50+ sayı (şu an verisi olmadığı için yoklar).

Wikidata kalır: doğum yeri (§4.5) ve ünlülük için `wiki_pages`. EuroLeague hattı değişmez.

**Değişmeyen şey: veri şeması.** `nba_data.json` aynı alanlarla yazılır (`name`, `country`,
`teams`, `seasons`, `stints`, `awards`, `draft`, `college`, `stats`, `wiki_pages`, `aliases`,
`born`, `pos`). Böylece `backend/catalog`, `backend/game` ve frontend'e dokunmak gerekmez.
Yeni alanlar yalnızca §7'deki yeni kriterler için eklenir.

---

## 2. Kısıtlar ve riskler (önce bunları bil)

1. **Erişim.** stats.nba.com bulut sağlayıcılarının IP'lerini çoğunlukla engelliyor ve tarayıcı
   benzeri başlıklar istiyor (nba_api bunları kendisi gönderiyor). Sonuç:
   - Toplama **ev makinesinde** (normal internet bağlantısı) çalışır, VPS'te değil.
   - Claude'un çalıştığı ortamdan da erişilemiyor; denemeler izin sınıflandırıcısına takıldı.
     Toplayıcıyı Claude yazabilir, ama çalıştıran insan olmalı.
   - Sunucu NBA verisini kendi çekmez; evde üretilen önbelleği alır (§5).
2. **Lisans.** Veri NBA.com kullanım şartlarına tabi. Sorun ZenGM'den NBA'e kayıyor, tamamen
   kalkmıyor. Ticari olmayan bir hayran oyunu için risk düşük ama sıfır değil. Herkese açık
   yayından önce şartlar okunmalı (P0).
3. **ABA yılları düşer.** nba_api yalnızca NBA istatistiği içeriyor: Dr. J'nin Nets, George
   Gervin'in Spurs ABA yılları kaybolur. Bu bir ürün kararı; DATA.md'ye yazılmalı.
4. **Hız ve süre.** İlk tam çekim ~5.000 oyuncu × 3 istek ≈ 15.000 istek; saniyede ~1 istekle
   **3–5 saat**. Sonraki güncellemeler yalnızca aktif oyuncular (~550 × 3) ve kadrolar: ~30 dk.
5. **`COUNTRY` alanının anlamı bilinmiyor.** Bizim kuralımız doğum ülkesi. Alan uyruksa doğum
   yerini Wikidata/rosterdan almaya devam ederiz (§4.5). P0'da test edilir.

---

## 3. Aşamalar ve kabul ölçütleri

| Aşama | İş | Bitti sayılır |
|---|---|---|
| **P0** | Erişim ve `COUNTRY` testi (§3.1); NBA.com kullanım şartlarını oku | Ev makinesinden 3 uç nokta cevap veriyor; `COUNTRY` anlamı biliniyor; şartlar için karar var |
| **P1** | Toplayıcı + önbellek (§4.1–§4.3), ilk tam çekim | Önbellekte ~5.000 oyuncu; yarıda kesilip yeniden başlatılınca kaldığı yerden devam ediyor |
| **P2** | Builder kaynağı + `--nba-source nba_stats` bayrağı (§4.4–§4.6) | Önbellekten `nba_data.json` üretiliyor, şema aynı, testler geçiyor |
| **P3** | Eski ve yeni çıktıyı karşılaştırma (§6) | Fark raporu okundu; §6 kontrol listesi geçiyor; `refresh_data.validate` ve `FAME_CHECKS` geçiyor |
| **P4** | Geçiş: varsayılan kaynak nba_stats; BBGM, ESPN, 538 kodu silinir; DATA.md ve README güncellenir | Docker'da builder önbellekle çalışıyor (§5) |
| **P5** | Yeni kriterler: All-Star, sayı krallığı, maçta 50+ sayı (§7) | `criteria.py`'de builder'lar, testler, ünlülük ağırlıkları |

### 3.1 P0 testi (ev makinesinde, 1 dakika)

```bash
pip install nba_api
python - <<'EOF'
from nba_api.stats.endpoints import commonplayerinfo, playercareerstats, playerawards
info = commonplayerinfo.CommonPlayerInfo(player_id=202681).get_normalized_dict()["CommonPlayerInfo"][0]
print(info["DISPLAY_FIRST_LAST"], info["COUNTRY"], info["BIRTHDATE"], info["SCHOOL"],
      info["DRAFT_YEAR"], info["DRAFT_ROUND"], info["DRAFT_NUMBER"])
career = playercareerstats.PlayerCareerStats(player_id=202681).get_normalized_dict()
print(career["SeasonTotalsRegularSeason"][0])
print({a["DESCRIPTION"] for a in playerawards.PlayerAwards(player_id=202681).get_normalized_dict()["PlayerAwards"]})
EOF
```

Kyrie Irving Melbourne doğumlu: `COUNTRY` "Australia" ise alan doğum ülkesi, "USA" ise uyruk.
Ödül açıklamalarının tam yazımı (`DESCRIPTION`) §4.4'teki eşleme tablosu için not edilir.
Aynı testi bir kez VPS'ten de denemek, sunucunun erişip erişemediğini netleştirir.

---

## 4. Tasarım

### 4.1 Toplayıcı: `backend/scripts/collect_nba_stats.py`

Docker imajına girmez; yalnızca toplama yapan makinede çalışır. Bağımlılığı ayrı dosyada:
`requirements-collect.txt` → `nba_api==<sabit sürüm>`.

```bash
python backend/scripts/collect_nba_stats.py --cache ~/hoopgrid-nba-cache            # eksikleri ve aktifleri çek
python backend/scripts/collect_nba_stats.py --cache ~/hoopgrid-nba-cache --full     # her şeyi yeniden çek
python backend/scripts/collect_nba_stats.py --cache ~/hoopgrid-nba-cache --player 202681  # tek oyuncu
```

Kurallar:
- **Nazik:** istekler arasında en az 0,8 sn; zaman aşımı 30 sn; hata/429/zaman aşımında üstel
  bekleme ile 3 deneme. Bir oyuncu üç kez başarısız olursa `failures.json`'a yazılır, çekim sürer.
- **Devam edebilir:** her dosya bitince yazılır (önce `.tmp`, sonra yeniden adlandırma). Kesilip
  yeniden başlatılınca var olan dosyalar atlanır.
- **Artımlı:** `TO_YEAR` güncel sezondan eski olan (emekli) oyuncular bir kez çekilir ve bir daha
  çekilmez (`--full` hariç). Aktif oyuncular ve kadrolar her çalıştırmada yenilenir.
- **İlerleme:** "1234/4987 oyuncu, kalan ~2 sa" gibi satırlar; sonunda özet.

### 4.2 Hangi uç noktalar

| Uç nokta | Ne için | Çağrı |
|---|---|---|
| `CommonAllPlayers(is_only_current_season=0)` | Tüm oyuncu listesi, `FROM_YEAR`/`TO_YEAR`, `PERSON_ID` | 1 |
| `CommonPlayerInfo` | Doğum tarihi, ülke, kolej (`SCHOOL`), draft, pozisyon, boy | oyuncu başı 1 |
| `PlayerCareerStats` | Sezon × takım satırları (normal sezon ve playoff), maç ve dakika | oyuncu başı 1 |
| `PlayerAwards` | Ödüller ve şampiyonluklar, sezonlarıyla | oyuncu başı 1 |
| `CommonTeamRoster` | Güncel sezon kadroları (ESPN'in yerine) | takım başı 1 |
| `LeagueLeaders` | Sezon sayı/ribaund/asist liderleri (P5) | sezon başı ~3 |
| `LeagueGameLog(player_or_team_abbreviation="P")` | Oyuncu maç logları, maçta 50+ sayı (P5) | sezon × (normal + playoff) |

### 4.3 Önbellek düzeni

```
<cache>/
  index.json                         CommonAllPlayers + çekim zamanı
  players/<PERSON_ID>.json           {"info": ..., "career": ..., "awards": ..., "fetched_at": ...}
  rosters/<sezon>.json               güncel kadrolar, takım başına
  seasons/<sezon>/leaders.json       (P5)
  seasons/<sezon>/game_highs.json    (P5) oyuncu başına sezonun en yüksek sayısı; ham log saklanmaz
  failures.json
  MANIFEST.json                      oyuncu sayısı, son çekim, nba_api sürümü
```

Ham API cevabı saklanır, yorum yapılmaz. Yorum builder'da yapılır; kural değişince yeniden
çekmeye gerek kalmaz. Sezonlar API'deki gibi yazılır ("2024-25"); builder bizim kurala
("2025") çevirir.

### 4.4 Builder kaynağı: `backend/scripts/builder/sources/nba_stats.py`

Ağa çıkmaz; yalnızca önbelleği okur. Diğer kaynak modülleri gibi sade kayıtlar döndürür:

- **Takımlar:** `TEAM_ID` franchise'a bağlıdır ve taşınmalarda değişmez (Sonics ve Thunder aynı
  kimlik). `nba_teams.py`'ye 30 kimlik → franchise tablosu eklenir. Kapanmış takımların kimlikleri
  yok sayılır. `TEAM_ID == 0` (traded oyuncunun "TOT" toplam satırı) atlanır.
- **Stint'ler:** `(sezon, franchise, playoff)`. Normal sezon satırı `False`, playoff satırı `True`.
  Mevcut `Person.stints` biçimiyle aynı; `add_championships` aynen çalışır.
- **Maç/dakika:** sezon başına `GP` ve `MIN` → mevcut `Person.add_workload`.
- **Ödüller:** `DESCRIPTION` → anahtar tablosu. P0 testinden gelen tam yazımlarla doldurulmalı;
  örnek eşleme:

  | nba_api `DESCRIPTION` (doğrulanmalı) | Bizim anahtar |
  |---|---|
  | NBA Champion | `champion` |
  | NBA Most Valuable Player | `mvp` |
  | NBA Finals Most Valuable Player | `finals_mvp` |
  | All-NBA | `all_nba` |
  | NBA Rookie of the Year | `roy` |
  | NBA Defensive Player of the Year | `dpoy` |
  | NBA Sixth Man of the Year | `sixth_man` |
  | NBA Most Improved Player | `mip` |
  | NBA All-Star | `all_star` (yeni, P5) |

  Tabloda olmayan bir açıklama build çıktısında listelenir; sessizce yutulmaz.
- **Draft:** `DRAFT_ROUND`/`DRAFT_NUMBER` ("Undrafted" → `round: 0`). Bizdeki `pick` tur içi
  sıra; nba_api'deki `DRAFT_NUMBER` genel sıra olabilir. P0'da Jokić (2014, 41. seçim, 2. tur 11.)
  ile kontrol edilmeli ve gerekirse çevrilmeli.
- **Kolej:** `SCHOOL`; mevcut `clean_college` ve `COLLEGE_ALIASES` aynen kullanılır.
- **Doğum, pozisyon:** `BIRTHDATE` → `born` (aynı adlıları ayırmak için), `POSITION` → `pos`.

### 4.5 `builder/nba.py` içinde yeni akış

`build_nba_database(out_dir, source="legacy" | "nba_stats")`. Yeni akış:

1. Önbellekten her `PERSON_ID` için bir `Person` (kimlik artık isim+doğum yılı tahmini değil,
   NBA'in kimliği; `merge_roster_duplicates` bu akışta gereksiz).
2. Güncel kadrolar (`rosters/`) → güncel sezon stint'leri.
3. `match_wikidata` → `wiki_pages`, doğum yeri. Wikidata'dan artık **takım alınmaz**
   (`wikidata_teams` / `wikidata_seasons` bu akışta kullanılmaz).
4. Ülke: P0 sonucuna göre:
   - `COUNTRY` doğum ülkesiyse: önce o; çakışmada mevcut kurallar (§6.1 DATA.md) ve
     `NBA_COUNTRY_OVERRIDES` geçerli.
   - Uyruksa: doğum yeri Wikidata P19'dan; yoksa `COUNTRY` yedek olarak.
5. `export_player` ve `apply_aliases` aynen; şema değişmez.

`build_databases.py` ve `refresh_data.py` bayrağı geçirir:
`--nba-source nba_stats --nba-cache <dizin>`. Önbellek yoksa veya `MANIFEST.json` 14 günden
eskiyse build hata verir ve canlı veri olduğu gibi kalır.

### 4.6 Ünlülük (`backend/catalog/fame.py`)

`nba_score` bugün 1977 sonrası dakikalara bakıyor (538). Yeni veride 1946'dan bu yana dakika
var (1952 öncesi `MIN` boş olabilir; doğrulanmalı). `FAME_CHECKS` (refresh_data.py) yeni
veriyle çalıştırılır; gerekirse ağırlıklar yeniden ayarlanır. Docstring'deki "since 1977"
ifadesi güncellenir.

---

## 5. Önbelleğin sunucuya gitmesi

Sunucu stats.nba.com'a ulaşamayacağı için NBA verisi evden gelir:

1. Ev makinesinde haftalık (ya da maç günleri günlük) `collect_nba_stats.py`.
2. Önbellek sunucuya `rsync` ile gider: `rsync -az ~/hoopgrid-nba-cache/ vps:/srv/hoopgrid/nba-cache/`.
   (Alternatif: ayrı, özel bir veri reposu. Ana repoya **girmez**; boyutu ve lisansı yüzünden.)
3. `docker-compose.yml`: builder'a `/srv/hoopgrid/nba-cache:/nba-cache:ro` bağlanır;
   `refresh_data.py --nba-source nba_stats --nba-cache /nba-cache`.
4. Sunucudaki günlük yenileme EuroLeague ve Wikidata'yı tazeler, NBA için en son gelen
   önbelleği kullanır. Önbellek 14 günden eskiyse yenileme reddedilir (§4.5) ve log'a yazılır.

---

## 6. Karşılaştırma ve kontrol listesi (P3)

`backend/scripts/compare_datasets.py old.json new.json`: oyuncu sayısı, yalnızca birinde olanlar,
takım kümesi farkı, ödül sayıları, ülke farkları. Fark raporu okunur; beklenen farklar
(ABA yılları, koçluk kayıtları) not edilir.

Elle kontrol edilecek örnekler:

| Oyuncu | Beklenen |
|---|---|
| Alex Hannum | Houston ve Denver **yok** (koçluk) |
| Julius Erving | yalnızca 76ers (ABA Nets yok) |
| LeBron James | Cavaliers, Heat, Lakers (güncel takımı eski veriyle aynı); MVP, Finals MVP, şampiyon |
| Marcus Smart | Rockets dahil (güncel sezon kadrosundan) |
| Kyrie Irving | ülke Australia (doğum ülkesi kuralı) |
| Moses Malone | 7 franchise; MVP; draft: undrafted mı? (ABA'dan geldi) |
| Nikola Jokić | 2. tur 11. seçim; MVP, Finals MVP, şampiyon |
| Bill Russell | Celtics; 11 şampiyonluk sezonu stint'lerde playoff `True` |
| Reggie Jordan | ülke dolu (bugün boş) |
| İki Mike James | iki ayrı kayıt, doğum tarihleriyle ayrılıyor |

Ayrıca: `refresh_data.validate` (oyuncu sayısı, takım büyüklüğü, çözülebilir ızgara,
`FAME_CHECKS`) yeni veriyle geçmeli; tüm testler geçmeli.

---

## 7. Yeni kriterler (P5)

`backend/catalog/criteria.py`'de yeni builder'lar; tahta üretici ve oyun yöneticisi değişmez.

| Kriter | Veri | Alan |
|---|---|---|
| All-Star | `PlayerAwards` | `awards` içinde `all_star` |
| Sayı / ribaund / asist kralı | `LeagueLeaders` (sezon başına) | `awards` içinde `scoring_title`, `rebounding_title`, `assists_title` |
| Maçta 50+ sayı | `LeagueGameLog` → sezonun en yüksek sayısı | `stats.high_points` |

Maç logları 1983 öncesinde eksik olabilir (doğrulanmalı). Eksik dönem varsa "maçta 50+ sayı"
kriteri o dönemin oyuncularını haksız yere reddeder. Kapsam P5'te ölçülür ve DATA.md'ye yazılır.
`fame.py`'de All-Star bir ağırlık alır.

---

## 8. Testler

- **Ağsız:** `tests/fixtures/nba_stats/` altında 4–5 oyuncunun gerçek API cevapları
  (LeBron, Jokić, Hannum, aynı adlı iki oyuncu, takaslı bir sezon). Builder testleri bunlarla
  çalışır; testler asla stats.nba.com'a çıkmaz.
- **Toplayıcı:** sahte bir HTTP istemcisiyle: yeniden deneme, zaman aşımı, devam etme,
  artımlı çekim (emekli oyuncu tekrar çekilmiyor).
- **Eşleme:** `TEAM_ID` → franchise, ödül açıklaması → anahtar, sezon "2024-25" → 2025.

---

## 9. Kararlar (Mert'in sormadan ilerleyebileceği varsayılanlar)

- Ham cevaplar önbellekte, yorum builder'da.
- Wikidata'dan takım alınmaz; yalnızca doğum yeri ve `wiki_pages`.
- ABA yılları düşer; DATA.md'ye yazılır.
- Önbellek ana repoya girmez.
- Eski hat P4'e kadar kalır (`--nba-source legacy`), sonra silinir.

Sorulması gerekenler: NBA.com şartlarına göre yayın kararı (P0), `COUNTRY` sonucu (P0).
