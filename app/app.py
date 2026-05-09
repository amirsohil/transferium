import streamlit as st
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import pandas as pd

load_dotenv()

st.set_page_config(
    page_title="Transferium · Player Intelligence",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Neo4j connection ──────────────────────────────────────────────────────────
@st.cache_resource
def get_driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )

driver = get_driver()

# ── Data fetchers ─────────────────────────────────────────────────────────────
@st.cache_data
def get_all_players():
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            RETURN p.id AS id, p.name AS name, p.full_name AS full_name,
                   p.overall AS overall, p.primary_position AS position,
                   p.age AS age, p.nationality AS nationality
            ORDER BY p.overall DESC
        """)
        return pd.DataFrame([dict(r) for r in result])

def get_player_details(player_id):
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player {id: $id})
            RETURN p
        """, id=player_id)
        row = result.single()
        if row:
            return dict(row["p"])
        return None

def get_replacements(player_id, min_overall, max_overall, top_n):
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player {id: $id})-[r:SIMILAR_TO]->(s:Player)
            WHERE s.overall >= $min_overall AND s.overall <= $max_overall
            RETURN s.id AS id, s.name AS name, s.full_name AS full_name,
                   s.overall AS overall, s.age AS age,
                   s.primary_position AS position,
                   s.nationality AS nationality,
                   r.score AS score,
                   r.pos_match AS pos_match
            ORDER BY r.score DESC
            LIMIT $top_n
        """, id=player_id, min_overall=min_overall,
             max_overall=max_overall, top_n=top_n)
        return pd.DataFrame([dict(r) for r in result])

# ── Helpers ───────────────────────────────────────────────────────────────────
def score_tier(score):
    if score >= 0.88:
        return ("ELITE", "#C9F31D", "#0d1a00")
    elif score >= 0.78:
        return ("STRONG", "#00E5FF", "#001a1f")
    elif score >= 0.68:
        return ("GOOD", "#FF9500", "#1f1200")
    else:
        return ("FAIR", "#8A8A9A", "#0e0e12")

def overall_color(ovr):
    if ovr >= 88: return "#C9F31D"
    elif ovr >= 82: return "#00E5FF"
    elif ovr >= 75: return "#FF9500"
    else: return "#8A8A9A"

def position_abbr(pos):
    return pos if pos else "?"

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;600&display=swap');

/* ── Reset Streamlit chrome ── */
#MainMenu, footer { visibility: hidden; }
header { background: transparent !important; }
header > div { visibility: hidden; }
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[kind="header"],
header button {
    visibility: visible !important;
    color: #C9F31D !important;
    background: transparent !important;
    z-index: 999 !important;
}
.block-container { padding: 0 !important; max-width: 100% !important; }
.stApp { background: #080C12 !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0B0F18 !important;
    border-right: 1px solid rgba(201,243,29,0.12) !important;
    padding: 0 !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }

/* Sidebar inputs */
[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(201,243,29,0.2) !important;
    border-radius: 8px !important;
    color: #E8EAF0 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
}
[data-testid="stSidebar"] .stTextInput input:focus {
    border-color: rgba(201,243,29,0.6) !important;
    box-shadow: 0 0 0 3px rgba(201,243,29,0.08) !important;
}
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(201,243,29,0.2) !important;
    border-radius: 8px !important;
    color: #E8EAF0 !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown p {
    color: #6B7280 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}

/* Slider */
[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="slider"] {
    background: #C9F31D !important;
    border-color: #C9F31D !important;
}
[data-testid="stSidebar"] .stSlider [data-testid="stTickBar"] {
    color: #4B5563 !important;
}

/* Divider */
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.06) !important;
    margin: 16px 0 !important;
}

/* Main area scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(201,243,29,0.2); border-radius: 4px; }

/* ── Custom components ── */
.scoutiq-logo {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.6rem;
    letter-spacing: 0.12em;
    color: #C9F31D;
    line-height: 1;
    padding: 28px 24px 4px 24px;
    display: block;
}
.scoutiq-sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.68rem;
    color: #4B5563;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 0 24px 20px 24px;
    display: block;
}
.sidebar-section-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.65rem;
    color: #4B5563;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 0 24px;
    margin-bottom: 10px;
    display: block;
}
.sidebar-footer {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #2D3748;
    padding: 20px 24px;
    border-top: 1px solid rgba(255,255,255,0.04);
    margin-top: 24px;
    letter-spacing: 0.06em;
}

/* ── Main topbar ── */
.topbar {
    background: linear-gradient(180deg, #0B0F18 0%, rgba(11,15,24,0) 100%);
    padding: 28px 48px 0 48px;
    display: flex;
    align-items: flex-end;
    gap: 16px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    padding-bottom: 20px;
    margin-bottom: 32px;
}
.topbar-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2.8rem;
    letter-spacing: 0.08em;
    color: #F0F2F8;
    line-height: 1;
}
.topbar-accent {
    color: #C9F31D;
}
.topbar-subtitle {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.82rem;
    color: #4B5563;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.breadcrumb {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #374151;
    letter-spacing: 0.06em;
    padding: 0 48px;
    margin-bottom: 32px;
}
.breadcrumb span { color: #C9F31D; }

/* ── Hero player card ── */
.hero-wrap {
    padding: 0 48px;
    margin-bottom: 36px;
}
.hero-card {
    background: linear-gradient(135deg, #0F1724 0%, #111827 50%, #0D1520 100%);
    border: 1px solid rgba(201,243,29,0.18);
    border-radius: 20px;
    padding: 32px 36px;
    position: relative;
    overflow: hidden;
}
.hero-card::before {
    content: '';
    position: absolute;
    top: -80px; right: -80px;
    width: 260px; height: 260px;
    background: radial-gradient(circle, rgba(201,243,29,0.07) 0%, transparent 70%);
    pointer-events: none;
}
.hero-card::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(201,243,29,0.3), transparent);
}
.hero-position-bg {
    position: absolute;
    right: 36px; top: 50%;
    transform: translateY(-50%);
    font-family: 'Bebas Neue', sans-serif;
    font-size: 9rem;
    color: rgba(255,255,255,0.025);
    letter-spacing: 0.04em;
    line-height: 1;
    pointer-events: none;
    user-select: none;
}
.hero-overall {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 4.5rem;
    line-height: 1;
    letter-spacing: 0.02em;
}
.hero-name {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2.2rem;
    letter-spacing: 0.06em;
    color: #F0F2F8;
    line-height: 1;
    margin-bottom: 6px;
}
.hero-meta-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 14px;
}
.hero-pill {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.75rem;
    font-weight: 500;
    color: #9CA3AF;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 100px;
    padding: 4px 14px;
    letter-spacing: 0.04em;
}
.hero-stat-grid {
    display: flex;
    gap: 28px;
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.hero-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.hero-stat-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.62rem;
    color: #4B5563;
    text-transform: uppercase;
    letter-spacing: 0.12em;
}
.hero-stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.05rem;
    font-weight: 600;
    color: #E8EAF0;
}

/* ── Methodology note ── */
.method-wrap {
    padding: 0 48px;
    margin-bottom: 32px;
}
.method-card {
    background: rgba(201,243,29,0.03);
    border: 1px solid rgba(201,243,29,0.08);
    border-radius: 10px;
    padding: 14px 20px;
    display: flex;
    align-items: flex-start;
    gap: 14px;
}
.method-icon {
    font-size: 1.1rem;
    margin-top: 1px;
    flex-shrink: 0;
}
.method-text {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.8rem;
    color: #6B7280;
    line-height: 1.55;
}
.method-text b { color: #9CA3AF; font-weight: 500; }

/* ── Section header ── */
.section-header-wrap {
    padding: 0 48px;
    margin-bottom: 20px;
    display: flex;
    align-items: baseline;
    gap: 12px;
}
.section-header-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.4rem;
    letter-spacing: 0.1em;
    color: #F0F2F8;
}
.section-header-count {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #C9F31D;
    background: rgba(201,243,29,0.08);
    border: 1px solid rgba(201,243,29,0.15);
    border-radius: 6px;
    padding: 2px 8px;
}
.section-header-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, rgba(255,255,255,0.06) 0%, transparent 100%);
}

/* ── Replacement cards ── */
.cards-wrap {
    padding: 0 48px 48px 48px;
}
.rep-card {
    background: #0D1320;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 20px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s, background 0.2s;
    cursor: default;
}
.rep-card:hover {
    border-color: rgba(201,243,29,0.22);
    background: #0F1624;
}
.rep-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    border-radius: 3px 0 0 3px;
}
.rep-card.tier-elite::before { background: #C9F31D; }
.rep-card.tier-strong::before { background: #00E5FF; }
.rep-card.tier-good::before { background: #FF9500; }
.rep-card.tier-fair::before { background: #4B5563; }

/* Rank number */
.rep-rank {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #374151;
    font-weight: 600;
    letter-spacing: 0.04em;
    width: 24px;
    text-align: center;
    flex-shrink: 0;
}

/* Score ring */
.score-ring-wrap {
    flex-shrink: 0;
    position: relative;
    width: 56px;
    height: 56px;
}
.score-ring-wrap svg { position: absolute; top: 0; left: 0; }
.score-ring-center {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
.score-ring-pct {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1;
}
.score-ring-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.46rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 1px;
}

/* Overall badge */
.rep-overall {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2rem;
    line-height: 1;
    flex-shrink: 0;
    width: 42px;
    text-align: center;
}

/* Player info */
.rep-info { flex: 1; min-width: 0; }
.rep-name {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.0rem;
    font-weight: 600;
    color: #E8EAF0;
    white-space: normal;
    word-break: break-word;
    margin-bottom: 6px;
}
.rep-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
}
.rep-tag {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.7rem;
    color: #6B7280;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
    padding: 2px 9px;
}
.rep-tag.highlight {
    color: #C9F31D;
    background: rgba(201,243,29,0.06);
    border-color: rgba(201,243,29,0.15);
}

/* Tier badge */
.tier-badge {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    border-radius: 6px;
    padding: 4px 10px;
    flex-shrink: 0;
}

/* ── Empty state ── */
.empty-state {
    padding: 64px 48px;
    text-align: center;
    font-family: 'DM Sans', sans-serif;
    color: #374151;
    font-size: 0.9rem;
}
.empty-state .icon { font-size: 2.5rem; margin-bottom: 12px; }

/* ── Footer ── */
.app-footer {
    border-top: 1px solid rgba(255,255,255,0.04);
    padding: 20px 48px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.footer-left {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #1F2937;
    letter-spacing: 0.06em;
}
.footer-right {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.65rem;
    color: #1F2937;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
</style>
""", unsafe_allow_html=True)

