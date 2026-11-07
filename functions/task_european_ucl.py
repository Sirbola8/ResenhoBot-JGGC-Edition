"""Consulta, filtra e formata partidas de clubes europeus e da Champions League."""
import json
import os
import asyncio
from datetime import datetime, timedelta
import discord

from config import EUROPEAN_LEAGUES, EUROPEAN_TEAMS
from functions.team_utils import jogo_tem_time_europeu
from functions.task_match_info import obter_detalhes_dos_jogos, formatar_local_arbitragem

# Arquivo atualizado pela coleta e compartilhado com os alertas automáticos.
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dados_jogos.json")

# LEITURA E FILTROS: selecionam competições e clubes a partir da coleta compartilhada.
def obter_jogos_ucl(arquivo_json=DATA_PATH):
    """
    Busca todos os jogos da UEFA Champions League no arquivo JSON.

    Args:
        arquivo_json: Caminho do arquivo JSON com os dados dos jogos

    Returns:
        Lista de dicionários com informações dos jogos da UCL
    """
    try:
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            jogos = json.load(f)

        # Filtra apenas jogos da Champions League
        jogos_ucl = [j for j in jogos if j.get('liga', '').lower() == 'europa' or 
                    'champions' in j.get('liga', '').lower() or
                    'champions' in j.get('status', '').lower()]

        return jogos_ucl
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def obter_jogos_european_teams(arquivo_json=DATA_PATH, times_filtro=None):
    """
    Busca todos os jogos que envolvem times europeus.

    Args:
        arquivo_json: Caminho do arquivo JSON com os dados dos jogos
        times_filtro: Lista de times para filtrar. Se None, usa EUROPEAN_TEAMS

    Returns:
        Lista de dicionários com informações dos jogos dos times europeus
    """
    if times_filtro is None:
        times_filtro = EUROPEAN_TEAMS

    try:
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            jogos = json.load(f)

        return [
            jogo
            for jogo in jogos
            if str(jogo.get("liga", "")).casefold().strip() in EUROPEAN_LEAGUES
            and jogo_tem_time_europeu(jogo, times_filtro)
        ]
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def obter_jogos_ucl_european_teams(arquivo_json=DATA_PATH):
    """
    Busca jogos da UEFA Champions League que envolvem times europeus.

    Args:
        arquivo_json: Caminho do arquivo JSON com os dados dos jogos

    Returns:
        Lista de dicionários com informações dos jogos da UCL com times europeus
    """
    jogos_ucl = obter_jogos_ucl(arquivo_json)
    return [
        jogo
        for jogo in jogos_ucl
        if str(jogo.get("liga", "")).casefold().strip() in EUROPEAN_LEAGUES
        and jogo_tem_time_europeu(jogo, EUROPEAN_TEAMS)
    ]

# Encontra o próximo jogo válido sem selecionar partidas antigas ou encerradas.
def obter_proximo_jogo_european_teams(arquivo_json=DATA_PATH, times_filtro=None):
    """
    Busca APENAS o próximo jogo dos times europeus selecionados.
    Não retorna jogos com datas inválidas (como 0001-01-01).

    Args:
        arquivo_json: Caminho do arquivo JSON com os dados dos jogos
        times_filtro: Lista de times para filtrar. Se None, usa EUROPEAN_TEAMS

    Returns:
        Dicionário com informações do próximo jogo ou None se não houver
    """
    if times_filtro is None:
        times_filtro = EUROPEAN_TEAMS

    try:
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            jogos = json.load(f)

        # Obtém a data de hoje
        hoje = datetime.now().date().isoformat()

        # Filtra jogos que envolvem times europeus e são futuros (não encerrados)
        jogos_futuros = []
        for j in jogos:
            if str(j.get('liga', '')).casefold().strip() not in EUROPEAN_LEAGUES:
                continue
            data_jogo = j.get('data', '')

            # Valida se a data é válida (não é 0001-01-01 ou inferior a hoje)
            if not data_jogo or data_jogo < '2000-01-01' or data_jogo < hoje:
                continue

            # Verifica se é um time filtrado e se não está encerrado
            if jogo_tem_time_europeu(j, times_filtro) and \
               "ENCERRADO" not in j.get('tipo_status', '') and \
               "CANCELADO" not in j.get('tipo_status', ''):
                jogos_futuros.append(j)

        # Ordena por data e hora para encontrar o próximo
        jogos_futuros.sort(key=lambda x: (x.get('data', '9999-12-31'), x.get('hora', '23:59')))

        # Retorna apenas o primeiro (próximo jogo) se a data for válida
        if jogos_futuros:
            proximo = jogos_futuros[0]
            data = proximo.get('data', '')
            # Validação final: garante que data não é inválida
            if data and data > '2000-01-01' and data < '2099-12-31':
                return proximo

        return None

    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

