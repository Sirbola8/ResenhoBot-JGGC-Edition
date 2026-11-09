"""Configurações centrais dos clubes e das competições monitoradas."""

# CLUBES MONITORADOS: nomes canônicos usados para filtrar partidas por região.
BRAZILIAN_TEAMS = [
    "Flamengo",
    "Corinthians",
    "São Paulo",
    "Palmeiras",
    "Santos",
    "Vasco da Gama",
    "Fluminense",
    "Botafogo",
    "Atlético Mineiro",
    "Cruzeiro",
    "Grêmio",
    "Internacional",
]

# Apelidos da mesma lista brasileira, mantidos para módulos que ainda usam esses identificadores.
SOUTH_AMERICAN_TEAMS = BRAZILIAN_TEAMS
RIVAL_TEAMS = BRAZILIAN_TEAMS

# CLUBES EUROPEUS: lista de equipes elegíveis para filtros e alertas da Europa.
EUROPEAN_TEAMS = [
    "AC Milan",
    "Inter Milan",
    "Juventus",
    "Paris Saint-Germain",
    "Bayern Munich",
    "Borussia Dortmund",
    "Atletico Madrid",
    "Barcelona",
    "Real Madrid",
    "Chelsea",
    "Manchester United",
    "Manchester City",
    "Tottenham",
    "Liverpool",
    "Arsenal",
    "Porto",
    "Benfica",
    "Sporting CP",
]

# Perfis Flashscore usados como referência para os clubes do filtro europeu.
EUROPEAN_TEAM_URLS = {
    "AC Milan": "https://www.flashscore.com/team/ac-milan/8Sa8HInO/",
    "Inter Milan": "https://www.flashscore.com/team/inter/Iw7eKK25/",
    "Juventus": "https://www.flashscore.com/team/juventus/C06aJvIB/",
    "Paris Saint-Germain": "https://www.flashscore.com/team/psg/CjhkPw0k/",
    "Bayern Munich": "https://www.flashscore.com/team/bayern-munich/nVp0wiqd/",
    "Borussia Dortmund": "https://www.flashscore.com/team/dortmund/nP1i5US1/",
    "Atletico Madrid": "https://www.flashscore.com/team/atl-madrid/jaarqpLQ/",
    "Barcelona": "https://www.flashscore.com/team/barcelona/SKbpVP5K/",
    "Real Madrid": "https://www.flashscore.com/team/real-madrid/W8mj7MDD/",
    "Chelsea": "https://www.flashscore.com/team/chelsea/4fGZN2oK/",
    "Manchester United": "https://www.flashscore.com/team/manchester-united/ppjDR086/",
    "Manchester City": "https://www.flashscore.com/team/manchester-city/Wtn9Stg0/",
    "Tottenham": "https://www.flashscore.com/team/tottenham/UDg08Ohm/",
    "Liverpool": "https://www.flashscore.com/team/liverpool/lId4TMwf/",
    "Arsenal": "https://www.flashscore.com/team/arsenal/hA1Zm19f/",
    "Porto": "https://www.flashscore.com.br/equipe/fc-porto/S2NmScGp/",
    "Benfica": "https://www.flashscore.com.br/equipe/benfica/zBkyuyRI/",
    "Sporting CP": "https://www.flashscore.com.br/equipe/sporting-cp/tljXuHBC/",
}

BRAZIL_NATIONAL_TEAM = "Seleção Brasileira"
BRAZIL_NATIONAL_TEAM_URL = "https://www.flashscore.com.br/equipe/brasil/I9l9aqLq/"

# ALIASES DE CLUBES: reconhecem variações de grafia e abreviações retornadas pelos provedores.
BRAZILIAN_TEAM_ALIASES = {
    "Flamengo": ("Flamengo", "Flamengo RJ", "CR Flamengo"),
    "Corinthians": ("Corinthians", "SC Corinthians", "Corinthians SP"),
    "São Paulo": ("São Paulo", "Sao Paulo", "São Paulo FC", "Sao Paulo FC"),
    "Palmeiras": ("Palmeiras", "SE Palmeiras"),
    "Santos": ("Santos", "Santos FC"),
    "Vasco da Gama": ("Vasco da Gama", "Vasco", "CR Vasco da Gama"),
    "Fluminense": ("Fluminense", "Fluminense FC"),
    "Botafogo": ("Botafogo", "Botafogo FR", "Botafogo RJ", "Botafogo de Futebol e Regatas"),
    "Atlético Mineiro": ("Atlético Mineiro", "Atletico Mineiro", "Atlético-MG", "Atletico-MG", "Atletico MG"),
    "Cruzeiro": ("Cruzeiro", "Cruzeiro EC"),
    "Grêmio": ("Grêmio", "Gremio", "Grêmio FBPA"),
    "Internacional": ("Internacional", "SC Internacional", "Internacional RS"),
}

EUROPEAN_TEAM_ALIASES = {
    "Real Madrid": ("Real Madrid", "Real Madrid CF"),
    "Barcelona": ("Barcelona", "FC Barcelona", "Barça"),
    "Bayern Munich": ("Bayern Munich", "Bayern München", "FC Bayern München"),
    "Manchester United": ("Manchester United", "Man United", "Man Utd"),
    "Liverpool": ("Liverpool", "Liverpool FC"),
    "Juventus": ("Juventus", "Juventus FC"),
    "Paris Saint-Germain": ("Paris Saint-Germain", "Paris SG", "PSG"),
    "Chelsea": ("Chelsea", "Chelsea FC"),
    "Manchester City": ("Manchester City", "Man City"),
    "Inter Milan": ("Inter Milan", "Internazionale", "Inter"),
    "AC Milan": ("AC Milan", "Milan", "Milan AC"),
    "Arsenal": ("Arsenal", "Arsenal FC"),
    "Tottenham": ("Tottenham", "Tottenham Hotspur", "Spurs"),
    "Atletico Madrid": ("Atletico Madrid", "Atlético Madrid", "Atl. Madrid", "Atletico de Madrid", "Atleti"),
    "Borussia Dortmund": ("Borussia Dortmund", "Dortmund", "BVB"),
    "Sporting CP": ("Sporting CP", "Sporting", "Sporting Clube de Portugal"),
    "Porto": ("Porto", "FC Porto", "Futebol Clube do Porto"),
    "Benfica": ("Benfica", "SL Benfica", "Sport Lisboa e Benfica"),
}

# Une os aliases em um único mapa consumido pelas funções de comparação de times.
TEAM_ALIASES = {**BRAZILIAN_TEAM_ALIASES, **EUROPEAN_TEAM_ALIASES}
TEAM_ALIASES[BRAZIL_NATIONAL_TEAM] = (
    BRAZIL_NATIONAL_TEAM, "Brasil", "Brazil", "Brazil National Team"
)

# COMPETIÇÕES MONITORADAS: nomes normalizados que determinam a região de cada partida.
SOUTH_AMERICAN_LEAGUES = {
    "brasil",
    "brazil",
    "brasileirao",
    "brasileirao serie a",
    "libertadores",
    "sulamericana",
}
EUROPEAN_LEAGUES = {
    "espanha",
    "franca",
    "inglaterra",
    "italia",
    "alemanha",
    "portugal",
    "europa",
    "champions league",
    "europa league",
    "conference league",
}

# Intervalo, em segundos, entre as execuções do monitor automático.
CHECK_INTERVAL = 70