# ── Load all players ──────────────────────────────────────────────────────────
all_players = get_all_players()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<span class='scoutiq-logo'>Transferium</span>", unsafe_allow_html=True)
    st.markdown("<span class='scoutiq-sub'>Player Intelligence · FC 26 · Sep 2025 Snapshot</span>", unsafe_allow_html=True)

    st.markdown("<span class='sidebar-section-label'>Search Player</span>", unsafe_allow_html=True)
    search_query = st.text_input("", placeholder="Bellingham, Salah, Mbappé…", label_visibility="collapsed")

    if search_query:
        mask = (
            all_players["name"].str.contains(search_query, case=False, na=False) |
            all_players["full_name"].str.contains(search_query, case=False, na=False)
        )
        filtered = all_players[mask]
    else:
        filtered = all_players

    if filtered.empty:
        st.markdown("<div class='empty-state'><div class='icon'>🔍</div>No players found.</div>", unsafe_allow_html=True)
        st.stop()

    options = filtered.apply(
        lambda r: f"{r['full_name']}  [{r['position']} · {r['overall']}]", axis=1
    ).tolist()
    player_ids = filtered["id"].tolist()

    st.markdown("<span class='sidebar-section-label' style='margin-top:12px;display:block;'>Select Player</span>", unsafe_allow_html=True)
    selected_label = st.selectbox("", options, index=0, label_visibility="collapsed")
    selected_id = player_ids[options.index(selected_label)]

    st.markdown("---")
    st.markdown("<span class='sidebar-section-label'>Filter Replacements</span>", unsafe_allow_html=True)
    min_overall, max_overall = st.slider("Overall Rating Range", 47, 99, (70, 91))
    top_n = st.slider("Max Results", 3, 20, 8)

    st.markdown(
        "<div class='sidebar-footer'>DATA: FC 26 · SOFIFA<br>GRAPH: NEO4J · APP: STREAMLIT</div>",
        unsafe_allow_html=True
    )

