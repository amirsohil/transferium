import pandas as pd
import numpy as np
import os

# ── Load ─────────────────────────────────────────────────────────────────────
df = pd.read_csv("data/players_raw.csv", low_memory=False)
print(f"Raw shape: {df.shape}")

# ── Parse positions ───────────────────────────────────────────────────────────
df["positions_list"]   = df["player_positions"].str.split(", ")
df["primary_position"] = df["positions_list"].str[0].str.strip()
df["is_goalkeeper"]    = df["primary_position"] == "GK"

# ── Clean name ────────────────────────────────────────────────────────────────
df["short_name"] = df["short_name"].str.strip()
df["long_name"]  = df["long_name"].str.strip()

# ── Attribute column definitions ──────────────────────────────────────────────
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

# ── Convert attributes to numeric ─────────────────────────────────────────────
all_attrs = list(set(OUTFIELD_ATTRS + GK_ATTRS))
for col in all_attrs:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# ── Split outfield vs GK ──────────────────────────────────────────────────────
df_outfield = df[~df["is_goalkeeper"]].copy()
df_gk       = df[ df["is_goalkeeper"]].copy()

df_outfield = df_outfield.dropna(subset=OUTFIELD_ATTRS, thresh=len(OUTFIELD_ATTRS) - 3)
df_gk       = df_gk.dropna(subset=GK_ATTRS, thresh=len(GK_ATTRS) - 1)

df_clean = pd.concat([df_outfield, df_gk], ignore_index=True)
print(f"After cleaning: {df_clean.shape}")

# ── Select final columns ──────────────────────────────────────────────────────
KEEP_COLS = [
    "player_id", "short_name", "long_name", "age", "dob",
    "height_cm", "weight_kg", "overall", "potential",
    "preferred_foot", "weak_foot", "skill_moves", "international_reputation",
    "body_type", "value_eur", "wage_eur", "release_clause_eur",
    "club_name", "league_name", "nationality_name",
    "primary_position", "positions_list", "is_goalkeeper",
    "player_face_url",
] + OUTFIELD_ATTRS + GK_ATTRS

df_clean = df_clean[[c for c in KEEP_COLS if c in df_clean.columns]]

# ── Save ──────────────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
df_clean.to_csv("data/players_clean.csv", index=False)
print(f"Saved: data/players_clean.csv — {df_clean.shape[0]} players, {df_clean.shape[1]} columns")

# ── Sanity checks ─────────────────────────────────────────────────────────────
print("\n── Position breakdown (top 15) ──")
print(df_clean["primary_position"].value_counts().head(15))
print(f"\n── GK count:      {df_clean['is_goalkeeper'].sum()}")
print(f"── Outfield count: {(~df_clean['is_goalkeeper']).sum()}")
print(f"\n── Overall range: {df_clean['overall'].min()} → {df_clean['overall'].max()}")
print(f"── Age range:     {df_clean['age'].min()} → {df_clean['age'].max()}")
print(f"\n── Value EUR sample: {df_clean['value_eur'].dropna().head(3).tolist()}")
print("\n── Remaining nulls in attributes:")
null_counts = df_clean[OUTFIELD_ATTRS].isnull().sum()
print(null_counts[null_counts > 0] if null_counts.any() else "  None — clean!")