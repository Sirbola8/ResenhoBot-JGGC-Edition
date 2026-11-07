"""Coleta jogos do Flashscore e normaliza os dados usados pelo restante do bot."""

import html as html_lib
import re
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag
from urllib.request import Request, urlopen

import pytz

from config import (
    BRAZIL_NATIONAL_TEAM, BRAZIL_NATIONAL_TEAM_URL,
    EUROPEAN_TEAMS, EUROPEAN_TEAM_URLS, SOUTH_AMERICAN_TEAMS,
)
from functions.team_utils import time_corresponde

# COMPETIÇÕES E FEEDS: URLs de origem e padrão que localiza os dados embutidos nas páginas.
FLASHSCORE_COMPETITIONS = (
    ("https://www.flashscore.com/football/brazil/serie-a/#/hdLUdQGi/standings/overall/", "brasileirao serie a"),
    ("https://www.flashscore.com/football/italy/serie-a/#/CfujcOgK/standings/overall/", "italia"),
    ("https://www.flashscore.com/football/england/premier-league/#/CfoA8Dmm/standings/overall/", "inglaterra"),
    ("https://www.flashscore.com/football/france/ligue-1/#/CQF28KxR/standings/overall/", "franca"),
    ("https://www.flashscore.com/football/germany/bundesliga/#/jg0MwVuC/standings/overall/", "alemanha"),
    ("https://www.flashscore.com/football/spain/laliga/#/dWdJXP6U/standings/overall/", "espanha"),
    ("https://www.flashscore.com/football/europe/champions-league/#/vT1iNRGq/standings/overall/", "champions league"),
    ("https://www.flashscore.com/football/europe/europa-league/#/OjQOTQKa/standings/overall/", "europa league"),
    ("https://www.flashscore.com/football/europe/conference-league/#/8WHkz50k/standings/overall/", "conference league"),
    ("https://www.flashscore.com/football/south-america/copa-libertadores/#/SlYIvtWi/draw/", "libertadores"),
    ("https://www.flashscore.com/football/south-america/copa-sudamericana/#/6m37slS7/draw/", "sulamericana"),
)
FLASHSCORE_GROUP_STANDINGS = {
    "libertadores": "https://www.flashscore.com.br/futebol/america-do-sul/copa-libertadores/classificacao/dQHOGxvo/classificacoes/geral/",
    "sulamericana": "https://www.flashscore.com.br/futebol/america-do-sul/copa-sul-americana/classificacao/2e6joWSr/classificacoes/geral/",
    "copa do mundo": "https://www.flashscore.com.br/futebol/mundo/campeonato-do-mundo/classificacao/SbLsX4y7/",
}
FLASHSCORE_GROUP_FEED_IDS = {
    "libertadores": "dQHOGxvo",
    "sulamericana": "2e6joWSr",
    "copa do mundo": "SbLsX4y7",
}
FLASHSCORE_GROUP_FEED_BASE = "https://global.flashscore.ninja/401/x/feed/to_"
FLASHSCORE_FEED_SIGNATURE = "SW9D1eZo"
FLASHSCORE_INITIAL_FEEDS = re.compile(
    r'cjs\.initialFeeds\["([^"]+)"\]\s*=\s*\{\s*data:\s*`([^`]*)`',
    re.DOTALL,
)
FUSO_BRASIL = pytz.timezone("America/Sao_Paulo")
_CACHE_ESTADIO_TIMES = {}
_CACHE_ESTADIO_TIMES_TTL = timedelta(hours=12)