# ── Fetch data ────────────────────────────────────────────────────────────────
player = get_player_details(selected_id)
replacements = get_replacements(selected_id, min_overall, max_overall, top_n)

# ── Topbar ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='topbar'>
    <div>
        <div class='topbar-subtitle'>Similarity Engine</div>
        <div class='topbar-title'>PLAYER <span class='topbar-accent'>REPLACEMENT</span> FINDER</div>
    </div>
</div>
""", unsafe_allow_html=True)

if player:
    pname = player.get('full_name', player.get('name',''))
    st.markdown(
        f"<div class='breadcrumb'>ALL PLAYERS → <span>{pname.upper()}</span> → REPLACEMENTS</div>",
        unsafe_allow_html=True
    )

# ── Hero Card ─────────────────────────────────────────────────────────────────
if player:
    ovr = player.get('overall', 0)
    ovr_color = overall_color(ovr)
    pos = player.get('primary_position', '?')
    age = player.get('age', '?')
    nat = player.get('nationality', '?')
    pname = player.get('full_name', player.get('name', ''))

    st.markdown(f"""
    <div class='hero-wrap'>
        <div class='hero-card'>
            <div class='hero-position-bg'>{pos}</div>
            <div style='display:flex;align-items:center;gap:24px;'>
                <div class='hero-overall' style='color:{ovr_color};'>{ovr}</div>
                <div>
                    <div class='hero-name'>{pname}</div>
                    <div class='hero-meta-row'>
                        <span class='hero-pill'>📍 {pos}</span>
                        <span class='hero-pill'>🌍 {nat}</span>
                        <span class='hero-pill'>🎂 Age {age}</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Methodology ───────────────────────────────────────────────────────────────
