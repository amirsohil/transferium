from neo4j import GraphDatabase
from dotenv import load_dotenv
import pandas as pd
import ast
import os

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

df = pd.read_csv("data/players_clean.csv")
df["positions_list"] = df["positions_list"].apply(ast.literal_eval)

print(f"Loaded {len(df)} players")

# ── Clear database ────────────────────────────────────────────────────────────
print("Clearing existing data...")
with driver.session() as session:
    session.run("MATCH (n) DETACH DELETE n")

# ── Constraints ───────────────────────────────────────────────────────────────
print("Creating constraints...")
with driver.session() as session:
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Player) REQUIRE p.id IS UNIQUE")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Club) REQUIRE c.name IS UNIQUE")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:League) REQUIRE l.name IS UNIQUE")
    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (pos:Position) REQUIRE pos.code IS UNIQUE")

# ── Leagues ───────────────────────────────────────────────────────────────────
print("Loading leagues...")
leagues = df["league_name"].dropna().unique()
with driver.session() as session:
    session.run("""
        UNWIND $leagues AS name
        MERGE (l:League {name: name})
    """, leagues=[str(l) for l in leagues])
print(f"  → {len(leagues)} leagues created")

# ── Clubs ─────────────────────────────────────────────────────────────────────
print("Loading clubs...")
clubs = df[["club_name", "league_name"]].dropna(subset=["club_name"]).drop_duplicates("club_name")
club_batch = [
    {"club": str(row["club_name"]), "league": str(row["league_name"])}
    for _, row in clubs.iterrows()
]
with driver.session() as session:
    session.run("""
        UNWIND $clubs AS c
        MERGE (club:Club {name: c.club})
        WITH club, c
        MATCH (l:League {name: c.league})
        MERGE (club)-[:IN_LEAGUE]->(l)
    """, clubs=club_batch)
print(f"  → {len(clubs)} clubs created")

# ── Positions ─────────────────────────────────────────────────────────────────
print("Loading positions...")
all_positions = set()
for positions in df["positions_list"]:
    all_positions.update([p.strip() for p in positions])
with driver.session() as session:
    session.run("""
        UNWIND $positions AS code
        MERGE (p:Position {code: code})
    """, positions=list(all_positions))
print(f"  → {len(all_positions)} positions created")

# ── Players ───────────────────────────────────────────────────────────────────
print("Loading players...")

OUTFIELD_ATTRS = [
    "attacking_crossing", "attacking_finishing", "attacking_heading_accuracy",
    "attacking_short_passing", "attacking_volleys", "skill_dribbling", "skill_curve",
    "skill_fk_accuracy", "skill_long_passing", "skill_ball_control",
    "movement_acceleration", "movement_sprint_speed", "movement_agility",
    "movement_reactions", "movement_balance", "power_shot_power", "power_jumping",
    "power_stamina", "power_strength", "power_long_shots", "mentality_aggression",
    "mentality_interceptions", "mentality_positioning", "mentality_vision",
    "mentality_penalties", "mentality_composure", "defending_marking_awareness",
    "defending_standing_tackle", "defending_sliding_tackle",
]
GK_ATTRS = [
    "goalkeeping_diving", "goalkeeping_handling", "goalkeeping_kicking",
    "goalkeeping_positioning", "goalkeeping_reflexes",
    "movement_reactions", "mentality_composure",
]

def row_to_player_dict(row):
    attrs = {}
    cols = GK_ATTRS if row["is_goalkeeper"] else OUTFIELD_ATTRS
    for col in cols:
        val = row.get(col)
        if pd.notna(val):
            attrs[col] = int(val)
    return attrs

BATCH_SIZE = 250
rows = df.to_dict("records")
total = len(rows)

with driver.session() as session:
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i+BATCH_SIZE]

        player_batch  = []
        position_rels = []
        club_rels     = []

        for row in batch:
            attrs = row_to_player_dict(row)
            props = {
                "id":               str(row["player_id"]),
                "name":             str(row["short_name"]),
                "full_name":        str(row["long_name"]),
                "age":              int(row["age"]) if pd.notna(row["age"]) else 0,
                "overall":          int(row["overall"]),
                "potential":        int(row["potential"]),
                "height_cm":        int(row["height_cm"]) if pd.notna(row["height_cm"]) else 0,
                "weight_kg":        int(row["weight_kg"]) if pd.notna(row["weight_kg"]) else 0,
                "preferred_foot":   str(row["preferred_foot"]) if pd.notna(row["preferred_foot"]) else "",
                "value_eur":        float(row["value_eur"]) if pd.notna(row["value_eur"]) else 0.0,
                "wage_eur":         float(row["wage_eur"]) if pd.notna(row["wage_eur"]) else 0.0,
                "nationality":      str(row["nationality_name"]) if pd.notna(row["nationality_name"]) else "",
                "image_url":        str(row["player_face_url"]) if pd.notna(row["player_face_url"]) else "",
                "is_goalkeeper":    bool(row["is_goalkeeper"]),
                "primary_position": str(row["primary_position"]),
                **attrs
            }
            player_batch.append(props)

            for idx, pos in enumerate(row["positions_list"]):
                position_rels.append({
                    "id":      props["id"],
                    "code":    pos.strip(),
                    "primary": (idx == 0)
                })

            if pd.notna(row["club_name"]):
                club_rels.append({
                    "id":   props["id"],
                    "club": str(row["club_name"])
                })

        # Write players
        session.run("""
            UNWIND $batch AS props
            MERGE (p:Player {id: props.id})
            SET p += props
        """, batch=player_batch)

        # Write position relationships
        session.run("""
            UNWIND $rels AS rel
            MATCH (p:Player {id: rel.id})
            MATCH (pos:Position {code: rel.code})
            MERGE (p)-[:PLAYS_AT {is_primary: rel.primary}]->(pos)
        """, rels=position_rels)

        # Write club relationships
        session.run("""
            UNWIND $rels AS rel
            MATCH (p:Player {id: rel.id})
            MATCH (c:Club {name: rel.club})
            MERGE (p)-[:PLAYS_FOR]->(c)
        """, rels=club_rels)

        print(f"  → Loaded {min(i + BATCH_SIZE, total)}/{total} players")

# ── Final count ───────────────────────────────────────────────────────────────
with driver.session() as session:
    result = session.run("""
        MATCH (p:Player) WITH count(p) AS players
        MATCH (c:Club)   WITH players, count(c) AS clubs
        MATCH (l:League) WITH players, clubs, count(l) AS leagues
        MATCH (pos:Position)
        RETURN players, clubs, leagues, count(pos) AS positions
    """)
    counts = result.single()
    print(f"\n── Graph loaded ──")
    print(f"  Players:   {counts['players']}")
    print(f"  Clubs:     {counts['clubs']}")
    print(f"  Leagues:   {counts['leagues']}")
    print(f"  Positions: {counts['positions']}")

driver.close()
print("\nDone!")