"""Monitora partidas sul-americanas ao vivo e alerta quando a situação dos rivais muda."""

import json
import os
import discord
from config import SOUTH_AMERICAN_LEAGUES
from functions.team_utils import time_corresponde
from functions.task_match_info import obter_detalhes_dos_jogos, formatar_local_arbitragem
from datetime import datetime

# Caminho do arquivo atualizado pelo job.
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dados_jogos.json")

# Estado anterior dos jogos: chave = "mandante_visitante", valor = dict com situação e placar
# Cache de placar e situação usado para evitar alertas repetidos entre ciclos.
_estado_anterior: dict[str, dict] = {}
_estados_por_servidor: dict[str, dict[str, dict]] = {}

# Estado anterior do próximo jogo europeu
_proximo_jogo_europeu_anterior: dict = {}
_proximo_jogo_brasileiro_anterior: dict = {}
_proximos_europeus_por_servidor: dict[str, dict] = {}
_proximos_brasileiros_por_servidor: dict[str, dict] = {}

SIT_LABEL = {
    "winning": "VENCENDO  ✅",
    "drawing":  "EMPATANDO ⚠️",
    "losing":   "PERDENDO  🚨",
}

# AUXILIARES: identificam clubes, status e mudanças relevantes no placar.
def _log(tag: str, msg: str) -> None:
    hora = datetime.now().strftime("%H:%M:%S")
    print(f"[{hora}] [{tag}] {msg}")

def _is_rival(team_name: str, rival_teams: list[str]) -> bool:
    return any(time_corresponde(team_name, rival) for rival in rival_teams)

def _is_europeu(team_name: str, european_teams: list[str]) -> bool:
    return any(time_corresponde(team_name, europeu) for europeu in european_teams)

def _parse_placar(placar: str) -> tuple[int, int] | None:
    """
    Converte '2 x 1' em (2, 1).
    Retorna None se o placar for 'x' (jogo ainda não começou).
    """
    partes = placar.strip().split("x")
    if len(partes) != 2:
        return None
    try:
        return int(partes[0].strip()), int(partes[1].strip())
    except ValueError:
        return None  # placar = "x" — jogo não iniciado

def _is_live(jogo: dict) -> bool:
    return jogo.get("tipo_status", "").upper() == "AO_VIVO"

def _is_finished(jogo: dict) -> bool:
    return jogo.get("tipo_status", "").upper() == "ENCERRADO"

def _is_future(jogo: dict) -> bool:
    return jogo.get("tipo_status", "").upper() == "FUTURO"

def _situacao_rival(placar: tuple[int, int], rival_is_home: bool) -> str:
    """Retorna 'winning', 'drawing' ou 'losing' do ponto de vista do rival."""
    rival_g = placar[0] if rival_is_home else placar[1]
    opp_g   = placar[1] if rival_is_home else placar[0]
    if rival_g > opp_g:
        return "winning"
    if rival_g == opp_g:
        return "drawing"
    return "losing"

def _chave(jogo: dict) -> str:
    return f"{jogo['mandante'].strip().lower()}_{jogo['visitante'].strip().lower()}"

