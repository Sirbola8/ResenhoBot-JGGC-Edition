# Ponto de entrada do ResenhoBot: reúne integrações, comandos e monitoramento automático de partidas.
import discord
from discord.ext import commands, tasks
import os
import re
import unicodedata

from dotenv import load_dotenv

load_dotenv()

from config import (
    BRAZIL_NATIONAL_TEAM,
    BRAZILIAN_TEAMS,
    CHECK_INTERVAL,
    EUROPEAN_TEAMS,
    TEAM_ALIASES,
)
from tasks.task_update_data import atualizar_arquivo
from tasks.obter_jogos_geral import (
    jogo_tem_time_filtrado,
    obter_classificacao_fase_grupos,
)
from functions.team_utils import time_corresponde
from functions.task_monitor_resenha import verificar_resenha
from functions.task_monitor_european import verificar_partidas_europeias
from functions.task_european_ucl import obter_proximo_jogo_european_teams
from functions.task_brazilian import obter_proximo_jogo_brasileirao
from functions.task_match_info import (
    obter_detalhes_dos_jogos,
    adicionar_campos_local_arbitragem,
    limpar_cache_consultas,
)
import json
import asyncio
import datetime
import pytz
from config import EUROPEAN_LEAGUES, SOUTH_AMERICAN_LEAGUES

# ============================================================
# CONFIGURAÇÕES
# ============================================================
# Credenciais e parâmetros de ambiente usados para autenticar o bot e direcionar os alertas.
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN", "")
ALERT_CHANNEL_ID   = int(os.getenv("ALERT_CHANNEL_ID", "1489395180158062622"))
FOOTBALL_API_KEY   = os.getenv("FOOTBALL_API_KEY", "")
 

# INTENTS E CLIENTE: habilita a leitura do conteúdo para reconhecer comandos iniciados por !.
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)
# Os comandos consultam este JSON; o fuso define qual data conta como "hoje" para os jogos.
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'dados_jogos.json')
GUILD_SETTINGS_PATH = os.path.join(
    os.path.dirname(__file__), 'data', 'monitoramento_servidores.json'
)
FUSO_BRASIL = pytz.timezone('America/Sao_Paulo')
_aviso_selecao_verificado_nesta_execucao = False
AVISO_SELECAO_BRASILEIRA = (
    'data fifa ta chegando cambada de chupa engole, preparem-se pra sofrer '
    'com a seleção bostileira mais uma vez kkkkk:shit::flag_br:'
)


