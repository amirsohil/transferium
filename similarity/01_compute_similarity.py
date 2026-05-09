import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
from neo4j import GraphDatabase
from dotenv import load_dotenv
from tqdm import tqdm
import os

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

df = pd.read_csv("data/players_clean.csv")
print(f"Loaded {len(df)} players")

# ─────────────────────────────────────────────────────────────────────────────
# LEARN: Weighted attribute groups
# Rather than treating all 29 attributes equally, we assign weights
# by football role. A CDM's interceptions matter more than their finishing.
# We'll multiply each attribute by its group weight before computing similarity.
# ─────────────────────────────────────────────────────────────────────────────

OUTFIELD_ATTRS = {
    # Technical (35%)
    "attacking_crossing":          0.35 / 7,
    "attacking_finishing":         0.35 / 7,
    "attacking_short_passing":     0.35 / 7,
    "skill_long_passing":          0.35 / 7,
    "skill_ball_control":          0.35 / 7,
    "skill_dribbling":             0.35 / 7,
    "mentality_vision":            0.35 / 7,
    # Physical (25%)
    "movement_acceleration":       0.25 / 6,
    "movement_sprint_speed":       0.25 / 6,
    "power_stamina":               0.25 / 6,
    "power_strength":              0.25 / 6,
    "movement_agility":            0.25 / 6,
    "power_jumping":               0.25 / 6,
    # Tactical (30%)
    "mentality_positioning":       0.30 / 5,
    "defending_marking_awareness": 0.30 / 5,
    "mentality_interceptions":     0.30 / 5,
    "defending_standing_tackle":   0.30 / 5,
    "movement_reactions":          0.30 / 5,
    # League/region handled separately (10%)
}

GK_ATTRS = {
    "goalkeeping_diving":      0.20,
    "goalkeeping_handling":    0.20,
    "goalkeeping_kicking":     0.10,
    "goalkeeping_positioning": 0.20,
    "goalkeeping_reflexes":    0.20,
    "movement_reactions":      0.05,
    "mentality_composure":     0.05,
}

# ─────────────────────────────────────────────────────────────────────────────
# LEARN: League region grouping
# We give a small similarity bonus (10%) when two players share a league
# or are in the same regional football family. This reflects how clubs
# scout — they prefer players already adapted to a similar style/culture.
# ─────────────────────────────────────────────────────────────────────────────

LEAGUE_REGIONS = {
    "Premier League":          "UK",
    "Championship":            "UK",
    "League One":              "UK",
    "Scottish Premiership":    "UK",
    "La Liga":                 "Iberian",
    "Liga Portugal":           "Iberian",
    "Serie A":                 "Italian",
    "Serie B":                 "Italian",
    "Bundesliga":              "German",
    "2. Bundesliga":           "German",
    "Ligue 1":                 "French",
    "Ligue 2":                 "French",
    "Eredivisie":              "Benelux",
    "Jupiler Pro League":      "Benelux",
    "MLS":                     "Americas",
    "Liga MX":                 "Americas",
    "Brasileirão":             "Americas",
    "Argentine Primera":       "Americas",
}

def get_region(league):
    if pd.isna(league):
        return "Other"
    return LEAGUE_REGIONS.get(str(league), "Other")

df["region"] = df["league_name"].apply(get_region)

def league_bonus(league_a, league_b, region_a, region_b):
    """Returns a bonus between 0 and 0.10 based on league/region similarity."""
    if pd.notna(league_a) and pd.notna(league_b) and league_a == league_b:
        return 0.10   # same league
    if region_a == region_b and region_a != "Other":
        return 0.05   # same region
    return 0.0

# ─────────────────────────────────────────────────────────────────────────────
# LEARN: Cosine similarity
# We represent each player as a vector of weighted attribute scores (0-100).
# Cosine similarity measures the angle between two vectors — 1.0 means
# identical profile, 0.0 means nothing in common.
# It's better than Euclidean distance here because a 70-rated player
# with balanced stats is more "similar" to an 85-rated balanced player
# than to a 90-rated specialist in one area.
# ─────────────────────────────────────────────────────────────────────────────

def build_vector(row, attr_weights):
    return np.array([row[attr] * weight for attr, weight in attr_weights.items()])

# ── Split outfield and GK ─────────────────────────────────────────────────────
df_out = df[~df["is_goalkeeper"]].copy().reset_index(drop=True)
df_gk  = df[ df["is_goalkeeper"]].copy().reset_index(drop=True)

# ── Build matrices ────────────────────────────────────────────────────────────
print("Building outfield vectors...")
out_attrs = list(OUTFIELD_ATTRS.keys())
out_matrix = np.array([build_vector(row, OUTFIELD_ATTRS) for _, row in df_out[out_attrs].iterrows()])

print("Building GK vectors...")
gk_attrs = list(GK_ATTRS.keys())
gk_matrix = np.array([build_vector(row, GK_ATTRS) for _, row in df_gk[gk_attrs].iterrows()])

