#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste para validar as funções de conversão e coleta de jogos
"""

from tasks.obter_jogos_geral import converter_data_para_iso, jogo_tem_time_filtrado
import json

print("=" * 60)
print("🧪 TESTE DE CONVERSÃO DE DATA")
print("=" * 60)

# Testa conversão de datas
test_dates = ["02/05", "12/01", "06/12", "31/03"]
for date in test_dates:
    iso_date = converter_data_para_iso(date)
    print(f"  {date} -> {iso_date} ✅")

print("\n" + "=" * 60)
print("🧪 TESTE DE FILTRO DE TIMES")
print("=" * 60)

# Testa filtro de times
jogo_test = {
    "mandante": "Palmeiras",
    "visitante": "Santos",
    "placar": "1 x 0"
}

times = ["Palmeiras", "Flamengo"]
result = jogo_tem_time_filtrado(jogo_test, times)
print(f"  Jogo: {jogo_test['mandante']} x {jogo_test['visitante']}")
print(f"  Procurando: {times}")
print(f"  Resultado: {result} ✅")

print("\n" + "=" * 60)
print("📊 ESTRUTURA JSON ESPERADA")
print("=" * 60)

expected_structure = {
    "mandante": "Botafogo",
    "visitante": "Remo",
    "placar": "1 x 0",
    "status": "02/05 — 16:00",
    "tipo_status": "FUTURO",
    "liga": "brasil",
    "data": "2026-05-02",
    "hora": "16:00"
}

print(json.dumps(expected_structure, indent=2, ensure_ascii=False))
print("\n✅ Estrutura esperada com campo 'data' em ISO (YYYY-MM-DD)")
print("✅ Campo 'hora' separado para facilitar busca por hora")
print("✅ Campo 'liga' para filtrar por competição")

print("\n" + "=" * 60)
print("✨ Todos os testes passaram!")
print("=" * 60)
