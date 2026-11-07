"""Consulta, persiste e formata os detalhes dos jogos exibidos pelo bot."""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import discord

from functions.team_utils import normaliza_time, time_corresponde
from tasks.obter_jogos_geral import obter_detalhes_partida_flashscore


_ARQUIVO_DETALHES = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "detalhes_partidas.json"
)
_INTERVALO_ATUALIZACAO = timedelta(hours=12)
_INTERVALO_RECONSULTA_INCOMPLETOS = timedelta(minutes=30)
_INTERVALO_CACHE_MANDANTE_NAO_CADASTRADO = timedelta(hours=6)
_INTERVALO_CACHE_FLASHSCORE = timedelta(hours=24)
_CHAVE_ESTADIOS_FLASHSCORE_TEMPORARIOS = "_estadios_times_flashscore_temporarios"


def _ler_detalhes_persistidos():
    try:
        with open(_ARQUIVO_DETALHES, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar_detalhes_persistidos(dados):
    diretorio = os.path.dirname(_ARQUIVO_DETALHES)
    os.makedirs(diretorio, exist_ok=True)
    descritor, caminho_temporario = tempfile.mkstemp(
        prefix="detalhes_partidas_", suffix=".tmp", dir=diretorio
    )
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.replace(caminho_temporario, _ARQUIVO_DETALHES)
    finally:
        if os.path.exists(caminho_temporario):
            os.remove(caminho_temporario)


def limpar_cache_consultas():
    """Remove detalhes de partidas em cache, preservando os estÃ¡dios cadastrados."""
    detalhes_persistidos = _ler_detalhes_persistidos()
    chaves_permanentes = {
        "_estadios_times_europeus",
        "_estadios_times_sulamericanos",
    }
    dados_permanentes = {
        chave: valor
        for chave, valor in detalhes_persistidos.items()
        if chave in chaves_permanentes
    }
    secao_flashscore = detalhes_persistidos.get(
        _CHAVE_ESTADIOS_FLASHSCORE_TEMPORARIOS,
        {},
    )
    times_flashscore = (
        secao_flashscore.get("times", {})
        if isinstance(secao_flashscore, dict)
        else {}
    )
    times_flashscore_validos = {}
    agora = datetime.now(timezone.utc)
    if isinstance(times_flashscore, dict):
        for chave_time, registro_time in times_flashscore.items():
            if not isinstance(registro_time, dict):
                continue
            try:
                consultado_em = datetime.fromisoformat(registro_time["consultado_em"])
                if consultado_em.tzinfo is None:
                    consultado_em = consultado_em.replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            tem_localizacao = any(
                str(registro_time.get(campo, "")).strip()
                for campo in ("estadio", "cidade", "pais")
            )
            if tem_localizacao and agora - consultado_em < _INTERVALO_CACHE_FLASHSCORE:
                times_flashscore_validos[chave_time] = registro_time
    if times_flashscore_validos:
        dados_permanentes[_CHAVE_ESTADIOS_FLASHSCORE_TEMPORARIOS] = {
            "times": times_flashscore_validos,
        }

    removidos = len(detalhes_persistidos) - len(dados_permanentes)
    _gravar_detalhes_persistidos(dados_permanentes)
    return removidos


def _times_com_estadio_cadastrado(detalhes_persistidos):
    times_cadastrados = []
    for chave_secao in (
        "_estadios_times_europeus",
        "_estadios_times_sulamericanos",
    ):
        secao = detalhes_persistidos.get(chave_secao, {})
        times = secao.get("times", {}) if isinstance(secao, dict) else {}
        if isinstance(times, dict):
            times_cadastrados.extend(times)
    return times_cadastrados


def _mandante_nao_cadastrado_com_time_filtrado(jogo, detalhes_persistidos):
    times_cadastrados = _times_com_estadio_cadastrado(detalhes_persistidos)
    if not times_cadastrados:
        return False

    mandante = str(jogo.get("mandante", "")).strip()
    visitante = str(jogo.get("visitante", "")).strip()
    mandante_cadastrado = any(
        time_corresponde(mandante, nome) for nome in times_cadastrados
    )
    visitante_cadastrado = any(
        time_corresponde(visitante, nome) for nome in times_cadastrados
    )
    return visitante_cadastrado and not mandante_cadastrado


def _detalhe_expirado(registro, jogo, agora, detalhes_persistidos):
    """Reconsulta detalhes incompletos e atualiza árbitros de jogos futuros."""
    try:
        consultado_em = datetime.fromisoformat(registro["consultado_em"])
        if consultado_em.tzinfo is None:
            consultado_em = consultado_em.replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return True

    localizacao_incompleta = any(
        not str(registro.get(campo, "")).strip()
        for campo in ("estadio", "cidade", "pais")
    )
    if localizacao_incompleta:
        if _mandante_nao_cadastrado_com_time_filtrado(jogo, detalhes_persistidos):
            return agora - consultado_em >= _INTERVALO_CACHE_MANDANTE_NAO_CADASTRADO
        return agora - consultado_em >= _INTERVALO_RECONSULTA_INCOMPLETOS

    if (
        str(jogo.get("tipo_status", "")).upper() == "FUTURO"
        and not str(registro.get("arbitro", "")).strip()
    ):
        return agora - consultado_em >= _INTERVALO_ATUALIZACAO
    return False


def _campos_exibiveis(registro):
    return {
        campo: registro[campo]
        for campo in ("estadio", "cidade", "pais", "arbitro")
        if str(registro.get(campo, "")).strip()
    }


def _completar_localizacao_mandante(registro, jogo, detalhes_persistidos):
    """Usa o estádio cadastrado do clube mandante quando o feed omite o local."""
    registro_completo = dict(registro)
    mandante = str(jogo.get("mandante", "")).strip()

    for chave_secao in (
        "_estadios_times_europeus",
        "_estadios_times_sulamericanos",
        _CHAVE_ESTADIOS_FLASHSCORE_TEMPORARIOS,
    ):
        dados_estadios = detalhes_persistidos.get(chave_secao, {})
        times = dados_estadios.get("times", {}) if isinstance(dados_estadios, dict) else {}
        if not isinstance(times, dict):
            continue

        for nome_time, dados_time in times.items():
            nome_comparacao = dados_time.get("nome", nome_time) if isinstance(dados_time, dict) else nome_time
            if not isinstance(dados_time, dict) or not time_corresponde(mandante, nome_comparacao):
                continue
            if chave_secao == _CHAVE_ESTADIOS_FLASHSCORE_TEMPORARIOS:
                try:
                    consultado_em = datetime.fromisoformat(dados_time["consultado_em"])
                    if consultado_em.tzinfo is None:
                        consultado_em = consultado_em.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - consultado_em >= _INTERVALO_CACHE_FLASHSCORE:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue
            for campo in ("estadio", "cidade", "pais"):
                if not str(registro_completo.get(campo, "")).strip():
                    valor = str(dados_time.get(campo, "")).strip()
                    if valor:
                        registro_completo[campo] = valor
            return registro_completo
    return registro_completo


def _guardar_localizacao_flashscore_mandante(detalhes_persistidos, jogo, perfil, agora):
    """Guarda temporariamente os dados obtidos no perfil Flashscore do mandante."""
    if not isinstance(perfil, dict):
        return
    valores = {
        campo: str(perfil.get(campo, "")).strip()
        for campo in ("estadio", "cidade", "pais")
        if str(perfil.get(campo, "")).strip()
    }
    if not valores:
        return

    mandante = str(jogo.get("mandante", "")).strip()
    chave_time = normaliza_time(mandante)
    if not chave_time:
        return

    secao = detalhes_persistidos.setdefault(
        _CHAVE_ESTADIOS_FLASHSCORE_TEMPORARIOS,
        {"times": {}},
    )
    times = secao.setdefault("times", {})
    registro_time = times.setdefault(chave_time, {"nome": mandante})
    registro_time.update(valores)
    registro_time["nome"] = mandante
    registro_time["consultado_em"] = agora.isoformat()
    registro_time["fonte"] = "Flashscore"
    if perfil.get("url"):
        registro_time["flashscore_url"] = perfil["url"]


async def obter_detalhes_dos_jogos(jogos):
    """Carrega o JSON local e consulta apenas partidas sem dados atuais."""
    agora = datetime.now(timezone.utc)
    detalhes_persistidos = _ler_detalhes_persistidos()
    loop = asyncio.get_running_loop()
    limite_concorrencia = asyncio.Semaphore(5)
    jogos_por_id = {
        str(jogo.get("id")): jogo
        for jogo in jogos
        if jogo.get("id")
    }

    async def carregar(identificador, jogo):
        registro = detalhes_persistidos.get(identificador, {})
        if not isinstance(registro, dict):
            registro = {}

        if registro and not _detalhe_expirado(
            registro, jogo, agora, detalhes_persistidos
        ):
            registro_completo = _completar_localizacao_mandante(
                registro, jogo, detalhes_persistidos
            )
            atualizado = registro_completo != registro
            if atualizado:
                detalhes_persistidos[identificador] = registro_completo
            return identificador, _campos_exibiveis(registro_completo), atualizado

        try:
            async with limite_concorrencia:
                detalhes = await loop.run_in_executor(
                    None, obter_detalhes_partida_flashscore, identificador
                )
        except Exception as error:
            print(
                f"[PARTIDA] Não foi possível consultar os detalhes de "
                f"{identificador}: {error}"
            )
            detalhes = {}

        # Mantém informações já coletadas se uma consulta posterior vier incompleta.
        if (
            _mandante_nao_cadastrado_com_time_filtrado(jogo, detalhes_persistidos)
            and isinstance(detalhes, dict)
        ):
            _guardar_localizacao_flashscore_mandante(
                detalhes_persistidos,
                jogo,
                detalhes.get("perfil_mandante", {}),
                agora,
            )

        registro_atualizado = dict(registro)
        for campo, valor in _campos_exibiveis(detalhes or {}).items():
            registro_atualizado[campo] = valor
        registro_atualizado = _completar_localizacao_mandante(
            registro_atualizado, jogo, detalhes_persistidos
        )
        registro_atualizado["consultado_em"] = agora.isoformat()
        detalhes_persistidos[identificador] = registro_atualizado
        return identificador, _campos_exibiveis(registro_atualizado), True

    resultados = await asyncio.gather(
        *(carregar(identificador, jogo) for identificador, jogo in jogos_por_id.items())
    )
    if any(gravou for _, _, gravou in resultados):
        try:
            _gravar_detalhes_persistidos(detalhes_persistidos)
        except OSError as error:
            print(f"[PARTIDA] Não foi possível salvar o cache de detalhes: {error}")
    return {identificador: detalhes for identificador, detalhes, _ in resultados}


def adicionar_campos_local_arbitragem(embed, detalhes):
    """Adiciona os dados da partida em campos separados do embed do Discord."""
    detalhes = detalhes or {}
    estadio = str(detalhes.get("estadio", "")).strip()
    cidade = str(detalhes.get("cidade", "")).strip()
    pais = str(detalhes.get("pais", "")).strip()

    embed.add_field(
        name="🏟 Estádio",
        value=discord.utils.escape_markdown(estadio) if estadio else "Ainda não informado",
        inline=True,
    )
    embed.add_field(
        name="📍 Cidade",
        value=discord.utils.escape_markdown(cidade) if cidade else "Ainda não informada",
        inline=True,
    )
    embed.add_field(
        name="🌎 País",
        value=discord.utils.escape_markdown(pais) if pais else "Ainda não informado",
        inline=True,
    )
    arbitro = str(detalhes.get("arbitro", "")).strip()
    if arbitro:
        embed.add_field(
            name="⚖️ Árbitro",
            value=discord.utils.escape_markdown(arbitro),
            inline=True,
        )
    else:
        embed.add_field(
            name="⚖️ Árbitro",
            value="Ainda não divulgado",
            inline=True,
        )
    return embed


def formatar_local_arbitragem(detalhes):
    """Formata os mesmos dados para os embeds dos alertas automáticos."""
    detalhes = detalhes or {}
    estadio = str(detalhes.get("estadio", "")).strip()
    cidade = str(detalhes.get("cidade", "")).strip()
    pais = str(detalhes.get("pais", "")).strip()

    linhas = [
        f"🏟 Estádio: {discord.utils.escape_markdown(estadio) if estadio else 'ainda não informado'}",
        f"📍 Cidade: {discord.utils.escape_markdown(cidade) if cidade else 'ainda não informada'}",
        f"🌎 País: {discord.utils.escape_markdown(pais) if pais else 'ainda não informado'}",
    ]
    arbitro = str(detalhes.get("arbitro", "")).strip()
    if arbitro:
        linhas.append(f"⚖️ Árbitro: {discord.utils.escape_markdown(arbitro)}")
    else:
        linhas.append("⚖️ Árbitro: ainda não divulgado")
    return "\n".join(linhas)
