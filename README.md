# ⚽ ResenhoBot

Bot de futebol para Discord, escrito em Python. Ele consulta partidas e classificações no Flashscore, permite escolher os clubes monitorados em cada servidor e publica resultados, lembretes e alertas de partidas ao vivo.

## Funcionalidades

- Agenda e resultados dos clubes configurados: 12 brasileiros e 18 europeus.
- Alertas automáticos de início, gols e marcos de período. Os placares ao vivo vêm do feed de partidas em andamento do Flashscore.
- Lembretes de partidas futuras com 24 horas e 30 minutos de antecedência e lembrete diário às 13h para partidas ainda não encerradas.
- Consulta dos próximos jogos de um clube, da agenda do dia e das competições continentais.
- Classificações de Libertadores, Sul-Americana e Copa do Mundo por grupos.
- Comando `!tabela` com HUD paginado para Brasileirão Série A, Premier League, LaLiga, Serie A italiana, Bundesliga e Ligue 1. Mostra dez posições por página e as setas avançam até o fim da tabela.
- Dados de configuração e histórico de alertas salvos por servidor, evitando que o bot dependa de configurações em memória após reiniciar.

O monitoramento de partidas roda a cada 70 segundos. Os lembretes de agenda são verificados a cada 15 segundos.

## Requisitos

- Python e `pip`.
- Uma aplicação de bot criada no [Discord Developer Portal](https://discord.com/developers/applications).

No painel do Discord, habilite **Message Content Intent** em *Bot → Privileged Gateway Intents*. Ao convidar o bot, conceda acesso aos canais em que ele será usado, além das permissões **Send Messages** e **Embed Links**.

## Instalação e execução

Na raiz do projeto, crie e ative um ambiente virtual e instale as dependências:

```bash
python -m venv .venv
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
Copy-Item env.example .env
```

```bash
# Linux ou macOS
source .venv/bin/activate
cp env.example .env
```

Edite `.env` e informe o token do bot:

```dotenv
DISCORD_TOKEN=seu_token_do_discord
```

Instale as dependências e inicie o bot:

```bash
pip install -r requirements.txt
python bot.py
```

O bot encerra a inicialização com uma mensagem de erro se `DISCORD_TOKEN` não estiver definido. Não compartilhe o token nem o envie para o repositório.

## Configuração no Discord

Quando o bot entrar no servidor, ele inicia a configuração pedindo um clube brasileiro. Use `!configresenha` (ou `!config`) para consultar a configuração atual ou iniciar o cadastro se o servidor ainda não foi configurado. Depois de escolher o primeiro clube:

1. Use `!<nome do time>` para adicionar um clube ao monitoramento do servidor.
2. Para remover um clube, use o mesmo comando e confirme com `sim` ou `não`.
3. Use `!aqui` no canal que deve receber os avisos automáticos. Cada servidor pode definir seu próprio canal.

O primeiro clube deve ser um dos brasileiros. Depois, podem ser adicionados os demais clubes brasileiros e os europeus listados em `config.py`. As configurações por servidor ficam em `data/monitoramento_servidores.json`, criado durante a execução.

## Comandos

| Comando | O que faz |
| --- | --- |
| `!ajuda` | Exibe a ajuda no Discord. |
| `!configresenha`, `!config`, `!configuracao` ou `!setup` | Mostra a configuração do servidor ou inicia o cadastro se ainda não estiver configurado. |
| `!aqui` | Define o canal atual como destino dos avisos automáticos do servidor. |
| `!<nome do time>` | Adiciona ou remove um clube da lista monitorada. Exemplo: `!Flamengo`. |
| `!jogos` ou `!jogoshoje` | Mostra os jogos de hoje dos clubes monitorados no servidor. |
| `!jogos<nome do time>` | Mostra os próximos três jogos do clube. Exemplo: `!jogosManchester City`. |
| `!jogos27`, `!jogostodos` ou `!jogos27times` | Mostra os jogos de hoje de todos os clubes cadastrados no código (12 brasileiros e 18 europeus). Os nomes `jogos27` e `jogos27times` são aliases antigos. |
| `!jogossulamericanos` ou `!sulamericanos` | Mostra jogos do dia e o próximo jogo futuro dos brasileiros monitorados. |
| `!jogoseuropeus` ou `!europeus` | Mostra jogos do dia e o próximo jogo futuro dos europeus monitorados. |
| `!jogoschampions`, `!jogosucl` ou `!ucl` | Mostra próximos jogos da Champions League entre os clubes monitorados. |
| `!jogoseuropaleague`, `!jogoseuroleague`, `!jogoseuro` ou `!euroleague` | Mostra próximos jogos da Europa League entre os clubes monitorados. |
| `!jogosconf`, `!conf` ou `!conferenceleague` | Mostra próximos jogos da Conference League entre os clubes monitorados. |
| `!jogosliberta`, `!libertadores` ou `!liberta` | Mostra próximos jogos da Libertadores entre os brasileiros monitorados. |
| `!fasegrupos <torneio>` ou `!fg <torneio>` | Mostra a classificação por grupos da Libertadores, Sul-Americana ou Copa do Mundo. |
| `!tabela <liga>`, `!classificacao <liga>` ou `!standings <liga>` | Mostra a classificação com setas para navegar pelas posições. |
| `!selecao` | Lista os jogos registrados da Seleção Brasileira. |
| `!datafifa` ou `!df` | Publica o aviso de Data FIFA. |
| `!salve` | Responde ao cumprimento. |

Para `!tabela`, os nomes aceitos incluem `brasileirão`, `premier league`, `laliga`, `serie a`, `bundesliga` e `ligue 1`. Exemplos de classificação por grupos: `!fasegrupos libertadores`, `!fg sulamericana` e `!fg copa do mundo`.

## Arquivos principais

- `bot.py`: comandos, configuração dos servidores e lógica de notificações do Discord.
- `config.py`: clubes, aliases, competições e intervalo do monitoramento.
- `functions/league_standings.py`: consulta e interpretação das tabelas das ligas.
- `functions/task_match_info.py`: consulta e cache dos detalhes das partidas.
- `tasks/obter_jogos_geral.py`: coleta e normalização dos jogos e placares do Flashscore.
- `tasks/task_update_data.py`: atualiza `data/dados_jogos.json`, usado pelos comandos e alertas.
- `data/monitoramento_servidores.json`: preferências e estado dos avisos por servidor, criado durante a execução.
- `data/detalhes_partidas.json`: cache de detalhes de partidas, criado durante a execução.

As páginas e feeds do Flashscore são consultados em tempo de execução; a disponibilidade dos comandos de dados depende do acesso ao serviço.

## Contribuição

1. Faça um fork do projeto.
2. Crie uma branch para a alteração: `git checkout -b feature/minha-alteracao`.
3. Faça commits com as mudanças.
4. Envie a branch e abra um Pull Request.

## Colaboradores

- [Jean Michel](https://github.com/Gl1tch42) — Lead Developer
- [Jão Gabriel](https://github.com/Sirbola8) — Developer
- [Kaio Msr](https://github.com/Kaio-Msr) — Developer