def obter_classificacao_fase_grupos(torneio):
    """Busca e converte a classificação por grupos do feed do Flashscore."""
    url = FLASHSCORE_GROUP_STANDINGS.get(str(torneio or "").casefold().strip())
    if not url:
        raise ValueError(f"Torneio sem classificação configurada: {torneio}")

    headers_pagina = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "User-Agent": "ResenhoBot/1.0",
    }
    try:
        with urlopen(Request(url, headers=headers_pagina), timeout=20) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"Falha ao consultar a página do torneio: {error}") from error

    identificador_temporada = _identificar_temporada_flashscore(html)
    identificador_classificacao = FLASHSCORE_GROUP_FEED_IDS[
        str(torneio or "").casefold().strip()
    ]
    feed_url = (
        f"{FLASHSCORE_GROUP_FEED_BASE}{identificador_temporada}_"
        f"{identificador_classificacao}_1"
    )
    request_feed = Request(
        feed_url,
        headers={
            "Accept": "text/plain,*/*;q=0.9",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "User-Agent": "ResenhoBot/1.0",
            "Referer": "https://www.flashscore.com.br/",
            "x-fsign": FLASHSCORE_FEED_SIGNATURE,
        },
    )
    try:
        with urlopen(request_feed, timeout=20) as response:
            feed = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"Falha ao consultar o feed de classificação: {error}") from error

    return _converter_classificacao_grupos_feed(feed)


def _identificar_temporada_flashscore(html):
    """Lê o identificador da temporada nos feeds de jogos embutidos na página."""
    for feed in FLASHSCORE_INITIAL_FEEDS.finditer(html):
        nome_feed, dados_feed = feed.groups()
        if nome_feed not in {"summary-results", "summary-fixtures"}:
            continue
        for registro in dados_feed.split("~"):
            identificador = _campos_feed(registro).get("ZE")
            if identificador:
                return identificador
    raise RuntimeError("Não foi possível identificar a temporada atual do torneio.")


def _converter_classificacao_grupos_feed(feed):
    """Converte os registros codificados de classificação para linhas simples."""
    linhas = []
    grupo_atual = ""
    for registro in feed.split("~"):
        campos = _campos_feed(registro)
        grupo = campos.get("TE", "").strip()
        if grupo.casefold().startswith("grupo "):
            grupo_atual = grupo

        posicao = campos.get("TR", "").strip()
        time = campos.get("TN", "").strip()
        if not (grupo_atual and posicao.isdigit() and time):
            continue

        linhas.append({
            "grupo": grupo_atual,
            "posicao": posicao,
            "time": time,
            "jogos": campos.get("TM", "0").strip(),
            "vitorias": campos.get("TW", "0").strip(),
            "empates": campos.get("TDR", "0").strip(),
            "derrotas": campos.get("TL", "0").strip(),
            "gols": campos.get("TG", "0:0").strip(),
            "saldo": campos.get("TPF", "0").strip(),
            "pontos": campos.get("TP", "0").strip(),
        })

    return linhas

# Alimenta o JSON que o atualizador consome para comandos e alertas automáticos.
def obter_jogos(times_filtro=None):
    """Busca os feeds configurados, deduplica partidas e aplica o filtro de clubes."""
    if times_filtro is None:
        times_filtro = list(dict.fromkeys(SOUTH_AMERICAN_TEAMS + EUROPEAN_TEAMS))

    if not times_filtro:
        print("[FLASHSCORE] No teams configured; no matches will be collected.")
        return []

    eventos_por_id = {}
    falhas = 0
    descartados_por_filtro = 0
    for url, nome_liga in FLASHSCORE_COMPETITIONS:
        eventos, erro = _buscar_eventos(url, nome_liga)
        if erro:
            falhas += 1
            continue

        for evento in eventos:
            identificador = evento.get("id") or (
                evento.get("data"), evento.get("hora"),
                evento.get("mandante"), evento.get("visitante"), nome_liga,
            )
            anterior = eventos_por_id.get(identificador)
            if anterior and _prioridade_status(anterior) > _prioridade_status(evento):
                continue
            if not jogo_tem_time_filtrado(evento, times_filtro):
                descartados_por_filtro += 1
                continue
            eventos_por_id[identificador] = evento

    # Perfis por equipe cobrem clubes sem uma competição dedicada na coleta geral.
    perfis = [
        (nome, EUROPEAN_TEAM_URLS[nome])
        for nome in ("Porto", "Benfica", "Sporting CP")
        if nome in EUROPEAN_TEAM_URLS
    ]
    perfis.append((BRAZIL_NATIONAL_TEAM, BRAZIL_NATIONAL_TEAM_URL))
    for nome_time, url in perfis:
        eventos, erro = _buscar_eventos(url, nome_time)
        if erro:
            continue
        for evento in eventos:
            identificador = evento.get("id") or (
                evento.get("data"), evento.get("hora"),
                evento.get("mandante"), evento.get("visitante"), evento.get("liga"),
            )
            anterior = eventos_por_id.get(identificador)
            if anterior and _prioridade_status(anterior) > _prioridade_status(evento):
                continue
            # O contexto do perfil nacional é próprio para permitir alertas independentes.
            if nome_time == BRAZIL_NATIONAL_TEAM:
                evento["liga"] = "selecao brasileira"
            else:
                evento["liga"] = "portugal"
            if jogo_tem_time_filtrado(evento, [nome_time]):
                eventos_por_id[identificador] = evento

    if falhas == len(FLASHSCORE_COMPETITIONS):
        raise RuntimeError("Could not read match feeds from any Flashscore competition.")

    lista_resultados = list(eventos_por_id.values())

    print(
        f"[FLASHSCORE] Unique events: {len(eventos_por_id)} | "
        f"Descartados pelo filtro de times: {descartados_por_filtro} | "
        f"Collected matches: {len(lista_resultados)} | "
        f"Consultas com falha: {falhas}."
    )
    return sorted(lista_resultados, key=lambda jogo: (jogo["data"], jogo["hora"]))