# ── Compute full similarity matrices ──────────────────────────────────────────
print("Computing outfield similarity matrix...")
out_sim = cosine_similarity(out_matrix)  # shape: (n_outfield, n_outfield)

print("Computing GK similarity matrix...")
gk_sim = cosine_similarity(gk_matrix)   # shape: (n_gk, n_gk)

# ─────────────────────────────────────────────────────────────────────────────
# LEARN: Position matching
# A CM is not a valid replacement for a ST, even if their stats are similar.
# We parse each player's positions_list and only create SIMILAR_TO edges
# when the two players share at least one position.
# Primary position match gets a 0.03 score boost.
# ─────────────────────────────────────────────────────────────────────────────

import ast
df_out["positions_list"] = df_out["positions_list"].apply(
    lambda x: ast.literal_eval(x) if isinstance(x, str) else x
)
df_gk["positions_list"] = df_gk["positions_list"].apply(
    lambda x: ast.literal_eval(x) if isinstance(x, str) else x
)

def positions_overlap(pos_list_a, pos_list_b):
    set_a = set([p.strip() for p in pos_list_a])
    set_b = set([p.strip() for p in pos_list_b])
    return set_a & set_b  # intersection

TOP_K = 15  # store top 15 similar players per player

def extract_top_similar(sim_matrix, df_subset, top_k=TOP_K):
    """For each player, find top_k most similar players with position overlap."""
    results = []
    n = len(df_subset)

    for i in tqdm(range(n)):
        player_a = df_subset.iloc[i]
        scores = sim_matrix[i].copy()
        scores[i] = -1  # exclude self

        # Sort descending
        sorted_idx = np.argsort(scores)[::-1]

        count = 0
        for j in sorted_idx:
            if count >= top_k:
                break

            player_b = df_subset.iloc[j]

            # Must share at least one position
            overlap = positions_overlap(player_a["positions_list"], player_b["positions_list"])
            if not overlap:
                continue

            base_score = float(scores[j])

            # Primary position boost
            pos_boost = 0.03 if player_a["primary_position"] == player_b["primary_position"] else 0.0

            # League/region bonus (weighted at 10%)
            l_bonus = league_bonus(
                player_a["league_name"], player_b["league_name"],
                player_a["region"],      player_b["region"]
            )

            # Penalise large overall rating gaps
            # A 17-point gap (90 vs 73) should significantly reduce the score
            overall_diff = abs(int(player_a["overall"]) - int(player_b["overall"]))
            overall_penalty = min(overall_diff * 0.015, 0.30)  # max 30% penalty

            final_score = min(base_score * 0.90 + l_bonus + pos_boost - overall_penalty, 1.0)

            results.append({
                "id_a":     str(player_a["player_id"]),
                "id_b":     str(player_b["player_id"]),
                "score":    round(final_score, 4),
                "pos_match": player_a["primary_position"] == player_b["primary_position"],
                "same_league": player_a["league_name"] == player_b["league_name"],
            })
            count += 1

    return results

print("\nExtracting top similar outfield players...")
outfield_edges = extract_top_similar(out_sim, df_out)

print("\nExtracting top similar GKs...")
gk_edges = extract_top_similar(gk_sim, df_gk)

all_edges = outfield_edges + gk_edges
print(f"\nTotal SIMILAR_TO edges to write: {len(all_edges)}")

# ── Write edges to Neo4j ──────────────────────────────────────────────────────
print("Writing SIMILAR_TO edges to Neo4j...")

BATCH_SIZE = 1000
with driver.session() as session:
    # Clear existing similarity edges first
    session.run("MATCH ()-[r:SIMILAR_TO]->() DELETE r")

    for i in tqdm(range(0, len(all_edges), BATCH_SIZE)):
        batch = all_edges[i:i+BATCH_SIZE]
        session.run("""
            UNWIND $edges AS edge
            MATCH (a:Player {id: edge.id_a})
            MATCH (b:Player {id: edge.id_b})
            MERGE (a)-[r:SIMILAR_TO]->(b)
            SET r.score      = edge.score,
                r.pos_match  = edge.pos_match,
                r.same_league = edge.same_league
        """, edges=batch)

# ── Verify ────────────────────────────────────────────────────────────────────
with driver.session() as session:
    count = session.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS total").single()["total"]
    print(f"\n── SIMILAR_TO edges in graph: {count}")

    print("\n── Sample: Top replacements for Jude Bellingham ──")
    result = session.run("""
        MATCH (p:Player)
        WHERE p.full_name = "Jude Victor William Bellingham"
        MATCH (p)-[r:SIMILAR_TO]->(s:Player)
        RETURN s.name, s.overall, r.score, r.pos_match
        ORDER BY r.score DESC
        LIMIT 5
    """)
    for row in result:
        print(f"  {row['s.name']:25s} | Overall: {row['s.overall']} | Score: {row['r.score']} | Same pos: {row['r.pos_match']}")

driver.close()
print("\nSimilarity engine complete!")