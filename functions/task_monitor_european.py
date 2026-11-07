"""Acompanha início, mudanças de placar e encerramento dos jogos europeus."""

import json
import os

import discord

from config import EUROPEAN_LEAGUES, EUROPEAN_TEAMS
from functions.team_utils import jogo_tem_time_europeu
from functions.task_match_info import obter_detalhes_dos_jogos, formatar_local_arbitragem

# Lê o JSON gerado pela coleta principal e conserva o estado entre execuções do monitor.
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dados_jogos.json")
# Guarda o último status e placar de cada jogo para detectar mudanças.
_estado_partidas: dict[str, dict[str, str]] = {}
_estados_por_servidor: dict[str, dict[str, dict[str, str]]] = {}

# Cria uma chave estável para reconhecer a mesma partida entre ciclos.
def _chave_partida(jogo: dict) -> str:
    campos = (
        jogo.get("liga", ""), jogo.get("data", ""), jogo.get("hora", ""),
        jogo.get("mandante", ""), jogo.get("visitante", ""),
    )
    return "|".join(str(campo).strip().casefold() for campo in campos)

# Abre e valida o JSON antes de iniciar as comparações.
def _ler_jogos(caminho: str) -> list[dict] | None:
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        return dados if isinstance(dados, list) else None
    except (OSError, json.JSONDecodeError):
        return None

# Compara cada partida ao estado salvo e monta embeds com o placar e a mudança detectada.
async def verificar_partidas_europeias(
    bot: discord.Client,
    canal_id: int,
    times: list[str] | None = None,
    caminho: str = DATA_PATH,
    state_key=None,
) -> None:
    """Envia uma atualização apenas quando uma partida monitorada muda."""
    times_monitorados = EUROPEAN_TEAMS if times is None else times
    estado_partidas = (
        _estado_partidas
        if state_key is None
        else _estados_por_servidor.setdefault(str(state_key), {})
    )
    jogos = _ler_jogos(caminho)
    if jogos is None:
        print(f"[EUROPA] Não foi possível ler os jogos em {caminho}")
        return

    canal = bot.get_channel(canal_id)
    if canal is None:
        try:
            canal = await bot.fetch_channel(canal_id)
        except discord.HTTPException as error:
            print(f"[EUROPA] Canal Discord não encontrado (ID: {canal_id}): {error}")
            return

    chaves_atuais: set[str] = set()
    for jogo in jogos:
        if str(jogo.get("liga", "")).casefold().strip() not in EUROPEAN_LEAGUES:
            continue
        if not jogo_tem_time_europeu(jogo, times_monitorados):
            continue

        chave = _chave_partida(jogo)
        chaves_atuais.add(chave)
        status = str(jogo.get("tipo_status", "DESCONHECIDO")).upper()
        placar = str(jogo.get("placar", "x")).strip()
        anterior = estado_partidas.get(chave)

        if anterior is None:
            estado_partidas[chave] = {"status": status, "placar": placar}
            if status != "AO_VIVO":
                continue
            titulo = "🇪🇺 Partida europeia ao vivo"
            cor = 0x2ECC71
            detalhe = "Partida identificada em andamento."
        elif anterior["placar"] != placar and status != "ENCERRADO":
            titulo = "⚽ Gol / atualização de placar"
            cor = 0xF1C40F
            detalhe = f"Placar anterior: **{anterior['placar']}**."
            estado_partidas[chave] = {"status": status, "placar": placar}
        elif anterior["status"] != status:
            if status == "AO_VIVO":
                titulo, cor, detalhe = "🇪🇺 Partida europeia começou", 0x2ECC71, "A bola está rolando."
            elif status == "ENCERRADO":
                titulo, cor, detalhe = "🏁 Partida europeia encerrada", 0x5865F2, "Resultado final."
            else:
                titulo, cor, detalhe = "🇪🇺 Status da partida atualizado", 0x3498DB, f"Novo status: **{status}**."
            estado_partidas[chave] = {"status": status, "placar": placar}
        else:
            continue

        detalhes_por_id = await obter_detalhes_dos_jogos([jogo])
        detalhes = detalhes_por_id.get(str(jogo.get("id")), {})
        # O alerta reúne placar, detalhe da mudança e competição no padrão do monitor automático.
        embed = discord.Embed(
            title=titulo,
            description=(
                f"**{jogo.get('mandante', '?')} {placar} {jogo.get('visitante', '?')}**\n"
                f"{detalhe}\n"
                f"🏆 {jogo.get('liga', 'Competição europeia')} · {jogo.get('status', status)}\n"
                f"{formatar_local_arbitragem(detalhes)}"
            ),
            color=cor,
        )
        await canal.send(embed=embed)

    # Descarta partidas antigas para limitar o estado mantido em memória.
    for chave in set(estado_partidas) - chaves_atuais:
        estado_partidas.pop(chave, None)
