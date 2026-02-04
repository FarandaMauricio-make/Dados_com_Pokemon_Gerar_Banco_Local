# Pokémon Data Warehouse

Este projeto conecta-se à **PokéAPI** e salva informações detalhadas sobre todos os pokémons em um banco de dados **SQLite**.  
Os dados incluem atributos básicos, estatísticas, tipos, movimentos, espécies e cadeias de evolução.

---

## 🚀 Funcionalidades
- Criação automática de tabelas no banco `pokemon_dw.db`:
  - **pokemon**: dados básicos (id, nome, altura, peso, experiência base).  
  - **pokemon_stats**: estatísticas base (HP, ataque, defesa, etc.).  
  - **pokemon_types**: tipos de cada pokémon (fogo, água, planta...).  
  - **pokemon_moves**: movimentos/ataques (limitados a 5 por pokémon).  
  - **species**: informações adicionais (taxa de captura, lendário, mítico, habitat, cor).  
  - **evolution**: cadeias de evolução e condições (nível, item, horário, etc.).  

- Busca assíncrona em **lotes** (batch) usando `aiohttp` e `asyncio`.  
- **Retry automático** em caso de falha de conexão com a API.  
- Evita duplicados verificando se o pokémon já existe no banco.  
- Exibe progresso durante a execução.  

---

## 📦 Requisitos
- Python 3.9+  
- Bibliotecas:
  ```bash
  pip install aiohttp requests

⚙️ Como executar
1. Clone ou copie este código para sua máquina.

2. Instale as dependências com pip install aiohttp requests.

3. Execute o script:

  python pokemon_pc.py

4. O programa criará o arquivo pokemon_dw.db com todas as tabelas e dados.

📊 Visualização dos dados
Você pode explorar os dados de duas formas:

Usando Python

import sqlite3

conn = sqlite3.connect("pokemon_dw.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM pokemon LIMIT 10")
print(cursor.fetchall())

conn.close()

Usando DB Browser for SQLite

1. Baixe em https://sqlitebrowser.org.
2. Abra o arquivo pokemon_dw.db.
3. Navegue pelas tabelas na aba Browse Data.
4. Execute consultas SQL na aba Execute SQL.

🔎 Exemplos de consultas SQL
Listar todos os pokémons lendários:

SELECT p.id, p.name
FROM pokemon p
JOIN species s ON p.id = s.pokemon_id
WHERE s.is_legendary = 1;

Ver evoluções do Bulbasaur:

SELECT * FROM evolution WHERE from_species = 'bulbasaur';

Tipos do Charizard:

SELECT * FROM pokemon_types WHERE pokemon_id = 6;

⚠️ Observações
A PokéAPI retorna um número total de pokémons (count), mas alguns IDs ainda não existem.

  Nestes casos, o programa detecta o erro 404 e pula o ID.

A tabela pokemon_moves está limitada a 5 movimentos por pokémon para evitar excesso de dados.

  Se quiser salvar todos, basta remover o [:5] no loop de movimentos.

📌 Resultado esperado

Ao final da execução, você terá:

~1025 pokémons salvos (quantidade atual na PokéAPI).
~484 evoluções registradas.
Todas as tabelas populadas com dados consistentes e prontos para análise.