# CICLO DE MONITORAMENTO: processa jogos ao vivo, atualiza caches e avalia os próximos confrontos.
async def verificar_resenha(bot: discord.ext.commands.Bot, alert_channel_id: int, rival_teams: list[str], european_teams: list[str], proximo_jogo_europeu_func=None, proximo_jogo_brasileiro_func=None, state_key=None) -> None:
    """
    Lê dados_jogos.json, compara com estado anterior e envia alertas
    apenas quando a situação do rival muda.
    Também monitora o próximo jogo europeu e o próximo jogo do Brasileirão
    quando as respectivas funções são fornecidas.
    Deve ser chamada dentro de um loop periódico (tasks.loop).
    """
    print("🔍 [Resenha] Verificando jogos para possíveis resenhas...")
    global _estado_anterior, _proximo_jogo_europeu_anterior
    global _proximo_jogo_brasileiro_anterior
    if state_key is None:
        estado_anterior = _estado_anterior
        proximo_europeu_anterior = _proximo_jogo_europeu_anterior
        proximo_brasileiro_anterior = _proximo_jogo_brasileiro_anterior
    else:
        chave_estado = str(state_key)
        estado_anterior = _estados_por_servidor.setdefault(chave_estado, {})
        proximo_europeu_anterior = _proximos_europeus_por_servidor.setdefault(
            chave_estado, {}
        )
        proximo_brasileiro_anterior = _proximos_brasileiros_por_servidor.setdefault(
            chave_estado, {}
        )

    _log("MONITOR", "=" * 55)
    _log("MONITOR", "Iniciando ciclo de monitoramento...")

    # ── Lê o arquivo ────────────────────────────────────────────
    try:
        if not os.path.exists(DATA_PATH):
            _log("ERRO", f"Arquivo não encontrado: {DATA_PATH}")
            return

        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            jogos: list[dict] = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _log("ERRO", f"Falha ao ler JSON: {e}")
        return

    _log("MONITOR", f"JSON carregado — {len(jogos)} jogo(s) encontrado(s)")

    channel = bot.get_channel(alert_channel_id)
    if channel is None:
        _log("ERRO", f"Canal Discord não encontrado (ID: {alert_channel_id})")
        return

    # Contadores do ciclo
    encerrados   = 0
    futuros      = 0
    outros_status = 0
    sem_placar   = 0
    ao_vivo      = 0
    sem_rival    = 0
    sem_europeus = 0
    monitorados  = 0
    sem_mudanca  = 0
    alertas      = 0

    for jogo in jogos:
        mandante   = jogo.get("mandante", "").strip()
        visitante  = jogo.get("visitante", "").strip()
        placar_str = jogo.get("placar", "").strip()
        status     = jogo.get("status", "").strip()
        partida    = f"{mandante} x {visitante}"
        liga = str(jogo.get("liga", "")).casefold().strip()
        if liga not in SOUTH_AMERICAN_LEAGUES:
            continue

        # Descarta encerrados
        if _is_finished(jogo):
            encerrados += 1
            continue

        if _is_future(jogo):
            futuros += 1
            continue

        if not _is_live(jogo):
            outros_status += 1
            continue

        placar = _parse_placar(placar_str)
        if placar is None:
            sem_placar += 1
            continue

        ao_vivo += 1

        # Verifica se tem rival
        rival_is_home = _is_rival(mandante, rival_teams)
        rival_is_away = _is_rival(visitante, rival_teams)
        europeu_is_home = _is_europeu(mandante, european_teams)
        europeu_is_away = _is_europeu(visitante, european_teams)

        if europeu_is_home and europeu_is_away:
            _log("INFO", f"{partida} — ambos europeus, ignorando")
            sem_europeus += 1
            continue

        if not rival_is_home and not rival_is_away:
            _log("INFO", f"{partida} [{placar_str}] — sem rival, ignorando")
            sem_rival += 1
            continue

        if rival_is_home and rival_is_away:
            _log("INFO", f"{partida} — ambos rivais, ignorando")
            sem_rival += 1
            continue

        monitorados += 1
        europeu  = mandante if europeu_is_home else visitante
        rival    = mandante if rival_is_home else visitante
        opponent = visitante if rival_is_home else mandante

        sit_atual   = _situacao_rival(placar, rival_is_home)
        chave       = _chave(jogo)
        anterior    = estado_anterior.get(chave, {})
        sit_prev    = anterior.get("sit")
        placar_prev = anterior.get("placar")

        sit_prev_label = SIT_LABEL.get(sit_prev, "NOVO JOGO  🆕")
        sit_atual_label = SIT_LABEL[sit_atual]

        _log("RIVAL", f"{rival} | {placar_str} | {sit_prev_label} → {sit_atual_label}")

        situacao_mudou = sit_atual != sit_prev
        placar_mudou   = placar_str != placar_prev

        if not situacao_mudou and not (placar_mudou and sit_atual in ("losing", "drawing")):
            _log("OK", f"{rival} — sem mudança, nenhum alerta enviado")
            sem_mudanca += 1
            estado_anterior[chave] = {"sit": sit_atual, "placar": placar_str}
            continue

        # ── ALERTA: rival começou a perder ou empatou saindo de vitória ──
        if sit_atual in ("losing", "drawing") and sit_prev == "winning":
            detalhes = await obter_detalhes_dos_jogos([jogo])
            local_arbitragem = formatar_local_arbitragem(
                detalhes.get(str(jogo.get("id")), {})
            )
            if sit_atual == "losing":
                descricao = f"😂 **{rival}** está **PERDENDO** para **{opponent}**!"
            else:
                descricao = f"😬 **{rival}** **EMPATOU** com **{opponent}**!"

            embed = discord.Embed(
                title="🚨 POSSÍVEL RESENHA! 🚨",
                description=(
                    f"@everyone\n\n"
                    f"{descricao}\n\n"
                    f"⚔️ **{mandante} {placar_str} {visitante}**\n"
                    f"📍 {status}\n"
                    f"{local_arbitragem}"
                ),
                color=0xFF4444,
            )
            embed.set_footer(text="Brasileirão • ao vivo")
            await channel.send(content="@everyone", embed=embed)
            _log("ALERTA", f"🚨 RESENHA enviada! {rival} {sit_atual_label} | {placar_str}")
            alertas += 1

        # ── ALERTA: rival entrou ao vivo já perdendo/empatando ──────────
        elif sit_atual in ("losing", "drawing") and sit_prev is None:
            detalhes = await obter_detalhes_dos_jogos([jogo])
            local_arbitragem = formatar_local_arbitragem(
                detalhes.get(str(jogo.get("id")), {})
            )
            if sit_atual == "losing":
                descricao = f"😂 **{rival}** já está **PERDENDO** para **{opponent}**!"
            else:
                descricao = f"😬 **{rival}** começa **EMPATANDO** com **{opponent}**."

            embed = discord.Embed(
                title="🚨 POSSÍVEL RESENHA! 🚨",
                description=(
                    f"@everyone\n\n"
                    f"{descricao}\n\n"
                    f"⚔️ **{mandante} {placar_str} {visitante}**\n"
                    f"📍 {status}\n"
                    f"{local_arbitragem}"
                ),
                color=0xFF4444,
            )
            embed.set_footer(text="Brasileirão • ao vivo")
            await channel.send(content="@everyone", embed=embed)
            _log("ALERTA", f"🚨 RESENHA (início detectado) | {rival} {sit_atual_label} | {placar_str}")
            alertas += 1

        # ── ALERTA: rival virou o jogo ───────────────────────────────────
        elif sit_atual == "winning" and sit_prev in ("losing", "drawing"):
            detalhes = await obter_detalhes_dos_jogos([jogo])
            local_arbitragem = formatar_local_arbitragem(
                detalhes.get(str(jogo.get("id")), {})
            )
            embed = discord.Embed(
                title="✅ RESENHA CANCELADA",
                description=(
                    f"@everyone\n\n"
                    f"😒 **{rival}** virou o jogo contra **{opponent}**. Acabou a festa.\n\n"
                    f"⚔️ **{mandante} {placar_str} {visitante}**\n"
                    f"📍 {status}\n"
                    f"{local_arbitragem}"
                ),
                color=0x44BB44,
            )
            embed.set_footer(text="Brasileirão • ao vivo")
            await channel.send(content="@everyone", embed=embed)
            _log("ALERTA", f"✅ RESENHA CANCELADA | {rival} virou | {placar_str}")
            alertas += 1

        # ── Placar mudou, rival continua sofrendo ────────────────────────
        elif sit_atual in ("losing", "drawing") and placar_mudou and sit_prev in ("losing", "drawing"):
            detalhes = await obter_detalhes_dos_jogos([jogo])
            local_arbitragem = formatar_local_arbitragem(
                detalhes.get(str(jogo.get("id")), {})
            )
            if sit_atual == "losing":
                descricao = f"😂 **{rival}** continua **PERDENDO** — tomou mais um!"
            else:
                descricao = f"😬 **{rival}** segue **EMPATADO** com **{opponent}**."

            embed = discord.Embed(
                title="🚨 RESENHA CONTINUA! 🚨",
                description=(
                    f"@everyone\n\n"
                    f"{descricao}\n\n"
                    f"⚔️ **{mandante} {placar_str} {visitante}**\n"
                    f"📍 {status}\n"
                    f"{local_arbitragem}"
                ),
                color=0xFF8800,
            )
            embed.set_footer(text="Brasileirão • ao vivo")
            await channel.send(content="@everyone", embed=embed)
            _log("ALERTA", f"🔥 RESENHA CONTINUA | {rival} | {placar_prev} → {placar_str}")
            alertas += 1

        # Atualiza estado
        estado_anterior[chave] = {"sit": sit_atual, "placar": placar_str}

    # ── Limpa jogos encerrados do estado ────────────────────────
    chaves_ativas = {
        _chave(j) for j in jogos
        if (
            str(j.get("liga", "")).casefold().strip() in SOUTH_AMERICAN_LEAGUES
            and _is_live(j)
            and _parse_placar(j.get("placar", "")) is not None
            and any(
                _is_rival(str(j.get(campo, "")).strip(), rival_teams)
                for campo in ("mandante", "visitante")
            )
        )
    }
    removidos = []
    for chave in list(estado_anterior.keys()):
        if chave not in chaves_ativas:
            estado_anterior.pop(chave, None)
            removidos.append(chave)

    if removidos:
        _log("CLEANUP", f"Removido(s) do estado: {', '.join(removidos)}")

    # ── Monitorar próximo jogo europeu ───────────────────────────
    if proximo_jogo_europeu_func is not None:
        try:
            proximo_jogo = proximo_jogo_europeu_func()

            if proximo_jogo:
                mandante_euro = proximo_jogo.get('mandante', '?')
                visitante_euro = proximo_jogo.get('visitante', '?')
                data_euro = proximo_jogo.get('data', 'N/A')
                hora_euro = proximo_jogo.get('hora', 'N/A')
                liga_euro = proximo_jogo.get('liga', 'N/A')
                chave_euro = f"{mandante_euro}_{visitante_euro}"

                # Verifica se mudou para alertar
                anterior_euro = proximo_europeu_anterior.get('chave')

                if anterior_euro != chave_euro:
                    _log("EUROPEU", f"Próximo jogo: {mandante_euro} vs {visitante_euro} em {data_euro} às {hora_euro}")
                    detalhes = await obter_detalhes_dos_jogos([proximo_jogo])
                    local_arbitragem = formatar_local_arbitragem(
                        detalhes.get(str(proximo_jogo.get("id")), {})
                    )

                    # Envia alerta sobre o novo próximo jogo
                    embed = discord.Embed(
                        title="🇪🇺 PRÓXIMO JOGO EUROPEU",
                        description=(
                            f"⚽ **{mandante_euro}** vs **{visitante_euro}**\n\n"
                            f"📅 Data: {data_euro}\n"
                            f"⏰ Hora: {hora_euro}\n"
                            f"🏆 Liga: {liga_euro}\n"
                            f"{local_arbitragem}"
                        ),
                        color=0x0066CC,
                    )
                    embed.set_footer(text="Campeonato Europeu • Monitoramento Automático")
                    await channel.send(embed=embed)
                    _log("ALERTA", f"✅ Próximo jogo europeu alertado: {mandante_euro} vs {visitante_euro}")

                    proximo_europeu_anterior['chave'] = chave_euro
        except Exception as e:
            _log("ERRO", f"Erro ao monitorar próximo jogo europeu: {e}")

    # ── Monitorar próximo jogo do Brasileirão ─────────────────────
    if proximo_jogo_brasileiro_func is not None:
        try:
            proximo_jogo = proximo_jogo_brasileiro_func()
            if proximo_jogo:
                mandante = proximo_jogo.get("mandante", "?")
                visitante = proximo_jogo.get("visitante", "?")
                data = proximo_jogo.get("data", "N/A")
                hora = proximo_jogo.get("hora", "N/A")
                liga = proximo_jogo.get("liga", "Brasileirão Série A")
                chave = f"{liga}_{data}_{hora}_{mandante}_{visitante}".casefold()

                if proximo_brasileiro_anterior.get("chave") != chave:
                    try:
                        data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
                    except (TypeError, ValueError):
                        data_formatada = data
                    detalhes = await obter_detalhes_dos_jogos([proximo_jogo])
                    local_arbitragem = formatar_local_arbitragem(
                        detalhes.get(str(proximo_jogo.get("id")), {})
                    )
                    embed = discord.Embed(
                        title="🇧🇷 PRÓXIMO JOGO DO BRASILEIRÃO",
                        description=(
                            f"⚽ **{mandante}** vs **{visitante}**\n\n"
                            f"📅 Data: {data_formatada}\n"
                            f"⏰ Hora: {hora}\n"
                            f"🏆 Liga: [Brasileirão Série A](https://www.flashscore.com/football/brazil/serie-a/#/hdLUdQGi/standings/overall/)\n"
                            f"{local_arbitragem}"
                        ),
                        color=0x009739,
                    )
                    embed.set_footer(text="Brasileirão Série A • Monitoramento Automático")
                    await channel.send(embed=embed)
                    proximo_brasileiro_anterior["chave"] = chave
                    _log("ALERTA", f"✅ Próximo jogo do Brasileirão alertado: {mandante} vs {visitante}")
        except Exception as e:
            _log("ERRO", f"Erro ao monitorar próximo jogo do Brasileirão: {e}")

    # ── Resumo do ciclo ──────────────────────────────────────────
    _log("RESUMO", f"Total no arquivo: {len(jogos)} | Ao vivo: {ao_vivo} | "
                   f"Encerrados: {encerrados} | Futuros: {futuros} | "
                   f"Outros status: {outros_status} | Sem placar: {sem_placar} | "
                   f"Sem rival: {sem_rival} | Ambos europeus: {sem_europeus} | "
                   f"Monitorados: {monitorados} | "
                   f"Sem mudança: {sem_mudanca} | Alertas: {alertas}")
    _log("MONITOR", "Ciclo finalizado.")
    _log("MONITOR", "=" * 55)
