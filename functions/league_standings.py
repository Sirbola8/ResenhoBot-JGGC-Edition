"""Consulta e interpreta as tabelas das ligas no Flashscore."""

import asyncio
from html.parser import HTMLParser
import re
import time
import unicodedata

import aiohttp


LIGAS_CLASSIFICACAO = {
    'brasileirao': {
        'nome': 'Brasileirão Série A',
        'url': 'https://www.flashscore.com.br/futebol/brasil/brasileirao-serie-a/classificacao/hdLUdQGi/classificacoes/geral/',
        'aliases': (
            'brasileirao', 'brasileirão', 'brasileirão série a',
            'brasileirão a', 'serie a brasil', 'série a brasileira',
            'série a do brasileirão', 'campeonato brasileiro',
            'liga brasileira', 'brasil',
        ),
    },
    'premier-league': {
        'nome': 'Premier League',
        'url': 'https://www.flashscore.com/football/england/premier-league/standings/CfoA8Dmm/live-standings/',
        'aliases': (
            'premier league', 'premier', 'pl', 'epl', 'inglêsão',
            'inglesão', 'inglês', 'liga inglesa', 'liga da inglaterra',
            'campeonato inglês', 'futebol inglês', 'english premier league',
            'england', 'inglaterra',
        ),
    },
    'laliga': {
        'nome': 'LaLiga',
        'url': 'https://www.flashscore.com/football/spain/laliga/standings/dWdJXP6U/live-standings/',
        'aliases': (
            'laliga', 'la liga', 'liga espanhola', 'liga da espanha',
            'campeonato espanhol', 'espanholão', 'espanhol',
            'la liga ea sports', 'espanha', 'spain',
        ),
    },
    'serie-a': {
        'nome': 'Serie A',
        'url': 'https://www.flashscore.com/football/italy/serie-a/standings/CfujcOgK/standings/overall/',
        'aliases': (
            'serie a', 'serie a italiana', 'serie a italia', 'italianão',
            'italiano', 'liga italiana', 'campeonato italiano', 'calcio',
            'italia', 'italy',
        ),
    },
    'bundesliga': {
        'nome': 'Bundesliga',
        'url': 'https://www.flashscore.com/football/germany/bundesliga/standings/jg0MwVuC/live-standings/',
        'aliases': (
            'bundesliga', 'bundes', 'buli', 'liga alemã', 'liga da alemanha',
            'campeonato alemão', 'alemão', 'alemã', 'alemanha', 'germany',
        ),
    },
    'ligue-1': {
        'nome': 'Ligue 1',
        'url': 'https://www.flashscore.com/football/france/ligue-1/standings/CQF28KxR/standings/overall/',
        'aliases': (
            'ligue 1', 'ligue1', 'l1', 'liga francesa', 'liga da frança',
            'liga da franca', 'campeonato francês', 'francesão', 'francês',
            'frances', 'frança', 'franca', 'france',
        ),
    },
}


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto or '').casefold())
    texto = ''.join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return ' '.join(re.findall(r'[a-z0-9]+', texto))


_LIGA_POR_ALIAS = {
    _normalizar(alias): chave
    for chave, liga in LIGAS_CLASSIFICACAO.items()
    for alias in (chave, liga['nome'], *liga['aliases'])
}


def localizar_liga(texto):
    """Retorna a chave da liga a partir do nome ou de um apelido."""
    return _LIGA_POR_ALIAS.get(_normalizar(texto))


class _ParserTabelaFlashscore(HTMLParser):
    """Extrai posição, clube e os sete valores de cada linha da tabela."""

    _CAMPOS = {
        'tableCellRank': 'posicao',
        'tableCellParticipant__name': 'time',
        'table__cell--value': 'estatistica',
    }
    _TAGS_SEM_CONTEUDO = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linhas = []
        self._linha = None
        self._captura = None
        self._profundidade_linha = 0

    def handle_starttag(self, tag, attrs):
        classes = set(dict(attrs).get('class', '').split())
        if 'ui-table__row' in classes:
            self._linha = {'posicao': '', 'time': '', 'estatisticas': []}
            self._profundidade_linha = 1
            return
        if self._linha is None:
            return

        if tag not in self._TAGS_SEM_CONTEUDO:
            self._profundidade_linha += 1
        if self._captura:
            if tag not in self._TAGS_SEM_CONTEUDO:
                self._captura['profundidade'] += 1
            return

        for classe, campo in self._CAMPOS.items():
            if classe in classes:
                self._captura = {
                    'tag': tag,
                    'campo': campo,
                    'texto': [],
                    'profundidade': 1,
                }
                return

    def handle_endtag(self, tag):
        if self._captura:
            if tag not in self._TAGS_SEM_CONTEUDO:
                self._captura['profundidade'] -= 1
            if self._captura['profundidade'] <= 0:
                captura = self._captura
                texto = ' '.join(''.join(captura['texto']).split())
                if captura['campo'] == 'estatistica':
                    self._linha['estatisticas'].append(texto)
                else:
                    self._linha[captura['campo']] = texto
                self._captura = None

        if self._linha is not None and tag not in self._TAGS_SEM_CONTEUDO:
            self._profundidade_linha -= 1
            if self._profundidade_linha <= 0:
                self._salvar_linha()

    def handle_data(self, data):
        if self._captura:
            self._captura['texto'].append(data)

    def _salvar_linha(self):
        linha = self._linha
        self._linha = None
        self._profundidade_linha = 0
        try:
            posicao = int(re.search(r'\d+', linha['posicao']).group())
        except (AttributeError, TypeError, ValueError):
            return

        valores = linha['estatisticas']
        if len(valores) < 7:
            return
        self.linhas.append({
            'posicao': posicao,
            'time': linha['time'],
            'jogos': valores[0],
            'vitorias': valores[1],
            'empates': valores[2],
            'derrotas': valores[3],
            'gols': valores[4],
            'saldo': valores[5],
            'pontos': valores[6],
        })


_CACHE_CLASSIFICACOES = {}
_CACHE_TTL_SEGUNDOS = 90


async def obter_classificacao_liga(chave_liga):
    """Busca a classificação geral no Flashscore e reutiliza cache por 90 segundos."""
    if chave_liga not in LIGAS_CLASSIFICACAO:
        raise ValueError('Liga não reconhecida.')

    agora = time.monotonic()
    cache = _CACHE_CLASSIFICACOES.get(chave_liga)
    if cache and agora - cache['consultado'] < _CACHE_TTL_SEGUNDOS:
        return cache['linhas']

    liga = LIGAS_CLASSIFICACAO[chave_liga]
    cabecalhos = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    }
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=cabecalhos) as sessao:
            async with sessao.get(liga['url']) as resposta:
                if resposta.status != 200:
                    raise RuntimeError(f'Flashscore respondeu com HTTP {resposta.status}.')
                html = await resposta.text()
    except asyncio.TimeoutError as erro:
        raise RuntimeError('A consulta ao Flashscore demorou demais.') from erro
    except aiohttp.ClientError as erro:
        raise RuntimeError('Não foi possível acessar o Flashscore agora.') from erro

    parser = _ParserTabelaFlashscore()
    parser.feed(html)
    if not parser.linhas:
        raise RuntimeError('Não encontrei a tabela nessa página do Flashscore.')

    parser.linhas.sort(key=lambda linha: linha['posicao'])
    _CACHE_CLASSIFICACOES[chave_liga] = {
        'consultado': time.monotonic(),
        'linhas': parser.linhas,
    }
    return parser.linhas
