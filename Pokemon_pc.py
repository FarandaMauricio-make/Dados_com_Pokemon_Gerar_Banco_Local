import aiohttp
import asyncio
import sqlite3
import requests

# Função assíncrona com retry para buscar dados da API
async def fetch_with_retry(session, url, retries=3, delay=2):
    """
    Tenta buscar a URL até 'retries' vezes, com pausa 'delay' segundos entre tentativas.
    Se falhar todas as tentativas, retorna None.
    """
    for attempt in range(retries):
        try:
            async with session.get(url, timeout=10) as resp:
                return await resp.json()
        except Exception as e:
            print(f"Erro na requisição {url}: {e}. Tentando novamente ({attempt+1}/{retries})...")
            await asyncio.sleep(delay)  # pausa antes de tentar de novo
    return None

# Função principal assíncrona
async def main():
    # Conexão com o banco
    conn = sqlite3.connect("pokemon_dw.db")
    cursor = conn.cursor()

    # Criação das tabelas (se não existirem)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pokemon (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        height INTEGER,
        weight INTEGER,
        base_experience INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pokemon_stats (
        pokemon_id INTEGER,
        stat_name TEXT,
        base_stat INTEGER,
        PRIMARY KEY (pokemon_id, stat_name),
        FOREIGN KEY(pokemon_id) REFERENCES pokemon(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pokemon_types (
        pokemon_id INTEGER,
        type_name TEXT,
        slot INTEGER,
        PRIMARY KEY (pokemon_id, type_name),
        FOREIGN KEY(pokemon_id) REFERENCES pokemon(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pokemon_moves (
        pokemon_id INTEGER,
        move_name TEXT,
        version_group TEXT,
        learn_method TEXT,
        level_learned_at INTEGER,
        PRIMARY KEY (pokemon_id, move_name, version_group),
        FOREIGN KEY(pokemon_id) REFERENCES pokemon(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS species ( 
        pokemon_id INTEGER PRIMARY KEY,
        capture_rate INTEGER,
        is_legendary INTEGER,
        is_mythical INTEGER,
        growth_rate TEXT,
        habitat TEXT,
        color TEXT,
        FOREIGN KEY(pokemon_id) REFERENCES pokemon(id)                                                      
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evolution (
        chain_id INTEGER,
        from_species TEXT,
        to_species TEXT,
        trigger TEXT,
        min_level INTEGER,
        item TEXT,
        time_of_day TEXT,
        location TEXT,
        PRIMARY KEY (chain_id, from_species, to_species)
    )
    """)
    conn.commit()

    # Descobre quantos pokémons existem na API (requisição síncrona só para contar)
    count_url = "https://pokeapi.co/api/v2/pokemon?limit=1"
    count_data = requests.get(count_url).json()
    total_pokemons = count_data["count"]
    print(f"Total de pokémons na API: {total_pokemons}")

    # Define o tamanho do lote (quantos pokémons buscar em paralelo)
    batch_size = 20

    processed_chains = set()  # guarda cadeias de evolução já processadas

    # Estrutura assíncrona para buscar em lotes
    async with aiohttp.ClientSession() as session:
        for start in range(1, total_pokemons+1, batch_size):
            end = min(start+batch_size, total_pokemons+1)

            # Cria tarefas para buscar vários pokémons em paralelo
            tasks = [fetch_with_retry(session, f"https://pokeapi.co/api/v2/pokemon/{i}") for i in range(start, end)]
            results = await asyncio.gather(*tasks)

            # Ordena os resultados pelo ID para manter a sequência correta
            for data in sorted([r for r in results if r], key=lambda x: x["id"]):
                # Checa se já existe no banco
                cursor.execute("SELECT 1 FROM pokemon WHERE id = ?", (data["id"],))
                if cursor.fetchone():
                    print(f"Pokémon {data['id']} já está no banco, pulando...")
                    continue

                print(f"Inserindo {data['name']}...")
                progress = (data["id"] / total_pokemons) * 100
                print(f"Progresso: {progress:.2f}%")

                # Dados básicos
                cursor.execute("""
                INSERT OR REPLACE INTO pokemon (id, name, height, weight, base_experience)
                VALUES (?, ?, ?, ?, ?)
                """, (data["id"], data["name"], data["height"], data["weight"], data["base_experience"]))

                # Stats
                stats_batch = [(data["id"], stat["stat"]["name"], stat["base_stat"]) for stat in data["stats"]]
                cursor.executemany("""
                INSERT OR IGNORE INTO pokemon_stats (pokemon_id, stat_name, base_stat)
                VALUES (?, ?, ?)
                """, stats_batch)

                # Tipos
                types_batch = [(data["id"], t["type"]["name"], t["slot"]) for t in data["types"]]
                cursor.executemany("""
                INSERT OR IGNORE INTO pokemon_types (pokemon_id, type_name, slot)
                VALUES (?, ?, ?)
                """, types_batch)

                # Moves (limitados a 5)
                moves_batch = []
                for move in data["moves"][:5]:
                    moves_batch.append((
                        data["id"],
                        move["move"]["name"],
                        move["version_group_details"][0]["version_group"]["name"],
                        move["version_group_details"][0]["move_learn_method"]["name"],
                        move["version_group_details"][0]["level_learned_at"]
                    ))
                cursor.executemany("""
                INSERT OR IGNORE INTO pokemon_moves (pokemon_id, move_name, version_group, learn_method, level_learned_at)
                VALUES (?, ?, ?, ?, ?)
                """, moves_batch)

                # Species (agora com retry assíncrono)
                species_url = data["species"]["url"]
                species_data = await fetch_with_retry(session, species_url)
                if not species_data:
                    print(f"Falha ao obter species para {data['name']}, pulando...")
                    continue

                cursor.execute("""
                INSERT OR REPLACE INTO species (pokemon_id, capture_rate, is_legendary, is_mythical, growth_rate, habitat, color)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["id"],
                    species_data.get("capture_rate", 0),
                    int(species_data.get("is_legendary", False)),
                    int(species_data.get("is_mythical", False)),
                    species_data["growth_rate"]["name"] if species_data.get("growth_rate") else "",
                    species_data["habitat"]["name"] if species_data.get("habitat") else "",
                    species_data["color"]["name"] if species_data.get("color") else ""
                ))

                # Evolution (também com retry assíncrono)
                evolution_url = species_data["evolution_chain"]["url"]
                evolution_data = await fetch_with_retry(session, evolution_url)
                if not evolution_data:
                    print(f"Falha ao obter evolução para {data['name']}, pulando...")
                    continue

                chain_id = evolution_data["id"]

                if chain_id not in processed_chains:
                    processed_chains.add(chain_id)

                    def parse_chain(chain, chain_id, from_species=None):
                        current_species = chain["species"]["name"]

                        for evo in chain["evolves_to"]:
                            details = evo["evolution_details"][0] if evo["evolution_details"] else {}

                            cursor.execute("""
                            INSERT OR IGNORE INTO evolution (chain_id, from_species, to_species, trigger, min_level, item, time_of_day, location)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                chain_id,
                                from_species if from_species else current_species,
                                evo["species"]["name"],
                                details.get("trigger", {}).get("name", ""),
                                details.get("min_level", None),
                                details.get("item", {}).get("name", "") if details.get("item") else "",
                                details.get("time_of_day", ""),
                                details.get("location", {}).get("name", "") if details.get("location") else ""
                            ))

                            parse_chain(evo, chain_id, evo["species"]["name"])

                    parse_chain(evolution_data["chain"], chain_id)

            # Commit no final de cada lote
            conn.commit()
            print(f"Commit realizado até o pokémon {end-1}")

    # Consultas finais
    cursor.execute("SELECT COUNT(*) FROM pokemon")
    print(f"\nNúmero total de pokémons salvos: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM evolution")
    print(f"\nNúmero total de evoluções salvas: {cursor.fetchone()[0]}")

    conn.close()

# Executa o programa
asyncio.run(main())