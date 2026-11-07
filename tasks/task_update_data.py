"""Atualiza e grava os jogos monitorados no JSON compartilhado pelo bot."""

import json
import os
from tasks.obter_jogos_geral import obter_jogos, jogo_tem_time_filtrado

from config import (
    BRAZIL_NATIONAL_TEAM, EUROPEAN_LEAGUES, EUROPEAN_TEAMS,
    SOUTH_AMERICAN_LEAGUES, SOUTH_AMERICAN_TEAMS,
)

# Atualiza a coleta completa para alimentar comandos e alertas automáticos.
def atualizar_arquivo():
    print("🔄 Atualizando dados de jogos com resenha...")
    try:
        # Obtém todos os jogos (brasileiros + europeus)
        todos_jogos = obter_jogos()
        
        # Mantém somente jogos dos clubes configurados na região correspondente.
        jogos_brasileiros = []
        jogos_europeus = []
        jogos_selecao = []
        for jogo in todos_jogos:
            liga = str(jogo.get("liga", "")).casefold().strip()
            if liga == "selecao brasileira" and jogo_tem_time_filtrado(
                jogo, [BRAZIL_NATIONAL_TEAM]
            ):
                jogos_selecao.append(jogo)
            elif liga in SOUTH_AMERICAN_LEAGUES and jogo_tem_time_filtrado(
                jogo, SOUTH_AMERICAN_TEAMS
            ):
                jogos_brasileiros.append(jogo)
            elif liga in EUROPEAN_LEAGUES and jogo_tem_time_filtrado(
                jogo, EUROPEAN_TEAMS
            ):
                jogos_europeus.append(jogo)

        # Combina ambos: primeiro brasileiros, depois europeus
        jogos_combinados = jogos_brasileiros + jogos_europeus + jogos_selecao

        # Cria o caminho do arquivo de forma compatível
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        json_path = os.path.join(data_dir, 'dados_jogos.json')

        # Cria o diretório se não existir
        os.makedirs(data_dir, exist_ok=True)

        # Salva também uma lista vazia quando não há jogos, para não manter dados antigos.
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(jogos_combinados, f, ensure_ascii=False, indent=4)

        # Log detalhado
        print("✅ Arquivo atualizado com sucesso!")
        print(f"   📊 Jogos brasileiros: {len(jogos_brasileiros)}")
        print(f"   📊 Jogos europeus: {len(jogos_europeus)}")
        print(f"   📊 Total de jogos: {len(jogos_combinados)}")
        if not jogos_combinados:
            print("   ℹ️ Nenhum jogo corresponde aos times monitorados nesta coleta.")
    # Registra falhas da coleta com traceback para facilitar o diagnóstico.
    except Exception as e:
        print(f"❌ Erro na task: {e}")
        import traceback
        traceback.print_exc()
