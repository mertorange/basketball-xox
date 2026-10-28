"""EuroLeague clubs used as criteria and the names the API has used for them."""

STANDARD_EUROLEAGUE_CLUBS = [
    "Real Madrid",
    "FC Barcelona",
    "Panathinaikos",
    "Olympiacos",
    "Fenerbahçe",
    "Anadolu Efes",
    "Maccabi Tel Aviv",
    "CSKA Moscow",
    "Baskonia",
    "AS Monaco",
    "Partizan",
    "Crvena Zvezda",
    "EA7 Emporio Armani Milan",
    "Zalgiris Kaunas",
    "FC Bayern Munich",
    "Virtus Segafredo Bologna",
    "Valencia Basket",
    "Paris Basketball",
    "ALBA Berlin",
    "LDLC ASVEL Villeurbanne",
    "Beşiktaş",
    "Dubai Basketball",
    "Hapoel Tel Aviv"
]

# Exact (lowercased) club names seen in the EuroLeague API since 2000 -> canonical club.
# Matching is exact on purpose: "Ulker" (Ülkerspor) is not "Fenerbahce Ulker", and
# "Skipper Bologna" (Fortitudo) is not Virtus.
EUROLEAGUE_CLUB_ALIASES = {
    "Real Madrid": ["real", "real madrid"],
    "FC Barcelona": ["barcelona", "fc barcelona", "fc barcelona lassa", "fc barcelona regal", "axa fc barcelona",
                     "regal barcelona", "regal fc barcelona", "winterthur fc barcelona"],
    "Panathinaikos": ["panathinaikos", "pao", "panathinaikos athens", "panathinaikos aktor athens",
                      "panathinaikos opap athens", "panathinaikos superfoods athens"],
    "Olympiacos": ["olympiacos", "olympiakos", "olympiacos piraeus"],
    "Fenerbahçe": ["fenerbahce", "fenerbahçe", "fenerbahce istanbul", "fenerbahce beko istanbul",
                   "fenerbahce dogus istanbul", "fenerbahce tarfin istanbul", "fenerbahce ulker",
                   "fenerbahce ulker istanbul"],
    "Anadolu Efes": ["efes", "anadolu efes", "anadolu efes istanbul", "efes pilsen", "efes pilsen istanbul"],
    "Maccabi Tel Aviv": ["maccabi", "maccabi tel aviv", "maccabi electra", "maccabi electra tel aviv", "maccabi elite",
                         "maccabi elite tel aviv", "maccabi fox tel aviv", "maccabi playtika tel aviv",
                         "maccabi rapyd tel aviv"],
    "CSKA Moscow": ["cska", "cska moscow"],
    "Baskonia": ["baskonia", "baskonia vitoria gasteiz", "baskonia vitoria-gasteiz", "bitci baskonia vitoria-gasteiz",
                 "caja laboral", "caja laboral vitoria", "cazoo baskonia vitoria-gasteiz",
                 "kirolbet baskonia vitoria gasteiz", "kirolbet baskonia vitoria-gasteiz",
                 "kosner baskonia vitoria-gasteiz", "laboral kutxa", "laboral kutxa vitoria",
                 "laboral kutxa vitoria gasteiz", "tau ceramica", "tau ceramica vitoria-gasteiz",
                 "td systems baskonia vitoria-gasteiz"],
    "AS Monaco": ["monaco", "as monaco"],
    "Partizan": ["partizan", "partizan belgrade", "partizan igokea", "partizan mozzart bet belgrade",
                 "partizan nis belgrade", "partizan mt:s belgrade"],
    "Crvena Zvezda": ["crvena zvezda", "red star", "crvena zvezda meridianbet belgrade",
                      "crvena zvezda telekom belgrade", "crvena zvezda mts belgrade"],
    "EA7 Emporio Armani Milan": ["milan", "milano", "olimpia milano", "aj milano", "armani jeans milano", "armani milan",
                                 "armani olimpia milan", "ax armani exchange milan",
                                 "ax armani exchange olimpia milan", "ea7 emporio armani",
                                 "ea7 emporio armani milan"],
    "Zalgiris Kaunas": ["zalgiris", "zalgiris kaunas"],
    "FC Bayern Munich": ["bayern", "bayern munich", "fc bayern munich"],
    "Virtus Segafredo Bologna": ["virtus", "virtus bologna", "virtus segafredo bologna", "kinder virtus bologna",
                                 "virtus vidivici"],
    "Valencia Basket": ["valencia", "valencia basket", "pamesa valencia", "power electronics valencia"],
    "Paris Basketball": ["paris", "paris basketball"],
    "ALBA Berlin": ["alba", "alba berlin"],
    "LDLC ASVEL Villeurbanne": ["asvel", "asvel basket", "ldlc asvel villeurbanne"],
    "Beşiktaş": ["besiktas", "besiktas istanbul", "besiktas jk istanbul"],
    "Dubai Basketball": ["dubai basketball"],
    "Hapoel Tel Aviv": ["hapoel ibi tel aviv"],
    # Former EuroLeague clubs (kept on player profiles, not used as grid criteria)
    "Unicaja": ["unicaja", "unicaja malaga"],
    "Darüşşafaka": ["darussafaka", "darussafaka dogus istanbul", "darussafaka tekfen istanbul"],
    "Khimki": ["khimki", "khimki moscow region", "bc khimki moscow region"],
    "Brose Bamberg": ["brose bamberg", "brose baskets", "brose baskets bamberg", "ghp bamberg"],
    "Cibona": ["cibona", "cibona vip", "cibona zagreb"],
    "Union Olimpija": ["union olimpija", "union olimpija ljubljana"],
    "Galatasaray": ["galatasaray liv hospital istanbul", "galatasaray medical park", "galatasaray odeabank istanbul"],
    "Lietuvos Rytas": ["lietuvos rytas", "lietuvos rytas vilnius"],
    "Prokom Gdynia": ["asseco prokom", "asseco prokom gdynia", "prokom trefl sopot"],
    "UNICS Kazan": ["unics kazan"],
    "Benetton Treviso": ["benetton basket", "benetton treviso"],
    "Fortitudo Bologna": ["climamio bologna", "skipper bologna", "skipper fortitudo bologna"],
    "Buducnost": ["buducnost", "kk buducnost", "buducnost voli pogdorica"],
    "Spirou Charleroi": ["spirou basket", "spirou charleroi", "belgacom spirou charleroi",
                         "region wallone spirou charleroi"],
    "Cantu": ["bennet cantu", "mapooro cantu"],
    "London Towers": ["haribo london towers", "kinder london towers"],
}

EUROLEAGUE_CLUB_NORMALIZER = {
    alias: club for club, aliases in EUROLEAGUE_CLUB_ALIASES.items() for alias in aliases
}

def normalize_euroleague_club(raw_club):
    raw_club = (raw_club or "").strip()
    return EUROLEAGUE_CLUB_NORMALIZER.get(raw_club.lower(), raw_club)