# Consulta uma competição e transforma os feeds encontrados em eventos normalizados.
def _buscar_eventos(url, contexto):
    url = urldefrag(url).url
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "ResenhoBot/1.0",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        print(f"[FLASHSCORE] Failed to fetch {contexto}: {error}")
        return [], True

    feeds_encontrados = 0
    eventos = []
    for feed in FLASHSCORE_INITIAL_FEEDS.finditer(html):
        nome_feed, dados_feed = feed.groups()
        if nome_feed not in {"summary-results", "summary-fixtures"}:
            continue
        feeds_encontrados += 1
        for registro in dados_feed.split("~AA÷")[1:]:
            campos = _campos_feed(registro)
            evento = _converter_evento_flashscore(campos, contexto)
            if evento:
                eventos.append(evento)

    if not feeds_encontrados:
        print(f"[FLASHSCORE] No match feeds found for {contexto}.")
        return [], True
    return eventos, False

# Separa os campos codificados de um registro do feed Flashscore.
def _campos_feed(registro):
    partes = registro.split("¬")
    campos = {"AA": partes[0].strip()}
    for parte in partes[1:]:
        chave, separador, valor = parte.partition("÷")
        if separador:
            campos[chave] = valor
    return campos

# Converte um registro do provedor para o formato de jogo salvo no JSON.
def _converter_evento_flashscore(campos, nome_liga):
    mandante = campos.get("CX", "").strip()
    visitante = campos.get("AF", "").strip()
    try:
        timestamp = int(campos.get("AD", ""))
    except (TypeError, ValueError):
        return None
    if not mandante or not visitante:
        return None

    inicio = datetime.fromtimestamp(timestamp, FUSO_BRASIL)
    codigo_status = campos.get("AB")
    tipo_status = {"2": "AO_VIVO", "3": "ENCERRADO"}.get(
        codigo_status, "FUTURO"
    )

    placar = "x"
    if tipo_status != "FUTURO":
        gols_mandante = campos.get("AG")
        gols_visitante = campos.get("AH")
        if gols_mandante is not None and gols_visitante is not None:
            placar = f"{gols_mandante} x {gols_visitante}"

    data = inicio.date().isoformat()
    hora = inicio.strftime("%H:%M")
    return {
        "id": campos.get("AA"),
        "mandante": mandante,
        "visitante": visitante,
        "placar": placar,
        "status": f"{inicio.strftime('%d/%m')} — {hora}",
        "tipo_status": tipo_status,
        "liga": nome_liga,
        "data": data,
        "hora": hora,
    }


