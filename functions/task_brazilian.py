"""Consulta o próximo jogo de Série A dos clubes brasileiros monitorados."""

import json
import os
from datetime import datetime

import pytz

from config import SOUTH_AMERICAN_TEAMS
from tasks.obter_jogos_geral import jogo_tem_time_filtrado

# Compartilha a coleta principal e o fuso usado para definir a data atual.
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dados_jogos.json")
BRAZILIAN_LEAGUE = "brasileirao serie a"
FUSO_BRASIL = pytz.timezone("America/Sao_Paulo")

# SELEÇÃO DO PRÓXIMO JOGO: considera Série A, data atual ou futura, status e clubes filtrados.
def obter_proximo_jogo_brasileirao(
    arquivo_json: str = DATA_PATH,
    times_filtro: list[str] | None = None,
) -> dict | None:
    """Retorna o próximo jogo futuro da Série A envolvendo um clube monitorado."""
    if times_filtro is None:
        times_filtro = SOUTH_AMERICAN_TEAMS

    try:
        with open(arquivo_json, "r", encoding="utf-8") as arquivo:
            jogos = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(jogos, list):
        return None

    hoje = datetime.now(FUSO_BRASIL).date().isoformat()
    jogos_futuros = []
    for jogo in jogos:
        if str(jogo.get("liga", "")).casefold().strip() != BRAZILIAN_LEAGUE:
            continue
        data_jogo = str(jogo.get("data", "")).strip()
        if not data_jogo or data_jogo < hoje:
            continue
        if str(jogo.get("tipo_status", "")).upper() != "FUTURO":
            continue
        if jogo_tem_time_filtrado(jogo, times_filtro):
            jogos_futuros.append(jogo)

    jogos_futuros.sort(
        key=lambda jogo: (jogo.get("data", "9999-12-31"), jogo.get("hora", "23:59"))
    )
    return jogos_futuros[0] if jogos_futuros else None