# FORMATAÇÃO: prepara data, hora e status no formato legível do Discord.
def formatar_data_hora_jogo(jogo):
    """
    Formata a data e hora do jogo para exibição legível.

    Args:
        jogo: Dicionário com informações do jogo

    Returns:
        String formatada com data e hora ou apenas hora se data não disponível
    """
    data = jogo.get('data', '')
    hora = jogo.get('hora', 'N/A')

    if data and data != '':
        try:
            # Converte formato ISO (2026-05-02) para formato legível (02/05/2026)
            data_obj = datetime.strptime(data, '%Y-%m-%d')
            data_formatada = data_obj.strftime('%d/%m/%Y')
            return f"{data_formatada} às {hora}"
        except (ValueError, TypeError):
            # Se falhar a conversão, retorna apenas a hora
            return f"Data: {data} às {hora}"

    return f"às {hora}"

def formatar_mensagem_jogos(jogos, titulo):
    """
    Formata uma lista de jogos em uma mensagem Discord.

    Args:
        jogos: Lista de dicionários com informações dos jogos
        titulo: Título da mensagem

    Returns:
        String formatada para enviar ao Discord
    """
    if not jogos:
        return f"⚠️ {titulo} - Nenhum jogo no momento."

    mensagem = f"**{titulo}**\n\n"

    for j in jogos:
        # Escolhe um símbolo para distinguir partidas encerradas, ao vivo e futuras.
        if "ENCERRADO" in j.get('tipo_status', '') or "CANCELADO" in j.get('tipo_status', '') or "ADIADO" in j.get('tipo_status', ''):
            emoji = "⬛"
        elif "AO_VIVO" in j.get('tipo_status', ''):
            emoji = "🟢"
        else:  # Futuros
            emoji = "🔵"

        # Formata data e hora
        data_hora = formatar_data_hora_jogo(j)

        linha = f"{emoji} {j.get('mandante', '?')} {j.get('placar', 'x')} {j.get('visitante', '?')} - {data_hora}\n"
        mensagem += linha

    mensagem += f"\n📊 Total: {len(jogos)} jogo(s)"

    return mensagem