st.markdown("""
<div class='method-wrap'>
    <div class='method-card'>
        <div class='method-icon'>⚡</div>
        <div class='method-text'>
            Replacements are ranked using <b>weighted skill vectors</b> across technical, physical,
            and tactical attributes. A contextual bonus is applied for players in the same league or region,
            reflecting real-world scouting patterns. Club and league are not hard filters, keeping results
            <b>globally unbiased</b>.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Results section ───────────────────────────────────────────────────────────
n_results = len(replacements)
st.markdown(f"""
<div class='section-header-wrap'>
    <div class='section-header-title'>TOP REPLACEMENTS</div>
    <div class='section-header-count'>{n_results} FOUND</div>
    <div class='section-header-line'></div>
</div>
""", unsafe_allow_html=True)

if replacements.empty:
    st.markdown("""
    <div class='empty-state'>
        <div class='icon'>🔍</div>
        No replacements found. Try widening the overall rating range.
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("<div class='cards-wrap'>", unsafe_allow_html=True)

    for i, r in enumerate(replacements.itertuples(), 1):
        score = r.score
        score_pct = int(score * 100)
        tier_label, tier_color, tier_bg = score_tier(score)
        tier_css = tier_label.lower()
        ovr = r.overall
        ovr_color = overall_color(ovr)
        pos = r.position
        nat = r.nationality if r.nationality else "?"
        age = r.age
        pos_match = r.pos_match

        # SVG score ring
        radius = 22
        circumference = 2 * 3.14159 * radius
        dash = circumference * score
        gap = circumference - dash

        tags_html = f"<span class='rep-tag'>{pos}</span>"
        tags_html += f"<span class='rep-tag'>{nat}</span>"
        tags_html += f"<span class='rep-tag'>Age {age}</span>"
        if pos_match:
            tags_html += "<span class='rep-tag highlight'>&#10003; Same Position</span>"

        full_name_safe = str(r.full_name)
        rank_str = f"#{i:02d}"
        dash_str = f"{dash:.1f}"
        gap_str = f"{gap:.1f}"

        st.markdown(
            f"<div class='rep-card tier-{tier_css}'>"
            f"<div class='rep-rank'>{rank_str}</div>"
            f"<div class='score-ring-wrap'>"
            f"<svg width='56' height='56' viewBox='0 0 56 56'>"
            f"<circle cx='28' cy='28' r='{radius}' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='4'/>"
            f"<circle cx='28' cy='28' r='{radius}' fill='none' stroke='{tier_color}' stroke-width='4' "
            f"stroke-dasharray='{dash_str} {gap_str}' stroke-linecap='round' transform='rotate(-90 28 28)'/>"
            f"</svg>"
            f"<div class='score-ring-center'>"
            f"<div class='score-ring-pct' style='color:{tier_color};'>{score_pct}</div>"
            f"<div class='score-ring-label' style='color:{tier_color};opacity:0.7;'>%</div>"
            f"</div></div>"
            f"<div class='rep-overall' style='color:{ovr_color};'>{ovr}</div>"
            f"<div class='rep-info'>"
            f"<div class='rep-name'>{full_name_safe}</div>"
            f"<div class='rep-tags'>{tags_html}</div>"
            f"</div>"
            f"<div class='tier-badge' style='color:{tier_color};background:{tier_bg};border:1px solid {tier_color}22;'>"
            f"{tier_label}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='app-footer'>
    <div class='footer-left'>© TRANSFERIUM PLAYER INTELLIGENCE · BUILT BY MOHAMED AMIR SOHIL BISHRUL HAFI</div>
    <div class='footer-right'>Data: FC 26 · SoFIFA · Graph: Neo4j</div>
</div>
""", unsafe_allow_html=True)