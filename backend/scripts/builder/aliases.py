"""One player, several records: the merges and nicknames applied at the end of every build.

Sources spell players differently, and some players changed their names. SAME_PLAYER lists
the records that are one person; each entry is (name to keep, a team of that record or None
when the name is unique, the other names). The other names stay on the player as aliases,
so they still work in the game. NICKNAMES only adds aliases.

Only confirmed cases belong here. Plenty of near-identical names are different people and
stay apart: Tony / Tony L. Mitchell, Cliff / Clifford Robinson, Mark / Marc Jackson,
Ken / Kenny Green, Chuck / Chuckie Williams; EuroLeague Jamon / Jamont Gordon, Jalen /
Jaylen Adams.
"""

SAME_PLAYER = {
    "nba": [
        ("Metta World Peace", None, ["Metta Sandiford-Artest", "Ron Artest"]),
        ("Enes Freedom", None, ["Enes Kanter"]),
        ("Hedo Turkoglu", None, ["Hidayet Turkoglu"]),
        ("Nene", None, ["Nene Hilario"]),
        ("Anfernee Hardaway", None, ["Penny Hardaway"]),
        ("Nate Archibald", None, ["Tiny Archibald"]),
        ("Sarunas Marciulionis", None, ["Sarunas Marciulonis"]),
        ("Chris Johnson", "Boston Celtics", ["Christapher Johnson"]),
        ("George Johnson", "Milwaukee Bucks", ["George L. Johnson"]),
        ("Greg Anderson", None, ['Greg "Cadillac" Anderson']),
        ("Cheese Johnson", None, ['Lynbert "Cheese" Johnson']),
        ("Ante Zizic", None, ["Ante Toni Zizic"]),
        ("Roger Mason", None, ["Roger Mason, Jr."]),
        ("Jeff Taylor", "Charlotte Hornets", ["Jeffery Taylor"]),
        ("Josh Reaves", None, ["Joshua Reaves"]),
        ("Jeff Sheppard", None, ["Jeffrey Sheppard"]),
        ("Walker Russell", "Detroit Pistons", ["Walker Russell, Jr."]),
        ("James Michael McAdoo", None, ["James McAdoo"]),
        ("Patrick Ewing", "New Orleans Pelicans", ["Patrick Ewing, Jr."]),
        ("Darius Washington", None, ["Darius Washington, Jr."]),
        ("David Greenwood", None, ["Dave Greenwood"]),
        ("David Nwaba", None, ["David Ugochukwu Nwaba"]),
        ("Fred Boyd", None, ["Freddie Boyd"]),
        ("Rob Rose", None, ["Robert Rose"]),
        ("Didier Ilunga-Mbenga", None, ["Didier Mbenga"]),
        ("Efthimis Rentzias", None, ["Efthimi Rentzias"]),
        ("Juancho Hernangomez", None, ["Juan Hernangomez"]),
        ("Ike Diogu", None, ["Ikechukwa Somotochukwa Diogu"]),
        ("Luc Mbah a Moute", None, ["Luc Richard Mbah a Moute"]),
        ("Luis Montero", None, ["Luis David Montero"]),
        ("Marcelo Huertas", None, ["Marcelinho Huertas"]),
        ("Mitch Creek", None, ["Mitchell Creek"]),
        ("Ollie Mack", None, ["Oliver Mack"]),
        ("Omer Yurtseven", None, ["Omer Faruk Yurtseven"]),
        ("Pete Verhoeven", None, ["Peter Verhoeven"]),
        ("Ron Grandison", None, ["Ronnie Grandison"]),
        ("Walter Lemon Jr.", None, ["Walter Lemon, Jr."]),
        ("Aleksandar Djordjevic", None, ["Aleksandar Dordevic"]),
        ("Jakob Poeltl", None, ["Jakob Poltl"]),
        ("Tom Burleson", None, ["Tommy Burleson"]),
        ("Louis Amundson", None, ["Lou Amundson"]),
        ("Charlie Brown Jr.", None, ["Charles Brown"]),
    ],
    "euroleague": [
        ("Armando Bacot Jr.", None, ["Armando Bacot"]),
        ("Brandon Boston Jr.", None, ["Brandon Boston"]),
        ("Matthew Morgan", None, ["Matt Morgan"]),
        ("Luigi Datome", None, ["Gigi Datome"]),
        ("Glynn Watson Jr.", None, ["Glynn Watson"]),
        ("Jeffrey Dowtin Jr.", None, ["Jeff Dowtin Jr."]),
        ("Juom Maker Bol", None, ["Juom Bol"]),
        ("Leopold Cavaliere", None, ["Leo Cavaliere"]),
        ("Matthew Costello", None, ["Matt Costello"]),
        ("Nathan Reuvers", None, ["Nate Reuvers"]),
        ("Nathan Sestina", None, ["Nate Sestina"]),
        ("Nikolaos Rogkavopoulos", None, ["Nikos Rogkavopoulos"]),
        ("Oshae Brissett", None, ["O'Shae J Brissett"]),
        ("Sarunas Jasikevicius", None, ["Saras Jasikevicius"]),
        ("Theodoros Papaloukas", None, ["Theo Papaloukas"]),
        ("William Rayman", None, ["Will Rayman"]),
        ("Zachary Seljaas", None, ["Zac Seljaas"]),
        ("Walter Tavares", None, ["Edy Tavares"]),
        ("Konstantinos Mitoglou", None, ["Dinos Mitoglou"]),
        ("Ali Muhammed", None, ["Bobby Dixon"]),
        ("Gur Lavi", None, ["Gur Lavy"]),
    ],
}