# ALERTAS: monta embeds por partida e controla notificações repetidas entre ciclos.
async def enviar_alerta_jogos(bot, canal_id, jogos, titulo, embed_color=discord.Color.blue()):
    """
    Envia um alerta no Discord com os jogos encontrados.

    Args:
        bot: Instância do bot Discord
        canal_id: ID do canal para enviar a mensagem
        jogos: Lista de jogos para exibir
        titulo: Título do embed
        embed_color: Cor do embed
    """
    if not jogos:
        return

    try:
        detalhes_por_id = await obter_detalhes_dos_jogos(jogos)
        canal = bot.get_channel(canal_id)
        if not canal:
            print(f"⚠️ Canal {canal_id} não encontrado")
            return

        # Cria um embed
        embed = discord.Embed(
            title=titulo,
            color=embed_color,
            timestamp=datetime.now()
        )

        for j in jogos:
            # Repete o código visual do status no embed do alerta.
            if "ENCERRADO" in j.get('tipo_status', '') or "CANCELADO" in j.get('tipo_status', ''):
                emoji = "⬛"
            elif "AO_VIVO" in j.get('tipo_status', ''):
                emoji = "🟢"
            else:
                emoji = "🔵"

            nome_campo = f"{emoji} {j.get('mandante', '?')} vs {j.get('visitante', '?')}"
            detalhes = detalhes_por_id.get(str(j.get("id")), {})
            local_arbitragem = formatar_local_arbitragem(detalhes)
            valor_campo = (
                f"Placar: {j.get('placar', 'x')}\n"
                f"Status: {j.get('status', 'N/A')}\n"
                f"Liga: {j.get('liga', 'N/A')}\n"
                f"{local_arbitragem}"
            )

            embed.add_field(name=nome_campo, value=valor_campo, inline=False)

        embed.set_footer(text=f"Total: {len(jogos)} jogo(s)")

        await canal.send(embed=embed)
        print(f"✅ Alerta enviado: {titulo}")

    except Exception as e:
        print(f"❌ Erro ao enviar alerta: {e}")

# Dicionários para rastrear últimos jogos alertados (para evitar duplicatas)
ultimo_alerta_ucl = {}
ultimo_alerta_europeus = {}

async def verificar_e_alertar_ucl(bot, canal_id, arquivo_json=DATA_PATH):
    """
    Verifica jogos da UCL e envia alerta se houver mudanças.

    Args:
        bot: Instância do bot Discord
        canal_id: ID do canal para enviar alertas
        arquivo_json: Caminho do arquivo JSON com os dados dos jogos
    """
    jogos_ucl = obter_jogos_ucl(arquivo_json)

    if not jogos_ucl:
        return

    # A Champions só gera atualização quando está ao vivo ou registra resultado final.
    jogos_importantes = [j for j in jogos_ucl if "AO_VIVO" in j.get('tipo_status', '') or 
                        "ENCERRADO" in j.get('tipo_status', '')]

    if not jogos_importantes:
        return

    # Resume os dados da UCL para evitar reenviar o mesmo estado em todos os ciclos.
    hash_atual = hash(json.dumps(jogos_importantes, sort_keys=True))

    global ultimo_alerta_ucl
    if hash_atual != ultimo_alerta_ucl.get('hash', None):
        await enviar_alerta_jogos(bot, canal_id, jogos_importantes, 
                                 "⚽ Atualização - UEFA Champions League", 
                                 discord.Color.gold())
        ultimo_alerta_ucl['hash'] = hash_atual

async def verificar_e_alertar_european_teams(bot, canal_id, arquivo_json=DATA_PATH):
    """
    Verifica jogos dos times europeus e envia alerta se houver mudanças.

    Args:
        bot: Instância do bot Discord
        canal_id: ID do canal para enviar alertas
        arquivo_json: Caminho do arquivo JSON com os dados dos jogos
    """
    jogos_europeus = obter_jogos_european_teams(arquivo_json)

    if not jogos_europeus:
        return

    # Para os demais clubes europeus, considera apenas partidas ao vivo ou encerradas.
    jogos_importantes = [j for j in jogos_europeus if "AO_VIVO" in j.get('tipo_status', '') or 
                        "ENCERRADO" in j.get('tipo_status', '')]

    if not jogos_importantes:
        return

    # O hash permite publicar novamente apenas quando o estado monitorado se altera.
    hash_atual = hash(json.dumps(jogos_importantes, sort_keys=True))

    global ultimo_alerta_europeus
    if hash_atual != ultimo_alerta_europeus.get('hash', None):
        await enviar_alerta_jogos(bot, canal_id, jogos_importantes, 
                                 "🇪🇺 Atualização - Times Europeus", 
                                 discord.Color.purple())
        ultimo_alerta_europeus['hash'] = hash_atual