def _carregar_configuracoes_servidores():
    try:
        with open(GUILD_SETTINGS_PATH, 'r', encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
        return dados if isinstance(dados, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _salvar_configuracoes_servidores():
    temporario = f'{GUILD_SETTINGS_PATH}.tmp'
    with open(temporario, 'w', encoding='utf-8') as arquivo:
        json.dump(guild_settings, arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, GUILD_SETTINGS_PATH)


guild_settings = _carregar_configuracoes_servidores()
_setup_lock = asyncio.Lock()
_prompted_guilds = set()
_pending_team_confirmations = set()
BRAZILIAN_TEAM_SET = set(BRAZILIAN_TEAMS)
# Catálogo completo usado nas consultas manuais que não dependem do filtro de cada servidor.
ELIGIBLE_TEAMS = BRAZILIAN_TEAMS + EUROPEAN_TEAMS


def _normalizar_entrada(texto):
    texto = unicodedata.normalize('NFKD', str(texto or '').casefold())
    sem_acentos = ''.join(
        caractere for caractere in texto
        if not unicodedata.combining(caractere)
    )
    return ' '.join(re.findall(r'[a-z0-9]+', sem_acentos))


def _mapa_aliases_times():
    mapa = {}
    for time in ELIGIBLE_TEAMS:
        for alias in TEAM_ALIASES.get(time, (time,)):
            mapa.setdefault(_normalizar_entrada(alias), time)
        mapa.setdefault(_normalizar_entrada(time), time)
    return mapa


TEAM_BY_ALIAS = _mapa_aliases_times()

TEAM_COUNTRY_FLAGS = {
    **{time: '🇧🇷' for time in BRAZILIAN_TEAMS},
    'AC Milan': '🇮🇹',
    'Inter Milan': '🇮🇹',
    'Juventus': '🇮🇹',
    'Paris Saint-Germain': '🇫🇷',
    'Bayern Munich': '🇩🇪',
    'Borussia Dortmund': '🇩🇪',
    'Atletico Madrid': '🇪🇸',
    'Barcelona': '🇪🇸',
    'Real Madrid': '🇪🇸',
    'Chelsea': '🇬🇧',
    'Manchester United': '🇬🇧',
    'Manchester City': '🇬🇧',
    'Tottenham': '🇬🇧',
    'Liverpool': '🇬🇧',
    'Arsenal': '🇬🇧',
    'River Plate': '🇦🇷',
    'Boca Juniors': '🇦🇷',
    'Estudiantes': '🇦🇷',
    'Lanús': '🇦🇷',
    'Rosario Central': '🇦🇷',
    'Racing Club': '🇦🇷',
    'Vélez Sarsfield': '🇦🇷',
    'Peñarol': '🇺🇾',
    'Nacional': '🇺🇾',
    'Coquimbo Unido': '🇨🇱',
    'Colo-Colo': '🇨🇱',
    'Libertad': '🇵🇾',
    'Cerro Porteño': '🇵🇾',
    'LDU Quito': '🇪🇨',
    'Independiente del Valle': '🇪🇨',
    'Barcelona SC': '🇪🇨',
    'Ind. Medellín': '🇨🇴',
    'Atlético Nacional': '🇨🇴',
    'Millonarios': '🇨🇴',
    'Tolima': '🇨🇴',
    'Universitario': '🇵🇪',
    'Alianza Lima': '🇵🇪',
    'Always Ready': '🇧🇴',
    'Bolívar': '🇧🇴',
    'Carabobo': '🇻🇪',
    'Universidad Central': '🇻🇪',
    'Argentina': '🇦🇷',
    'Brasil': '🇧🇷',
    'Bolívia': '🇧🇴',
    'Chile': '🇨🇱',
    'Colômbia': '🇨🇴',
    'Equador': '🇪🇨',
    'Paraguai': '🇵🇾',
    'Peru': '🇵🇪',
    'Uruguai': '🇺🇾',
    'Venezuela': '🇻🇪',
    'México': '🇲🇽',
    'Estados Unidos': '🇺🇸',
    'EUA': '🇺🇸',
    'Canadá': '🇨🇦',
    'Japão': '🇯🇵',
    'Coreia do Sul': '🇰🇷',
    'Austrália': '🇦🇺',
    'Irã': '🇮🇷',
    'Arábia Saudita': '🇸🇦',
    'Catar': '🇶🇦',
    'Uzbequistão': '🇺🇿',
    'Jordânia': '🇯🇴',
    'Espanha': '🇪🇸',
    'França': '🇫🇷',
    'Alemanha': '🇩🇪',
    'Portugal': '🇵🇹',
    'Países Baixos': '🇳🇱',
    'Bélgica': '🇧🇪',
    'Croácia': '🇭🇷',
    'Suíça': '🇨🇭',
    'Áustria': '🇦🇹',
    'Noruega': '🇳🇴',
    'Inglaterra': '🇬🇧',
    'Reino Unido': '🇬🇧',
    'Escócia': '🇬🇧',
    'Irlanda': '🇮🇪',
    'Suécia': '🇸🇪',
    'Dinamarca': '🇩🇰',
    'Polônia': '🇵🇱',
    'Sérvia': '🇷🇸',
    'Eslovênia': '🇸🇮',
    'Eslováquia': '🇸🇰',
    'Grécia': '🇬🇷',
    'Turquia': '🇹🇷',
    'Hungria': '🇭🇺',
    'Romênia': '🇷🇴',
    'República Tcheca': '🇨🇿',
    'Bósnia e Herzegovina': '🇧🇦',
    'Holanda': '🇳🇱',
    'Marrocos': '🇲🇦',
    'Senegal': '🇸🇳',
    'Costa do Marfim': '🇨🇮',
    'Egito': '🇪🇬',
    'África do Sul': '🇿🇦',
    'Curaçao': '🇨🇼',
    'Haiti': '🇭🇹',
    'Tunísia': '🇹🇳',
    'Nova Zelândia': '🇳🇿',
    'Cabo Verde': '🇨🇻',
    'Gana': '🇬🇭',
    'Iraque': '🇮🇶',
    'Panamá': '🇵🇦',
    'R. D. Congo': '🇨🇩',
    'Congo DR': '🇨🇩',
    'República Democrática do Congo': '🇨🇩',
    'Cusco': '🇵🇪',
    'Ind. Rivadavia': '🇦🇷',
    'La Guaira': '🇻🇪',
    'Universidad Católica': '🇪🇨',
    'Platense': '🇦🇷',
    'Santa Fe': '🇨🇴',
    'Ind. del Valle': '🇪🇨',
    'Macara': '🇪🇨',
    'Tigre': '🇦🇷',
    'América de Cali': '🇨🇴',
    'Alianza Atl.': '🇵🇪',
    'Cienciano': '🇵🇪',
    'Juventud': '🇺🇾',
    'Puerto Cabello': '🇻🇪',
    "O'Higgins": '🇨🇱',
    'Boston River': '🇺🇾',
    'Recoleta': '🇵🇾',
    'San Lorenzo': '🇦🇷',
    'Dep. Cuenca': '🇪🇨',
    'Caracas': '🇻🇪',
    'Independiente': '🇦🇷',
    'Montevideo City': '🇺🇾',
    'Dep. Riestra': '🇦🇷',
    'Palestino': '🇨🇱',
    'Olimpia Asuncion': '🇵🇾',
    'Audax Italiano': '🇨🇱',
    'Barracas Central': '🇦🇷',
    'Blooming': '🇧🇴',
    'Red Bull Bragantino': '🇧🇷',
}
COUNTRY_FLAGS_BY_LEAGUE = {
    'brasileirao serie a': '🇧🇷',
    'italia': '🇮🇹',
    'inglaterra': '🇬🇧',
    'franca': '🇫🇷',
    'alemanha': '🇩🇪',
    'espanha': '🇪🇸',
}
COUNTRY_FLAGS_BY_CODE = {
    'bra': '🇧🇷', 'arg': '🇦🇷', 'uru': '🇺🇾', 'chi': '🇨🇱',
    'par': '🇵🇾', 'ecu': '🇪🇨', 'col': '🇨🇴', 'per': '🇵🇪',
    'bol': '🇧🇴', 'ven': '🇻🇪', 'mex': '🇲🇽', 'usa': '🇺🇸',
    'can': '🇨🇦', 'jpn': '🇯🇵', 'kor': '🇰🇷', 'aus': '🇦🇺',
    'irn': '🇮🇷', 'ksa': '🇸🇦', 'qat': '🇶🇦', 'uzb': '🇺🇿',
    'jor': '🇯🇴', 'esp': '🇪🇸', 'fra': '🇫🇷', 'ger': '🇩🇪',
    'por': '🇵🇹', 'ned': '🇳🇱', 'bel': '🇧🇪', 'cro': '🇭🇷',
    'sui': '🇨🇭', 'aut': '🇦🇹', 'nor': '🇳🇴', 'eng': '🇬🇧',
    'sco': '🇬🇧', 'irl': '🇮🇪', 'swe': '🇸🇪', 'den': '🇩🇰',
    'pol': '🇵🇱', 'srb': '🇷🇸', 'slo': '🇸🇮', 'svk': '🇸🇰',
    'gre': '🇬🇷', 'tur': '🇹🇷', 'hun': '🇭🇺', 'rou': '🇷🇴',
    'cze': '🇨🇿', 'bih': '🇧🇦', 'mar': '🇲🇦', 'sen': '🇸🇳',
    'civ': '🇨🇮', 'egy': '🇪🇬', 'rsa': '🇿🇦', 'gha': '🇬🇭',
    'alg': '🇩🇿', 'nz': '🇳🇿', 'nzl': '🇳🇿', 'cpv': '🇨🇻',
    'hai': '🇭🇹', 'tun': '🇹🇳', 'irq': '🇮🇶', 'pan': '🇵🇦',
    'cu': '🇨🇼', 'cod': '🇨🇩', 'con': '🇨🇩',
}
TEAM_COUNTRY_FLAGS_NORMALIZED = {
    _normalizar_entrada(time): bandeira
    for time, bandeira in TEAM_COUNTRY_FLAGS.items()
}
CONTINENTAL_CLUB_FLAGS = {
    'Barcelona': '🇪🇨',
}
CONTINENTAL_CLUB_FLAGS_NORMALIZED = {
    _normalizar_entrada(time): bandeira
    for time, bandeira in CONTINENTAL_CLUB_FLAGS.items()
}

GROUP_STAGE_ALIASES = {
    'libertadores': ('libertadores', 'copa libertadores', 'liberta'),
    'sulamericana': (
        'sulamericana', 'sul-americana', 'sul americana',
        'copa sulamericana', 'copa sul-americana', 'copa sul americana',
        'sudamericana', 'sula',
    ),
    'copa do mundo': (
        'copa do mundo', 'copadomundo', 'mundo', 'mundial', 'world cup',
        'campeonato do mundo',
    ),
}
GROUP_STAGE_BY_COMPACT_ALIAS = {
    re.sub(r'[^a-z0-9]', '', _normalizar_entrada(alias)): torneio
    for torneio, aliases in GROUP_STAGE_ALIASES.items()
    for alias in aliases
}


def _bandeira_do_time(nome, liga=None):
    # O feed de partidas inclui o país entre parênteses ("Flamengo (Bra)").
    texto = str(nome or '').strip()
    sufixo_pais = re.search(r'\s*\(([^()]*)\)\s*$', texto)
    bandeira_sufixo = ''
    if sufixo_pais:
        bandeira_sufixo = COUNTRY_FLAGS_BY_CODE.get(
            _normalizar_entrada(sufixo_pais.group(1)), ''
        )
        texto = texto[:sufixo_pais.start()].strip()

    nome = texto
    normalizado = _normalizar_entrada(nome)
    liga_normalizada = str(liga or '').casefold().strip()
    if liga_normalizada in {'libertadores', 'sulamericana'}:
        bandeira_competicao = CONTINENTAL_CLUB_FLAGS_NORMALIZED.get(normalizado)
        if bandeira_competicao:
            return bandeira_competicao
    for time, bandeira in TEAM_COUNTRY_FLAGS.items():
        if time_corresponde(nome, time):
            return bandeira
    bandeira = TEAM_COUNTRY_FLAGS_NORMALIZED.get(normalizado, '')
    if bandeira:
        return bandeira
    return bandeira_sufixo or COUNTRY_FLAGS_BY_LEAGUE.get(
        liga_normalizada, ''
    )


def _nome_com_bandeira(nome, liga=None):
    bandeira = _bandeira_do_time(nome, liga)
    return f'{bandeira} {nome}' if bandeira else str(nome)


def _compactar_comando(texto):
    return re.sub(r'[^a-z0-9]', '', _normalizar_entrada(texto))


def _extrair_comando_fase_grupos(conteudo):
    if not str(conteudo or '').strip().startswith('!'):
        return None
    comando = _compactar_comando(str(conteudo).strip()[1:])
    for prefixo in ('fasegrupos', 'fg'):
        if comando.startswith(prefixo):
            torneio = GROUP_STAGE_BY_COMPACT_ALIAS.get(comando[len(prefixo):])
            return torneio or ''
    return None


def _resolver_comando_jogos_time(conteudo):
    # Resolve !jogos<apelido> antes do parser do discord.py, aceitando nomes com espaços e acentos.
    if not str(conteudo or '').strip().startswith('!'):
        return None
    comando = _compactar_comando(str(conteudo).strip()[1:])
    if not comando.startswith('jogos'):
        return None
    apelido = comando[len('jogos'):]
    if not apelido:
        return None
    for time in ELIGIBLE_TEAMS:
        aliases = TEAM_ALIASES.get(time, (time,))
        if any(_compactar_comando(alias) == apelido for alias in aliases + (time,)):
            return time
    return None


def _resolver_time(texto):
    return TEAM_BY_ALIAS.get(_normalizar_entrada(texto))


def _times_do_servidor(guild_id, regiao=None):
    configuracao = guild_settings.get(str(guild_id), {})
    times = configuracao.get('teams', [])
    if regiao == 'brasil':
        return [time for time in times if time in BRAZILIAN_TEAM_SET]
    if regiao == 'europa':
        return [time for time in times if time in EUROPEAN_TEAMS]
    return list(times)


def _canais_configurados(configuracao):
    """Aceita tanto um canal quanto a lista de canais salva nas configurações."""
    ids = configuracao.get('channel_id') or []
    if not isinstance(ids, (list, tuple, set)):
        ids = [ids]
    canais = []
    for canal_id in ids:
        try:
            canal_id = int(canal_id)
        except (TypeError, ValueError):
            continue
        if canal_id and canal_id not in canais:
            canais.append(canal_id)
    return canais


def _jogos_selecao_registrados():
    """Retorna os registros envolvendo a Seleção, sem depender do nome da competição."""
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as arquivo:
            jogos = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(jogos, list):
        return []
    registrados = [
        jogo for jogo in jogos
        if isinstance(jogo, dict) and any(
            time_corresponde(jogo.get(lado, ''), BRAZIL_NATIONAL_TEAM)
            for lado in ('mandante', 'visitante')
        )
    ]
    return sorted(
        registrados,
        key=lambda jogo: (str(jogo.get('data', '')), str(jogo.get('hora', ''))),
    )


def _inicio_jogo_selecao(jogo):
    try:
        inicio = datetime.datetime.strptime(
            f"{jogo.get('data', '')} {jogo.get('hora', '')}", '%Y-%m-%d %H:%M'
        )
    except (TypeError, ValueError):
        return None
    return FUSO_BRASIL.localize(inicio)


async def _exigir_configuracao_servidor(ctx):
    if ctx.guild is None:
        await ctx.send(f'{ctx.author.mention}, esse comando é coisa de servidor. Aqui no privado não tem arquibancada, pô.')
        return False
    if not guild_settings.get(str(ctx.guild.id), {}).get('initialized'):
        await ctx.send(f'{ctx.author.mention}, escolhe primeiro um time brasileiro na pergunta inicial; sem esse cadastro eu não sei quem você quer vigiar, criatura.')
        return False
    return True


def _canal_de_configuracao(guild, canal_preferido_id=None):
    membro_bot = guild.me
    if membro_bot is None:
        return None
    canais = []
    if canal_preferido_id:
        canal_preferido = guild.get_channel(canal_preferido_id)
        if canal_preferido:
            canais.append(canal_preferido)
    if guild.system_channel and guild.system_channel not in canais:
        canais.append(guild.system_channel)
    canais.extend(canal for canal in guild.text_channels if canal not in canais)
    for canal in canais:
        permissoes = canal.permissions_for(membro_bot)
        if permissoes.view_channel and permissoes.send_messages:
            return canal
    return None


async def iniciar_configuracao_servidor(guild):
    async with _setup_lock:
        chave = str(guild.id)
        configuracao = guild_settings.get(chave)
        if isinstance(configuracao, dict) and configuracao.get('initialized'):
            return
        if not isinstance(configuracao, dict):
            configuracao = {
                'teams': [],
                'channel_id': None,
                'setup_channel_id': None,
                'initialized': False,
                'prompted': False,
            }
            guild_settings[chave] = configuracao
            _salvar_configuracoes_servidores()
        else:
            configuracao.setdefault('teams', [])
            configuracao.setdefault('channel_id', None)
            configuracao.setdefault('setup_channel_id', None)
            configuracao.setdefault('initialized', False)
            configuracao.setdefault('prompted', False)

        if guild.id in _prompted_guilds:
            return

        canal = _canal_de_configuracao(
            guild, configuracao.get('setup_channel_id')
        )
        if canal is None:
            print(f'[CONFIG] Sem canal acessível para iniciar {guild.name} ({guild.id}).')
            return

        nomes_times = ', '.join(BRAZILIAN_TEAMS)
        try:
            await canal.send(
                f'⚽ **O ResenhoBot chegou, segura essa resenha!**\n'
                f'Qual dos 12 grandes do Brasil você quer monitorar primeiro, fiscal de sofá?\n'
                f'{nomes_times}\n\n'
                f'Responde com o nome do time aqui. Depois, usa `!<nome do time>` '
                f'pra adicionar ou remover qualquer um dos 27 clubes. Bora, não me deixa falando sozinho.'
            )
        except discord.HTTPException as error:
            print(f'[CONFIG] Não foi possível perguntar em {guild.name}: {error}')
            return

        configuracao['setup_channel_id'] = canal.id
        configuracao['channel_id'] = canal.id
        configuracao['prompted'] = True
        _salvar_configuracoes_servidores()
        _prompted_guilds.add(guild.id)


async def _confirmar_remocao(ctx, time):
    chave_pendente = (ctx.guild.id, ctx.channel.id, ctx.author.id)
    if chave_pendente in _pending_team_confirmations:
        await ctx.send(f'{ctx.author.mention}, responde a confirmação anterior primeiro, ô afobado.')
        return False

    _pending_team_confirmations.add(chave_pendente)
    try:
        await ctx.send(
            f'{ctx.author.mention}, **{time}** já tá no radar. Vai tirar o time da lista ou só veio apertar botão? '
            f'Responde **sim** ou **não** (também aceito: ss, s, yes, y, nn, n, ñ, no).'
        )
        prazo = asyncio.get_running_loop().time() + 60
        while True:
            restante = prazo - asyncio.get_running_loop().time()
            if restante <= 0:
                await ctx.send('Acabou o tempo, lenda. O monitoramento segue ativo porque você sumiu.')
                return False

            resposta = await bot.wait_for(
                'message',
                check=lambda mensagem: (
                    mensagem.guild is not None
                    and mensagem.guild.id == ctx.guild.id
                    and mensagem.channel.id == ctx.channel.id
                    and mensagem.author.id == ctx.author.id
                    and not mensagem.author.bot
                ),
                timeout=restante,
            )
            valor = _normalizar_entrada(resposta.content)
            if valor in {'sim', 'ss', 's', 'yes', 'y'}:
                return True
            if valor in {'nao', 'nn', 'n', 'no'}:
                await ctx.send('Fechou, o monitoramento continua ativo. Até que enfim uma decisão sensata.')
                return False
            await ctx.send('É **sim** ou **não**, meu consagrado. Não precisa inventar moda.')
    except asyncio.TimeoutError:
        await ctx.send('Acabou o tempo, lenda. O monitoramento segue ativo porque você sumiu.')
        return False
    finally:
        _pending_team_confirmations.discard(chave_pendente)


async def processar_comando_time(ctx, time):
    configuracao = guild_settings.get(str(ctx.guild.id))
    if not configuracao or not configuracao.get('initialized'):
        await ctx.send(f'{ctx.author.mention}, responde primeiro à pergunta inicial e escolhe um time brasileiro, ô perdido.')
        return

    times = configuracao.setdefault('teams', [])
    if time in times:
        if await _confirmar_remocao(ctx, time):
            # Revalida após a espera, pois outra pessoa pode ter alterado a seleção.
            if time in times:
                times.remove(time)
                _salvar_configuracoes_servidores()
                await ctx.send(f'Pronto, **{time}** saiu do radar deste servidor. Menos um motivo pra você perder o sono, {ctx.author.mention}.')
            else:
                await ctx.send(f'**{time}** já tinha saído da lista enquanto você filosofava, {ctx.author.mention}.')
        return

    times.append(time)
    _salvar_configuracoes_servidores()
    await ctx.send(f'**{time}** entrou no radar deste servidor. Boa, {ctx.author.mention}; agora pode fiscalizar mais um clube.')

# FUNÇÕES AUXILIARES: preparam os dados e as mensagens usados pelos comandos do bot.
# Links oficiais do Flashscore por competição; as mensagens usam este mapa para abrir a página da liga.
FLASHSCORE_LEAGUE_URLS = {
    'brasileirao serie a': 'https://www.flashscore.com/football/brazil/serie-a/#/hdLUdQGi/standings/overall/',
    'italia': 'https://www.flashscore.com/football/italy/serie-a/#/CfujcOgK/standings/overall/',
    'inglaterra': 'https://www.flashscore.com/football/england/premier-league/#/CfoA8Dmm/standings/overall/',
    'franca': 'https://www.flashscore.com/football/france/ligue-1/#/CQF28KxR/standings/overall/',
    'alemanha': 'https://www.flashscore.com/football/germany/bundesliga/#/jg0MwVuC/standings/overall/',
    'espanha': 'https://www.flashscore.com/football/spain/laliga/#/dWdJXP6U/standings/overall/',
    'champions league': 'https://www.flashscore.com/football/europe/champions-league/#/vT1iNRGq/standings/overall/',
    'europa league': 'https://www.flashscore.com/football/europe/europa-league/#/OjQOTQKa/standings/overall/',
    'conference league': 'https://www.flashscore.com/football/europe/conference-league/#/8WHkz50k/standings/overall/',
    'copa libertadores': 'https://www.flashscore.com/football/south-america/copa-libertadores/#/SlYIvtWi/draw/',
    'libertadores': 'https://www.flashscore.com/football/south-america/copa-libertadores/#/SlYIvtWi/draw/',
    'sulamericana': 'https://www.flashscore.com/football/south-america/copa-sudamericana/#/6m37slS7/draw/',
}
GROUP_STAGE_URLS = {
    'libertadores': 'https://www.flashscore.com.br/futebol/america-do-sul/copa-libertadores/classificacao/dQHOGxvo/classificacoes/geral/',
    'sulamericana': 'https://www.flashscore.com.br/futebol/america-do-sul/copa-sul-americana/classificacao/2e6joWSr/classificacoes/geral/',
    'copa do mundo': 'https://www.flashscore.com.br/futebol/mundo/campeonato-do-mundo/classificacao/SbLsX4y7/',
}
GROUP_STAGE_TITLES = {
    'libertadores': 'Copa Libertadores',
    'sulamericana': 'Copa Sul-Americana',
    'copa do mundo': 'Copa do Mundo',
}


# Normaliza o nome da competição e gera um link Markdown seguro para exibição no Discord.
def _link_liga_flashscore(nome_liga):
    nome = str(nome_liga or '').strip()
    url = FLASHSCORE_LEAGUE_URLS.get(nome.casefold())
    texto = discord.utils.escape_markdown(nome)
    return f'[{texto}]({url})' if url else texto


# Lê o JSON do dia, aplica filtros de liga e time e ordena as partidas por horário; sem dados válidos, retorna uma lista vazia.
def jogos_do_dia(ligas=None, times=None):
    hoje = datetime.datetime.now(FUSO_BRASIL).date().isoformat()
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as arquivo:
            jogos = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return []

    jogos_do_dia = [
        jogo for jogo in jogos
        if jogo.get('data') == hoje
        and (ligas is None or str(jogo.get('liga', '')).casefold().strip() in ligas)
        and (times is None or jogo_tem_time_filtrado(jogo, times))
    ]
    return sorted(jogos_do_dia, key=lambda jogo: jogo.get('hora', '23:59'))


# Lê os próximos jogos das competições indicadas, mantendo o filtro dos clubes configurados.
def proximos_jogos(liga, times, depois_de=None):
    agora = datetime.datetime.now(FUSO_BRASIL)
    ligas = (
        {liga.casefold().strip()}
        if isinstance(liga, str)
        else {str(item).casefold().strip() for item in liga}
    )
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as arquivo:
            jogos = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return []

    partidas_da_competicao = []
    for jogo in jogos:
        if str(jogo.get('liga', '')).casefold().strip() not in ligas:
            continue
        if not jogo_tem_time_filtrado(jogo, times):
            continue

        try:
            inicio = datetime.datetime.strptime(
                f"{jogo['data']} {str(jogo['hora'])[:5]}",
                '%Y-%m-%d %H:%M',
            )
            inicio = FUSO_BRASIL.localize(inicio)
        except (KeyError, TypeError, ValueError):
            continue
        if depois_de is not None and inicio.date() <= depois_de:
            continue

        partidas_da_competicao.append((inicio, jogo))

    partidas_da_competicao.sort(key=lambda item: item[0])
    proximas_por_id = {}
    for time in times:
        partidas_do_time = [
            (inicio, jogo)
            for inicio, jogo in partidas_da_competicao
            if any(
                time_corresponde(str(jogo.get(nome, '')), time)
                for nome in ('mandante', 'visitante')
            )
        ]
        for inicio, jogo in partidas_do_time:
            status = str(jogo.get('tipo_status', '')).upper()
            if status == 'ENCERRADO':
                continue
            # Uma partida iniciada, mas ainda não encerrada, bloqueia a volta do mata-mata.
            if inicio < agora:
                break
            identificador = jogo.get('id') or (
                jogo.get('data'), jogo.get('hora'),
                jogo.get('mandante'), jogo.get('visitante'),
            )
            proximas_por_id[identificador] = jogo
            break

    return sorted(
        proximas_por_id.values(),
        key=lambda jogo: (jogo.get('data', ''), jogo.get('hora', '23:59')),
    )


def proximos_jogos_do_time(time, limite=3):
    """Retorna os próximos jogos futuros do clube em todas as competições coletadas."""
    agora = datetime.datetime.now(FUSO_BRASIL)
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as arquivo:
            jogos = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return []

    futuros_por_id = {}
    for jogo in jogos:
        if not any(
            time_corresponde(str(jogo.get(lado, '')), time)
            for lado in ('mandante', 'visitante')
        ):
            continue
        if str(jogo.get('tipo_status', '')).upper() in {'ENCERRADO', 'AO_VIVO'}:
            continue
        try:
            inicio = datetime.datetime.strptime(
                f"{jogo['data']} {str(jogo['hora'])[:5]}",
                '%Y-%m-%d %H:%M',
            )
            inicio = FUSO_BRASIL.localize(inicio)
        except (KeyError, TypeError, ValueError):
            continue
        if inicio <= agora:
            continue
        identificador = jogo.get('id') or (
            jogo.get('data'), jogo.get('hora'),
            jogo.get('mandante'), jogo.get('visitante'),
        )
        futuros_por_id[identificador] = (inicio, jogo)

    return [
        jogo for _, jogo in sorted(futuros_por_id.values(), key=lambda item: item[0])[:limite]
    ]


# Envia os próximos jogos da competição em cartões com data e horário local.
async def enviar_proximos_jogos(ctx, titulo, liga, times, fala=None):
    jogos = proximos_jogos(liga, times)
    if not jogos:
        await ctx.send(embed=discord.Embed(
            title=titulo,
            description='⚠️ Não achei jogo futuro pra esse filtro. Vai descansar essa corneta um pouco, fiscal.',
            color=discord.Color.orange(),
        ), content=fala)
        return

    detalhes_por_id = await obter_detalhes_dos_jogos(jogos)
    embeds = []
    for jogo in jogos:
        mandante = discord.utils.escape_markdown(
            _nome_com_bandeira(str(jogo.get('mandante', '?')), jogo.get('liga'))
        )
        visitante = discord.utils.escape_markdown(
            _nome_com_bandeira(str(jogo.get('visitante', '?')), jogo.get('liga'))
        )
        try:
            data = datetime.datetime.strptime(
                jogo['data'], '%Y-%m-%d'
            ).strftime('%d/%m/%Y')
        except (KeyError, TypeError, ValueError):
            data = str(jogo.get('data', 'Data não informada'))
        hora = str(jogo.get('hora', '--:--'))[:5]
        nome_liga = _link_liga_flashscore(jogo.get('liga', ''))
        detalhes = detalhes_por_id.get(str(jogo.get('id')), {})
        embed = discord.Embed(
            title=titulo,
            description=(
                f'**{mandante} x {visitante}**\n'
                f'📅 {data} às {hora} (horário de Brasília)\n'
                f'🏆 {nome_liga}'
            ),
            color=discord.Color.blurple(),
        )
        adicionar_campos_local_arbitragem(embed, detalhes)
        embeds.append(embed)

    # O Discord aceita até 10 embeds por mensagem.
    for inicio in range(0, len(embeds), 10):
        await ctx.send(
            content=fala if inicio == 0 else None,
            embeds=embeds[inicio:inicio + 10],
        )


async def enviar_proximos_jogos_do_time(ctx, time):
    jogos = proximos_jogos_do_time(time, limite=3)
    if not jogos:
        await ctx.send(embed=discord.Embed(
            title=f'Próximos jogos de {_nome_com_bandeira(time)}',
            description='⚠️ Não achei jogo futuro desse clube nos dados carregados. A tabela tá mais vazia que teu argumento, pô.',
            color=discord.Color.orange(),
        ), content=f'{ctx.author.mention}, procurei e não veio jogo nenhum.')
        return

    detalhes_por_id = await obter_detalhes_dos_jogos(jogos)
    embeds = []
    for jogo in jogos:
        mandante = discord.utils.escape_markdown(
            _nome_com_bandeira(str(jogo.get('mandante', '?')), jogo.get('liga'))
        )
        visitante = discord.utils.escape_markdown(
            _nome_com_bandeira(str(jogo.get('visitante', '?')), jogo.get('liga'))
        )
        try:
            data = datetime.datetime.strptime(
                jogo['data'], '%Y-%m-%d'
            ).strftime('%d/%m/%Y')
        except (KeyError, TypeError, ValueError):
            data = str(jogo.get('data', 'Data não informada'))
        hora = str(jogo.get('hora', '--:--'))[:5]
        nome_liga = _link_liga_flashscore(jogo.get('liga', ''))
        detalhes = detalhes_por_id.get(str(jogo.get('id')), {})
        embed = discord.Embed(
            title=f'Próximos jogos de {_nome_com_bandeira(time)}',
            description=(
                f'**{mandante} x {visitante}**\n'
                f'📅 {data} às {hora} (horário de Brasília)\n'
                f'🏆 {nome_liga}'
            ),
            color=discord.Color.blurple(),
        )
        adicionar_campos_local_arbitragem(embed, detalhes)
        embeds.append(embed)

    await ctx.send(
        content=(
            f'{ctx.author.mention}, lá vem você secar **{time}**. '
            'Aqui estão os próximos três jogos; tenta não sofrer antes da hora.'
        ),
        embeds=embeds,
    )


async def enviar_fase_grupos(ctx, torneio):
    loop = asyncio.get_running_loop()
    try:
        linhas = await loop.run_in_executor(
            None, obter_classificacao_fase_grupos, torneio
        )
    except Exception as error:
        print(f'[FLASHScore] Falha ao consultar grupos de {torneio}: {error}')
        await ctx.send(embed=discord.Embed(
            title=f'Fase de grupos · {GROUP_STAGE_TITLES[torneio]}',
            description='Não consegui carregar a classificação agora. Dá um tempo e tenta de novo, ô apressado.',
            color=discord.Color.orange(),
            url=GROUP_STAGE_URLS[torneio],
        ), content=f'{ctx.author.mention}, o Flashscore resolveu dar trabalho.')
        return

    if not linhas:
        await ctx.send(embed=discord.Embed(
            title=f'Fase de grupos · {GROUP_STAGE_TITLES[torneio]}',
            description=(
                'A classificação da fase de grupos ainda não apareceu. Até a tabela tá te deixando no vácuo. '
                f'[Abrir no Flashscore]({GROUP_STAGE_URLS[torneio]})'
            ),
            color=discord.Color.orange(),
        ), content=f'{ctx.author.mention}, por enquanto não tem tabela pra mostrar.')
        return

    grupos = {}
    for linha in linhas:
        grupos.setdefault(linha['grupo'], []).append(linha)

    embed = discord.Embed(
        title=f'Fase de grupos · {GROUP_STAGE_TITLES[torneio]}',
        description=(
            f'[Classificação completa no Flashscore]({GROUP_STAGE_URLS[torneio]})\n'
            '`J` jogos · `V` vitórias · `E` empates · `D` derrotas · `SG` saldo · `P` pontos'
        ),
        color=discord.Color.blurple(),
    )
    for nome_grupo, times in sorted(grupos.items()):
        times.sort(key=lambda linha: int(linha['posicao']) if linha['posicao'].isdigit() else 99)
        tabela = '\n'.join(
            f"**{linha['posicao']}. {_nome_com_bandeira(linha['time'], torneio)}** — "
            f"{linha['pontos']} pts · {linha['jogos']}J "
            f"({linha['vitorias']}V {linha['empates']}E {linha['derrotas']}D) · "
            f"{linha['gols']} gols · SG {linha['saldo']}"
            for linha in times
        )
        embed.add_field(name=nome_grupo, value=tabela or 'Sem dados', inline=False)
    await ctx.send(
        content=f'{ctx.author.mention}, tá aí a classificação. Já pode voltar a cornetar com dados na mão.',
        embed=embed,
    )


# Converte cada partida em embed e separa os resultados por situação.
async def formatar_tabelas_jogos(jogos, titulo):
    grupos = (
        ('ENCERRADO', '🏁 Partida encerrada', discord.Color.dark_grey()),
        ('AO_VIVO', '🔴 Partida ao vivo', discord.Color.green()),
        ('FUTURO', '🕒 Partida futura', discord.Color.blurple()),
    )
    detalhes_por_id = await obter_detalhes_dos_jogos(jogos)
    embeds = []
    for status, titulo_status, cor in grupos:
        partidas = [
            jogo for jogo in jogos
            if (
                str(jogo.get('tipo_status', '')).upper() == status
                if status != 'FUTURO'
                else str(jogo.get('tipo_status', '')).upper() not in {'ENCERRADO', 'AO_VIVO'}
            )
        ]
        if not partidas:
            continue

        for jogo in partidas:
            mandante = discord.utils.escape_markdown(
                _nome_com_bandeira(str(jogo.get('mandante', '?')), jogo.get('liga'))
            )
            visitante = discord.utils.escape_markdown(
                _nome_com_bandeira(str(jogo.get('visitante', '?')), jogo.get('liga'))
            )
            placar = str(jogo.get('placar', 'x'))
            hora = str(jogo.get('hora', '--:--'))[:5]
            data = str(jogo.get('data', ''))
            hoje = datetime.datetime.now(FUSO_BRASIL).date().isoformat()
            if data and data != hoje:
                try:
                    data = datetime.datetime.strptime(data, '%Y-%m-%d').strftime('%d/%m/%Y')
                except ValueError:
                    pass
                horario = f'📅 {data} · 🕒 {hora}'
            else:
                horario = f'🕒 {hora}'
            liga = _link_liga_flashscore(jogo.get('liga', '')) or 'Competição não informada'
            status_exibido = str(jogo.get('status', '')).strip()
            detalhe_liga = f'🏆 {liga}'
            if status_exibido:
                detalhe_liga += f' · {discord.utils.escape_markdown(status_exibido)}'
            detalhes = detalhes_por_id.get(str(jogo.get('id')), {})

            embed = discord.Embed(
                title=f'{titulo_status} · {titulo}',
                description=(
                    f'**{mandante} {placar} {visitante}**\n'
                    f'{horario}\n'
                    f'{detalhe_liga}'
                ),
                color=cor,
            )
            adicionar_campos_local_arbitragem(embed, detalhes)
            embeds.append(embed)

    if not embeds:
        return [discord.Embed(
            title=titulo,
            description='⚠️ Nenhum jogo encontrado pra esse filtro. A bola não vai rolar só porque você tá encarando a tela, fiscal de sofá.',
            color=discord.Color.orange(),
        )]
    return embeds


# Centraliza os comandos de jogos e envia os cartões em lotes.
async def enviar_tabela_do_dia(
    ctx, titulo, ligas=None, times=None, incluir_proximos=False, fala=None
):
    # `times` define o alcance da consulta; None significa todas as partidas da liga, sem filtro de clube.
    jogos = jogos_do_dia(ligas, times)
    if incluir_proximos and times:
        data_hoje = datetime.datetime.now(FUSO_BRASIL).date()
        jogos.extend(proximos_jogos(ligas, times, depois_de=data_hoje))
        jogos_unicos = {}
        for jogo in jogos:
            identificador = jogo.get('id') or (
                jogo.get('data'), jogo.get('hora'),
                jogo.get('mandante'), jogo.get('visitante'),
            )
            jogos_unicos[identificador] = jogo
        jogos = sorted(
            jogos_unicos.values(),
            key=lambda jogo: (jogo.get('data', ''), jogo.get('hora', '23:59')),
        )
    embeds = await formatar_tabelas_jogos(jogos, titulo)
    # Discord aceita até 10 embeds por mensagem; os blocos respeitam o limite e mostram a fala só uma vez.
    for inicio in range(0, len(embeds), 10):
        await ctx.send(
            content=fala if inicio == 0 else None,
            embeds=embeds[inicio:inicio + 10],
        )


# EVENTOS DO DISCORD: inicializa os processos que dependem da conexão do cliente.
# Registra o evento chamado pelo Discord quando a sessão fica pronta.
@bot.event
async def on_ready():
    try:
        removidos = limpar_cache_consultas()
        print(f"[PARTIDA] Cache de consultas limpo ({removidos} registro(s)); cadastros de estÃ¡dios preservados.")
    except OSError as error:
        print(f"[PARTIDA] NÃ£o foi possÃ­vel limpar o cache de consultas: {error}")

    for guild in bot.guilds:
        await iniciar_configuracao_servidor(guild)
    if monitoring_loop.is_running():
        monitoring_loop.restart()
    else:
        monitoring_loop.start()
    print(f'Sucesso! Bot conectado como: {bot.user.name}')


@bot.event
async def on_guild_join(guild):
    await iniciar_configuracao_servidor(guild)


@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        await bot.process_commands(message)
        return

    chave_pendente = (message.guild.id, message.channel.id, message.author.id)
    if chave_pendente in _pending_team_confirmations:
        # A resposta é consumida pelo wait_for da confirmação, sem virar outro comando.
        return

    configuracao = guild_settings.get(str(message.guild.id), {})
    if not configuracao.get('initialized'):
        canal_inicial = configuracao.get('setup_channel_id')
        if canal_inicial == message.channel.id:
            texto = message.content.strip()
            if texto.startswith('!'):
                texto = texto[1:].strip()
            time = _resolver_time(texto)
            if time in BRAZILIAN_TEAM_SET:
                configuracao['teams'] = [time]
                configuracao['channel_id'] = canal_inicial
                configuracao['initialized'] = True
                configuracao['prompted'] = False
                _salvar_configuracoes_servidores()
                await message.channel.send(
                    f'{message.author.mention}, **{time}** entrou no radar deste servidor. '
                    f'Use `!<nome do time>` pra adicionar outros clubes, ô gerente de sofá.'
                )
                return
            if time in EUROPEAN_TEAMS:
                await message.channel.send(
                    'A seleção inicial tem que ser um dos 12 grandes do Brasil. '
                    'Depois você adiciona europeu com `!<nome do time>`. Calma, apressadinho.'
                )
                return

    conteudo = message.content.strip()
    torneio = _extrair_comando_fase_grupos(conteudo)
    if torneio is not None:
        contexto = await bot.get_context(message)
        if not torneio:
            await message.channel.send(
                f'{message.author.mention}, fala o torneio, meu consagrado: `!fasegrupos libertadores`, '
                '`!fasegrupos sulamericana` ou `!fg copa do mundo`.'
            )
            return
        if not await _exigir_configuracao_servidor(contexto):
            return
        await enviar_fase_grupos(contexto, torneio)
        return

    time_jogos = _resolver_comando_jogos_time(conteudo)
    if time_jogos:
        contexto = await bot.get_context(message)
        # Consulta manual é independente do filtro; o filtro continua valendo para o monitoramento automático.
        await enviar_proximos_jogos_do_time(contexto, time_jogos)
        return

    if conteudo.startswith('!'):
        time = _resolver_time(conteudo[1:].strip())
        if time:
            await processar_comando_time(await bot.get_context(message), time)
            return

    await bot.process_commands(message)

# COMANDOS DISCORD: cada função abaixo implementa uma ação disponível pelo prefixo !.
# !salve: responde ao cumprimento com a zoeira leve que dá o tom do bot.
@bot.command()
async def salve(ctx):
    await ctx.send(f'Coe {ctx.author.mention}, firmeza? Chegou o fiscal de sofá. Manda a resenha aí, porra. 😎✌🏿')

# !ajuda: publica a lista de comandos e resume como os resultados são exibidos.
@bot.command()
async def ajuda(ctx):
    # Explica a diferença entre consultar jogos e escolher quais clubes recebem alertas automáticos.
    help_text = (
        f"Salve, {ctx.author.mention}! Tá perdido nos comando, né? Respira e escolhe aí, fiscal de sofá. 😎\n\n"
        "Comandos disponíveis:\n"
        "`!salve` - Ganha um salve de volta, sortudo.\n"
        "`!ajuda` - Mostra essa lista, já que a memória falhou.\n\n"
        "`!<nome do time>` - Liga ou desliga o monitoramento automático do clube neste servidor.\n"
        "`!jogos<nome do time>` - Mostra os próximos 3 jogos de qualquer um dos 27 clubes, mesmo fora do filtro.\n"
        "`!jogos` ou `!jogoshoje` - Jogos de hoje dos clubes monitorados neste servidor.\n"
        "`!jogos27`, `!jogostodos` ou `!jogos27times` - Jogos de hoje de todos os 27 clubes, ignorando o filtro.\n"
        "`!jogossulamericanos` - Jogos de hoje e o próximo jogo futuro dos brasileiros monitorados.\n"
        "`!jogoseuropeus` - Jogos de hoje e o próximo jogo futuro dos europeus monitorados.\n\n"
        "`!jogoschampions`, `!jogosucl` ou `!ucl` - Próximos jogos da Champions League entre os clubes monitorados.\n"
        "`!jogoseuropaleague`, `!jogoseuroleague` ou `!euroleague` - Próximos jogos da Europa League entre os monitorados.\n"
        "`!jogosconf`, `!conf` ou `!conferenceleague` - Próximos jogos da Conference League entre os monitorados.\n"
        "`!jogosliberta`, `!libertadores` ou `!liberta` - Próximos jogos da Libertadores entre os brasileiros monitorados.\n"
        "`!fasegrupos<torneio>` ou `!fg<torneio>` - Classificação da Libertadores, Sul-Americana ou Copa do Mundo.\n\n"
        "Nos resultados de hoje, jogo encerrado mostra o placar; ao vivo, o placar atualizado pelo Flashscore. "
        "Agora escolhe um comando e para de me encarar, pô."
    )
    # Envia a mensagem de ajuda no canal
    await ctx.send(help_text)


# !datafifa / !df: publica o aviso de data FIFA sob demanda.
@bot.command(aliases=['df'])
async def datafifa(ctx):
    await ctx.send(AVISO_SELECAO_BRASILEIRA)


# !selecao e apelidos: lista as partidas da Seleção registradas na coleta do Flashscore.
@bot.command(aliases=[
    'seleção', 'seleçãocanarinho', 'seleçãocararinho',
    'canarinho', 'seleçãobostileira',
])
async def selecao(ctx):
    jogos = _jogos_selecao_registrados()
    if not jogos:
        await ctx.send('sem jogo da seleção por enquanto...GRAÇAS A DEUS!!')
        return

    linhas = ['**Jogos registrados da Seleção Brasileira:**']
    for jogo in jogos[-20:]:
        inicio = _inicio_jogo_selecao(jogo)
        data_hora = inicio.strftime('%d/%m/%Y às %H:%M') if inicio else 'Data não informada'
        mandante = str(jogo.get('mandante', '?'))
        visitante = str(jogo.get('visitante', '?'))
        status = str(jogo.get('tipo_status', '')).upper()
        placar = str(jogo.get('placar', 'x')).strip()
        resumo = f' · **{placar}**' if placar and placar.casefold() != 'x' else ''
        situacao = ' · encerrado' if status == 'ENCERRADO' else (
            ' · ao vivo' if status == 'AO_VIVO' else ''
        )
        linhas.append(f'• {data_hora} — {mandante} x {visitante}{resumo}{situacao}')

    mensagem = '\n'.join(linhas)
    for inicio in range(0, len(mensagem), 1900):
        await ctx.send(mensagem[inicio:inicio + 1900])

# !jogos / !jogoshoje: consulta os jogos de hoje dos times que este servidor escolheu monitorar.
@bot.command(aliases=['jogoshoje'])
async def jogos(ctx):
    if not await _exigir_configuracao_servidor(ctx):
        return
    await enviar_tabela_do_dia(
        ctx,
        'Jogos de hoje · clubes monitorados',
        times=_times_do_servidor(ctx.guild.id),
        fala=f'{ctx.author.mention}, catei os jogos dos times no radar deste servidor. Aí, fiscal de sofá.',
    )


# Consulta os jogos de hoje de todos os clubes cadastrados, sem depender da seleção deste servidor.
@bot.command(aliases=['jogostodos', 'jogos27times'])
async def jogos27(ctx):
    await enviar_tabela_do_dia(
        ctx,
        'Jogos de hoje · os 27 clubes',
        times=ELIGIBLE_TEAMS,
        fala=f'{ctx.author.mention}, aqui estão os jogos de hoje dos 27 clubes. Sim, até os que você esqueceu, cacete.',
    )


# !jogossulamericanos: mostra hoje e o próximo jogo futuro dos clubes brasileiros monitorados.
@bot.command(aliases=['sulamericanos'])
async def jogossulamericanos(ctx):
    if not await _exigir_configuracao_servidor(ctx):
        return
    await enviar_tabela_do_dia(
        ctx,
        'Futebol sul-americano: hoje e próximos jogos',
        SOUTH_AMERICAN_LEAGUES,
        _times_do_servidor(ctx.guild.id, 'brasil'),
        incluir_proximos=True,
        fala=f'{ctx.author.mention}, aqui vai a agenda dos brasileiros no radar. Já separa a corneta.',
    )


# !jogoseuropeus: mostra hoje e o próximo jogo futuro dos clubes europeus monitorados.
@bot.command(aliases=['europeus'])
async def jogoseuropeus(ctx):
    if not await _exigir_configuracao_servidor(ctx):
        return
    await enviar_tabela_do_dia(
        ctx,
        'Futebol europeu: hoje e próximos jogos',
        EUROPEAN_LEAGUES,
        _times_do_servidor(ctx.guild.id, 'europa'),
        incluir_proximos=True,
        fala=f'{ctx.author.mention}, agenda europeia na mão. Não confunde fuso e passa vergonha, hein.',
    )


# As consultas por competição continuam limitadas aos clubes monitorados neste servidor.
@bot.command(aliases=['jogosucl', 'ucl'])
async def jogoschampions(ctx):
    if not await _exigir_configuracao_servidor(ctx):
        return
    await enviar_proximos_jogos(
        ctx, 'Próximos jogos da Champions League', 'champions league',
        _times_do_servidor(ctx.guild.id, 'europa'),
        fala=f'{ctx.author.mention}, olha a Champions aí. Se teu time pipocar, não põe a culpa no bot.',
    )


@bot.command(aliases=['jogoseuroleague', 'jogoseuro', 'euroleague'])
async def jogoseuropaleague(ctx):
    if not await _exigir_configuracao_servidor(ctx):
        return
    await enviar_proximos_jogos(
        ctx, 'Próximos jogos da Europa League', 'europa league',
        _times_do_servidor(ctx.guild.id, 'europa'),
        fala=f'{ctx.author.mention}, agenda da Europa League na mão. Vai cornetar com responsabilidade, hein.',
    )


@bot.command(aliases=[
    'jogoscoferenceleague', 'jogosconferenceleague', 'conf', 'conferenceleague'
])
async def jogosconf(ctx):
    if not await _exigir_configuracao_servidor(ctx):
        return
    await enviar_proximos_jogos(
        ctx, 'Próximos jogos da Conference League', 'conference league',
        _times_do_servidor(ctx.guild.id, 'europa'),
        fala=f'{ctx.author.mention}, toma aí a Conference League. Não vale fingir que já conhecia todo mundo.',
    )


@bot.command(aliases=['jogoslibertadores', 'libertadores', 'liberta'])
async def jogosliberta(ctx):
    if not await _exigir_configuracao_servidor(ctx):
        return
    await enviar_proximos_jogos(
        ctx, 'Próximos jogos da Copa Libertadores', 'libertadores',
        _times_do_servidor(ctx.guild.id, 'brasil'),
        fala=f'{ctx.author.mention}, aqui está a Libertadores dos brasileiros monitorados. Prepara a corneta, meu consagrado.',
    )


# MONITORAMENTO: atualiza os dados globais; os avisos automáticos abaixo respeitam o filtro de cada servidor.
@tasks.loop(seconds=CHECK_INTERVAL)
async def monitoring_loop():
    global _aviso_selecao_verificado_nesta_execucao
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, atualizar_arquivo)
    except Exception as error:
        print(f"[LOOP] Falha ao atualizar os jogos: {error}")

    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as arquivo:
            jogos = json.load(arquivo)
        jogos_ativos = [
            jogo for jogo in jogos
            if isinstance(jogo, dict)
            and str(jogo.get('tipo_status', '')).upper() != 'ENCERRADO'
        ]
        await obter_detalhes_dos_jogos(jogos_ativos)
        print(f"[PARTIDA] Detalhes atualizados/verificados para {len(jogos_ativos)} jogo(s) ativo(s).")
    except (OSError, json.JSONDecodeError) as error:
        print(f"[PARTIDA] NÃ£o foi possÃ­vel carregar os jogos para atualizar detalhes: {error}")
    except Exception as error:
        print(f"[PARTIDA] Falha ao atualizar detalhes dos jogos ativos: {error}")

    # O aviso é avaliado uma vez por inicialização e enviado a cada canal configurado.
    if not _aviso_selecao_verificado_nesta_execucao:
        try:
            agora = datetime.datetime.now(FUSO_BRASIL)
            proximos = [
                inicio
                for jogo in _jogos_selecao_registrados()
                if str(jogo.get('tipo_status', '')).upper() == 'FUTURO'
                and (inicio := _inicio_jogo_selecao(jogo)) is not None
                and inicio > agora
            ]
            if proximos:
                horas_restantes = (min(proximos) - agora).total_seconds() / 3600
                if horas_restantes < 168:
                    _aviso_selecao_verificado_nesta_execucao = True
                    for guild in bot.guilds:
                        configuracao = guild_settings.get(str(guild.id), {})
                        if not configuracao.get('initialized'):
                            continue
                        for canal_id in _canais_configurados(configuracao):
                            canal = bot.get_channel(canal_id)
                            if canal is None:
                                try:
                                    canal = await bot.fetch_channel(canal_id)
                                except discord.HTTPException:
                                    continue
                            try:
                                await canal.send(AVISO_SELECAO_BRASILEIRA)
                            except discord.HTTPException as error:
                                print(f'[SELEÇÃO] Falha ao enviar aviso em {canal_id}: {error}')
                _aviso_selecao_verificado_nesta_execucao = True
        except Exception as error:
            print(f'[SELEÇÃO] Não foi possível avaliar o aviso de data FIFA: {error}')

    # Cada servidor recebe alertas apenas dos clubes que selecionou para monitoramento.
    for guild in bot.guilds:
        configuracao = guild_settings.get(str(guild.id), {})
        if not configuracao.get('initialized'):
            continue
        canais_ids = _canais_configurados(configuracao)
        if not canais_ids:
            continue

        times_brasileiros = _times_do_servidor(guild.id, 'brasil')
        times_europeus = _times_do_servidor(guild.id, 'europa')
        for canal_id in canais_ids:
            try:
                await verificar_resenha(
                    bot=bot,
                    alert_channel_id=canal_id,
                    rival_teams=times_brasileiros,
                    european_teams=times_europeus,
                    proximo_jogo_europeu_func=(
                        lambda: obter_proximo_jogo_european_teams(
                            times_filtro=times_europeus
                        )
                    ) if times_europeus else None,
                    proximo_jogo_brasileiro_func=(
                        lambda: obter_proximo_jogo_brasileirao(
                            times_filtro=times_brasileiros
                        )
                    ) if times_brasileiros else None,
                    state_key=f'{guild.id}:{canal_id}',
                )
            except Exception as error:
                print(f"[LOOP] Falha ao verificar a resenha em {guild.name}: {error}")

            if times_europeus:
                try:
                    await verificar_partidas_europeias(
                        bot, canal_id, times_europeus,
                        state_key=f'{guild.id}:{canal_id}',
                    )
                except Exception as error:
                    print(f"[LOOP] Falha ao monitorar a Europa em {guild.name}: {error}")


# Inicialização: valida a credencial antes de conectar o cliente ao Discord.
if not DISCORD_TOKEN:
    raise RuntimeError("Defina DISCORD_TOKEN no ambiente ou no arquivo .env.")
bot.run(DISCORD_TOKEN)
# Configure DISCORD_TOKEN no arquivo .env para autenticar o bot no Discord.