# Birth names and nicknames people actually type. Search only: the box shows the real name.
NICKNAMES = {
    "nba": {
        "Shaquille O'Neal": ["Shaq"], "Kevin Durant": ["KD"], "Carmelo Anthony": ["Melo"],
        "Allen Iverson": ["AI", "The Answer"], "Chris Paul": ["CP3"], "Dwyane Wade": ["D-Wade", "Flash"],
        "Julius Erving": ["Dr. J"], "Magic Johnson": ["Earvin Johnson"], "Tracy McGrady": ["T-Mac"],
        "Kareem Abdul-Jabbar": ["Lew Alcindor"], "Mahmoud Abdul-Rauf": ["Chris Jackson"],
        "World B. Free": ["Lloyd Free"], "Jamaal Wilkes": ["Keith Wilkes"], "Hakeem Olajuwon": ["Akeem Olajuwon", "The Dream"],
        "Nate Archibald": ["Tiny"], "Anfernee Hardaway": ["Penny"], "Tree Rollins": ["Wayne Rollins"],
        "Muggsy Bogues": ["Tyrone Bogues"], "Doc Rivers": ["Glenn Rivers"], "Peja Stojakovic": ["Predrag Stojakovic"],
        "Giannis Antetokounmpo": ["Greek Freak"], "LeBron James": ["King James"], "Kobe Bryant": ["Black Mamba"],
        "Stephen Curry": ["Steph Curry"], "Pete Maravich": ["Pistol Pete"], "Larry Bird": ["Larry Legend"],
        "Dennis Rodman": ["The Worm"], "Charles Barkley": ["Sir Charles"], "Anthony Davis": ["AD"],
        "Nikola Jokic": ["The Joker"], "James Harden": ["The Beard"], "Karl Malone": ["The Mailman"],
        "George Gervin": ["The Iceman"], "Clyde Drexler": ["The Glide"], "Walt Frazier": ["Clyde Frazier"],
        "Darryl Dawkins": ["Chocolate Thunder"], "Vince Carter": ["Vinsanity"], "Amar'e Stoudemire": ["STAT"],
        "Karl-Anthony Towns": ["KAT"], "DeMarcus Cousins": ["Boogie"], "Jimmy Butler": ["Jimmy Buckets"],
        "Zach Randolph": ["Z-Bo"], "Manu Ginobili": ["Emanuel Ginobili"], "Mo Williams": ["Maurice Williams"],
        "Mo Bamba": ["Mohamed Bamba"], "Metta World Peace": ["Metta Artest"],
    },
    "euroleague": {
        "Vassilis Spanoulis": ["Kill Bill", "V-Span"], "Juan Carlos Navarro": ["La Bomba"],
        "Sergio Rodriguez": ["Chacho"], "Facundo Campazzo": ["Facu"], "Sarunas Jasikevicius": ["Saras"],
    },
}


def _merge_into(keep, other):
    """Folds a second record of the same player into the first."""
    keep["teams"] = sorted(set(keep["teams"]) | set(other["teams"]))
    spans = [p["seasons"] for p in (keep, other) if p.get("seasons")]
    if spans:
        keep["seasons"] = [min(s[0] for s in spans), max(s[1] for s in spans)]
    awards = set(keep.get("awards", ())) | set(other.get("awards", ()))
    if awards:
        keep["awards"] = sorted(awards)
    stats = dict(keep.get("stats") or {})
    for field, value in (other.get("stats") or {}).items():
        stats[field] = max(stats.get(field, 0), value)  # sources overlap: never add them up
    if stats:
        keep["stats"] = stats
    if other.get("wiki_pages", 0) > keep.get("wiki_pages", 0):
        keep["wiki_pages"] = other["wiki_pages"]
    for field in ("country", "draft", "college", "born", "pos", "_born", "_pos"):
        if not keep.get(field) and other.get(field):
            keep[field] = other[field]


def _add_aliases(player, names):
    aliases = set(player.get("aliases", ())) | {name for name in names if name != player["name"]}
    if aliases:
        player["aliases"] = sorted(aliases)


def apply_aliases(league, players):
    """Merges the records of SAME_PLAYER and adds NICKNAMES. Safe to run twice."""
    for keep_name, team, others in SAME_PLAYER[league]:
        keepers = [p for p in players if p["name"] == keep_name and (team is None or team in p["teams"])]
        if not keepers:
            continue
        keep = keepers[0]
        for name in others:
            for record in [p for p in players if p["name"] == name]:
                _merge_into(keep, record)
                players.remove(record)
            _add_aliases(keep, [name])
    by_name = {p["name"]: p for p in players}
    for name, nicknames in NICKNAMES[league].items():
        if name in by_name:
            _add_aliases(by_name[name], nicknames)
    return players
