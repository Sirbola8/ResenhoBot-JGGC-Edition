"""Normaliza nomes e compara clubes monitorados entre diferentes provedores."""

import unicodedata

from config import TEAM_ALIASES

# Remove acentos e pontuação para comparar nomes sem depender da grafia do provedor.
def normaliza_time(nome: str) -> str:
    nome = unicodedata.normalize("NFKD", nome or "")
    sem_acentos = "".join(char for char in nome if not unicodedata.combining(char))
    return "".join(char for char in sem_acentos.casefold() if char.isalnum())

# Consulta aliases de configuração e verifica se o nome recebido corresponde ao clube.
def time_corresponde(nome_encontrado: str, time_configurado: str) -> bool:
    encontrado = normaliza_time(nome_encontrado)
    if not encontrado:
        return False

    aliases = TEAM_ALIASES.get(time_configurado, (time_configurado,))
    return encontrado in {normaliza_time(alias) for alias in aliases if alias}

# Aplica a comparação por aliases aos dois lados da partida.
def jogo_tem_time_filtrado(jogo: dict, times: list[str]) -> bool:
    return any(
        time_corresponde(nome, time)
        for nome in (jogo.get("mandante", ""), jogo.get("visitante", ""))
        for time in times
    )

# Mantém uma interface explícita para os módulos que filtram clubes europeus.
def jogo_tem_time_europeu(jogo: dict, times: list[str]) -> bool:
    return jogo_tem_time_filtrado(jogo, times)