# Consulta a partida pelo estádio, cidade, país e árbitro divulgado.
def obter_detalhes_partida_flashscore(identificador):
    if not identificador:
        return {}

    request = Request(
        f"https://www.flashscore.com/match/{identificador}/",
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "ResenhoBot/1.0",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            html_partida = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        print(
            f"[FLASHScore] Falha ao consultar os detalhes da partida "
            f"{identificador}: {type(error).__name__}: {error}"
        )
        return {}

    def valores_info(rotulo):
        bloco = re.search(
            r'<span\b[^>]*data-testid="wcl-overline-02"[^>]*>\s*'
            + re.escape(rotulo)
            + r'\s*</span>\s*</div>\s*<div\b[^>]*class="[^"]*wcl-infoValue[^"]*"[^>]*>(.*?)</div>',
            html_partida,
            re.IGNORECASE | re.DOTALL,
        )
        if not bloco:
            return []

        valores = re.findall(
            r'<span\b[^>]*data-testid="wcl-simple-text-01"[^>]*>(.*?)</span>',
            bloco.group(1),
            re.IGNORECASE | re.DOTALL,
        )
        return [
            re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", valor))).strip()
            for valor in valores
        ]

    valores_estadio = valores_info("Venue:") or valores_info("Stadium:")
    estadio = cidade = pais = ""
    if valores_estadio:
        estadio_partida, cidade_partida, pais_partida = _separar_local(
            valores_estadio[0]
        )
        estadio, cidade, pais = estadio_partida, cidade_partida, pais_partida

    # O perfil do mandante complementa somente os dados que a partida não informou.
    perfil_mandante = {}
    if not (estadio and cidade and pais):
        perfil_mandante = _obter_estadio_cidade_mandante(html_partida)
        estadio = estadio or perfil_mandante.get("estadio", "")
        cidade = cidade or perfil_mandante.get("cidade", "")
        pais = pais or perfil_mandante.get("pais", "")

    valores_arbitro = valores_info("Referee:")
    arbitro = " ".join(
        valor for valor in valores_arbitro if valor and valor not in {"-", "TBD"}
    )

    detalhes = {
        "estadio": estadio if estadio not in {"-", "TBD"} else "",
        "cidade": cidade if cidade not in {"-", "TBD"} else "",
        "pais": pais if pais not in {"-", "TBD"} else "",
    }
    if perfil_mandante:
        detalhes["perfil_mandante"] = perfil_mandante
    if arbitro:
        detalhes["arbitro"] = arbitro
    if not any(detalhes.values()):
        print(
            f"[FLASHSCORE] A página da partida {identificador} foi carregada, "
            "mas não foram encontrados estádio, cidade, país ou árbitro."
        )
    return detalhes

def _obter_estadio_cidade_mandante(html_partida):
    """Obtém estádio, cidade e país do perfil do mandante como fallback."""
    inicio_mandante = re.search(
        r'<div\b[^>]*class="[^"]*\bduelParticipant__home\b[^"]*"[^>]*>',
        html_partida,
        re.IGNORECASE,
    )
    if not inicio_mandante:
        return {}

    html_apos_mandante = html_partida[inicio_mandante.end():]
    inicio_visitante = re.search(
        r'<div\b[^>]*class="[^"]*\bduelParticipant__away\b[^"]*"[^>]*>',
        html_apos_mandante,
        re.IGNORECASE,
    )
    fim_bloco = (
        inicio_mandante.end() + inicio_visitante.start()
        if inicio_visitante
        else inicio_mandante.end() + 6000
    )
    bloco_mandante = html_partida[inicio_mandante.start():fim_bloco]
    perfil = re.search(r'href=["\'](/team/[^"\']+)["\']', bloco_mandante, re.IGNORECASE)
    if not perfil:
        return {}

    caminho_perfil = perfil.group(1)
    agora = datetime.now()
    cache = _CACHE_ESTADIO_TIMES.get(caminho_perfil)
    if cache and agora - cache[0] < _CACHE_ESTADIO_TIMES_TTL:
        return cache[1]

    request = Request(
        f"https://www.flashscore.com{caminho_perfil}",
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "ResenhoBot/1.0",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            html_time = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        print(
            f"[FLASHSCORE] Falha ao consultar o perfil do mandante "
            f"{caminho_perfil}: {type(error).__name__}: {error}"
        )
        return {}

    def obter_campo_perfil(rotulo):
        campo = re.search(
            r'<span\b[^>]*class="[^"]*\bheading__info--key\b[^"]*"[^>]*>\s*'
            + re.escape(rotulo)
            + r'\s*</span>(.*?)</div>',
            html_time,
            re.IGNORECASE | re.DOTALL,
        )
        if not campo:
            return ""
        texto = html_lib.unescape(re.sub(r"<[^>]+>", " ", campo.group(1)))
        return re.sub(r"\s+", " ", texto).strip()

    valor_estadio = obter_campo_perfil("Stadium:") or obter_campo_perfil("Venue:")
    estadio, cidade, pais = _separar_local(valor_estadio)
    cidade = cidade or obter_campo_perfil("City:")
    pais = pais or obter_campo_perfil("Country:")
    resultado = {
        "estadio": estadio,
        "cidade": cidade,
        "pais": pais,
    }
    if any(resultado[campo] for campo in ("estadio", "cidade", "pais")):
        resultado["url"] = f"https://www.flashscore.com{caminho_perfil}"
        _CACHE_ESTADIO_TIMES[caminho_perfil] = (agora, resultado)
    else:
        return {}
    return resultado


def _separar_local(texto):
    """Separa local no formato 'Nome do estádio (Cidade, País)'."""
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()
    if not texto or texto in {"-", "TBD"}:
        return "", "", ""

    local = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", texto)
    if not local:
        return texto, "", ""

    nome_estadio = local.group(1).strip()
    partes_local = [parte.strip() for parte in local.group(2).split(",") if parte.strip()]
    cidade = partes_local[0] if partes_local else ""
    pais = ", ".join(partes_local[1:]) if len(partes_local) > 1 else ""
    return nome_estadio, cidade, pais


# Prefere o status mais recente quando o mesmo evento aparece em mais de um feed.
def _prioridade_status(jogo):
    return {"FUTURO": 0, "AO_VIVO": 1, "ENCERRADO": 2}.get(
        jogo.get("tipo_status"), 0
    )

# Reutiliza os aliases configurados para comparar mandante e visitante.
def jogo_tem_time_filtrado(jogo_info, times_filtro):
    """Retorna se algum dos times da partida corresponde ao filtro configurado."""
    return any(time_corresponde(nome, time) for nome in (jogo_info.get("mandante", ""), jogo_info.get("visitante", "")) for time in times_filtro)

# Classifica a partida pelo horário local e estima a duração quando o feed não informa status.
def definir_status_por_horario(data_str, hora_str, placar_str="x"):
    agora = datetime.now(FUSO_BRASIL)
    try:
        data_inicio = datetime.strptime(
            f"{data_str} {hora_str}", "%Y-%m-%d %H:%M"
        )
        data_inicio = FUSO_BRASIL.localize(data_inicio)
        data_fim = data_inicio + timedelta(hours=2, minutes=15)

        if agora < data_inicio:
            return "FUTURO", hora_str
        if data_inicio <= agora <= data_fim:
            minutos = int((agora - data_inicio).total_seconds() / 60)
            return "AO_VIVO", f"{minutos}'"
        return "ENCERRADO", "Encerrado"
    except (TypeError, ValueError) as error:
        print(f"Erro ao converter data: {error}")
        return ("ENCERRADO", "Encerrado") if placar_str != "x" else ("FUTURO", hora_str)

# Padroniza datas do feed em ISO, usado para ordenar e identificar jogos por dia.
def converter_data_para_iso(data_str, placar_str="x"):
    """Converte datas DD/MM ou DD/MM/YYYY para YYYY-MM-DD."""
    agora = datetime.now(FUSO_BRASIL)
    try:
        if not data_str:
            return None

        data_str = data_str.strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(data_str, formato).date().isoformat()
            except ValueError:
                continue

        if "Hoje" in data_str:
            return agora.strftime("%Y-%m-%d")
        if "Ontem" in data_str:
            return (agora - timedelta(days=1)).strftime("%Y-%m-%d")

        dia, mes = map(int, data_str[:5].split("/"))
        ano = agora.year
        if mes < agora.month and placar_str.strip().lower() == "x":
            ano += 1
        return f"{ano:04d}-{mes:02d}-{dia:02d}"
    except (TypeError, ValueError) as error:
        print(f"Erro ao converter data '{data_str}' para ISO: {error}")
        return None
