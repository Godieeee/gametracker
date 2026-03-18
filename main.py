# ─── IMPORTS ──────────────────────────────────────────────────────────────────
import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
import os
from flask import Flask
from threading import Thread

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TOKEN = "TON_TOKEN_ICI"           # Token de ton bot Discord
RAWG_KEY = "TA_CLE_RAWG_ICI"     # Clé API RAWG (gratuite sur rawg.io/apidocs)
DB_FILE = "gaming_sessions.db"

# ─── FLASK (anti-sleep Replit) ────────────────────────────────────────────────
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot Game Tracker en ligne !"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()

# ─── SETUP BOT ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ─── BASE DE DONNÉES ──────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Sessions terminées
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            game TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_minutes REAL DEFAULT 0
        )
    """)

    # Sessions en cours
    c.execute("""
        CREATE TABLE IF NOT EXISTS active_sessions (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            game TEXT NOT NULL,
            start_time TEXT NOT NULL
        )
    """)

    # Infos jeux (cover + première fois)
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_info (
            user_id TEXT NOT NULL,
            game TEXT NOT NULL,
            first_played TEXT NOT NULL,
            cover_url TEXT,
            PRIMARY KEY (user_id, game)
        )
    """)

    conn.commit()
    conn.close()

def db():
    return sqlite3.connect(DB_FILE)

# ─── SCRAPING COVER (RAWG) ────────────────────────────────────────────────────
async def fetch_cover(game_name: str) -> str | None:
    """Récupère la cover d'un jeu via l'API RAWG (gratuite)."""
    try:
        url = f"https://api.rawg.io/api/games?key={RAWG_KEY}&search={game_name}&page_size=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        return results[0].get("background_image")
    except Exception:
        pass
    return None

# ─── ENREGISTREMENT PREMIÈRE FOIS + COVER ─────────────────────────────────────
async def register_first_play(user_id: str, username: str, game: str):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM game_info WHERE user_id = ? AND game = ?", (user_id, game))
    exists = c.fetchone()
    conn.close()

    if not exists:
        cover = await fetch_cover(game)
        conn = db()
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO game_info (user_id, game, first_played, cover_url)
            VALUES (?, ?, ?, ?)
        """, (user_id, game, datetime.utcnow().isoformat(), cover))
        conn.commit()
        conn.close()
        print(f"🆕 Première fois : {username} joue à {game} | Cover: {'✅' if cover else '❌'}")

# ─── DÉTECTION ACTIVITÉ ───────────────────────────────────────────────────────
@bot.event
async def on_ready():
    init_db()
    await tree.sync()
    print(f"✅ Bot connecté : {bot.user}")
    print("📡 Surveillance des activités activée")

@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    user_id = str(after.id)
    username = after.display_name

    before_games = {a.name for a in before.activities if isinstance(a, (discord.Game, discord.Activity))}
    after_games  = {a.name for a in after.activities  if isinstance(a, (discord.Game, discord.Activity))}

    started = after_games - before_games
    stopped = before_games - after_games

    conn = db()
    c = conn.cursor()

    for game in started:
        c.execute("""
            INSERT OR REPLACE INTO active_sessions (user_id, username, game, start_time)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, game, datetime.utcnow().isoformat()))
        print(f"🎮 {username} lance {game}")
        asyncio.ensure_future(register_first_play(user_id, username, game))

    for game in stopped:
        c.execute("SELECT start_time FROM active_sessions WHERE user_id = ? AND game = ?", (user_id, game))
        row = c.fetchone()
        if row:
            start    = datetime.fromisoformat(row[0])
            end      = datetime.utcnow()
            duration = (end - start).total_seconds() / 60

            c.execute("""
                INSERT INTO sessions (user_id, username, game, start_time, end_time, duration_minutes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, game, row[0], end.isoformat(), duration))
            c.execute("DELETE FROM active_sessions WHERE user_id = ? AND game = ?", (user_id, game))
            print(f"⏹ {username} quitte {game} après {duration:.1f} min")

    conn.commit()
    conn.close()

# ─── /stats ───────────────────────────────────────────────────────────────────
@tree.command(name="stats", description="Tes statistiques de jeu")
@app_commands.describe(membre="Membre (laisse vide = toi)")
async def stats(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    user_id = str(target.id)

    conn = db()
    c = conn.cursor()

    c.execute("""
        SELECT s.game, SUM(s.duration_minutes) as total,
               gi.first_played, gi.cover_url
        FROM sessions s
        LEFT JOIN game_info gi ON gi.user_id = s.user_id AND gi.game = s.game
        WHERE s.user_id = ?
        GROUP BY s.game ORDER BY total DESC
    """, (user_id,))
    rows = c.fetchall()

    c.execute("SELECT game, start_time FROM active_sessions WHERE user_id = ?", (user_id,))
    active = c.fetchone()
    conn.close()

    if not rows and not active:
        await interaction.response.send_message(f"❌ Aucune session pour **{target.display_name}**.", ephemeral=True)
        return

    # Prend la cover du jeu le plus joué
    cover_url = None
    top_game = None
    if rows:
        top_game = rows[0][0]
        cover_url = rows[0][3]

    embed = discord.Embed(title=f"🎮 Stats de {target.display_name}", color=0x52B043)

    if cover_url:
        embed.set_thumbnail(url=cover_url)

    if active:
        game, start_str = active
        elapsed = (datetime.utcnow() - datetime.fromisoformat(start_str)).total_seconds() / 60
        embed.add_field(name="🟢 En train de jouer", value=f"**{game}** — {elapsed:.0f} min", inline=False)

    if rows:
        total_all = sum(r[1] for r in rows)
        embed.add_field(name="⏱ Temps total", value=f"**{total_all/60:.1f}h**", inline=True)
        embed.add_field(name="🎯 Jeux différents", value=f"**{len(rows)}**", inline=True)

        top_lines = []
        for i, (game, total, first_played, _) in enumerate(rows[:6]):
            first = ""
            if first_played:
                d = datetime.fromisoformat(first_played).strftime("%d/%m/%Y")
                first = f" *(depuis le {d})*"
            top_lines.append(f"`{i+1}.` **{game}** — {total/60:.1f}h{first}")

        embed.add_field(name="🏆 Top jeux", value="\n".join(top_lines), inline=False)

    await interaction.response.send_message(embed=embed)

# ─── /jeu ─────────────────────────────────────────────────────────────────────
@tree.command(name="jeu", description="Détails sur un jeu spécifique")
@app_commands.describe(nom="Nom du jeu", membre="Membre (laisse vide = toi)")
async def jeu(interaction: discord.Interaction, nom: str, membre: discord.Member = None):
    target = membre or interaction.user
    user_id = str(target.id)

    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT SUM(duration_minutes), COUNT(*) FROM sessions
        WHERE user_id = ? AND LOWER(game) LIKE LOWER(?)
    """, (user_id, f"%{nom}%"))
    row = c.fetchone()

    c.execute("""
        SELECT game, first_played, cover_url FROM game_info
        WHERE user_id = ? AND LOWER(game) LIKE LOWER(?)
    """, (user_id, f"%{nom}%"))
    info = c.fetchone()
    conn.close()

    if not row or not row[0]:
        await interaction.response.send_message(f"❌ Aucune session trouvée pour **{nom}**.", ephemeral=True)
        return

    total_min, nb_sessions = row
    game_name = info[0] if info else nom
    first_played = info[1] if info else None
    cover_url = info[2] if info else None

    embed = discord.Embed(title=f"🎮 {game_name}", color=0x52B043)
    if cover_url:
        embed.set_image(url=cover_url)

    embed.add_field(name="⏱ Temps total", value=f"**{total_min/60:.1f}h** ({total_min:.0f} min)", inline=True)
    embed.add_field(name="🔁 Sessions", value=f"**{nb_sessions}**", inline=True)
    if first_played:
        d = datetime.fromisoformat(first_played).strftime("%d/%m/%Y à %H:%M")
        embed.add_field(name="🆕 Première fois", value=f"**{d}**", inline=False)

    await interaction.response.send_message(embed=embed)

# ─── /mois ────────────────────────────────────────────────────────────────────
@tree.command(name="mois", description="Jeu le plus joué ce mois + résumé mensuel")
@app_commands.describe(membre="Membre (laisse vide = toi)")
async def mois(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    user_id = str(target.id)

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0).isoformat()

    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT s.game, SUM(s.duration_minutes) as total, gi.cover_url
        FROM sessions s
        LEFT JOIN game_info gi ON gi.user_id = s.user_id AND gi.game = s.game
        WHERE s.user_id = ? AND s.start_time >= ?
        GROUP BY s.game ORDER BY total DESC
    """, (user_id, month_start))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("❌ Aucune session ce mois-ci.", ephemeral=True)
        return

    mois_nom = now.strftime("%B %Y")
    top_game, top_time, cover_url = rows[0]
    total_mois = sum(r[1] for r in rows)

    embed = discord.Embed(
        title=f"📊 Résumé de {mois_nom}",
        description=f"🏆 Jeu du mois : **{top_game}** avec **{top_time/60:.1f}h** !",
        color=0x52B043
    )
    if cover_url:
        embed.set_thumbnail(url=cover_url)

    embed.add_field(name="⏱ Total ce mois", value=f"**{total_mois/60:.1f}h**", inline=True)
    embed.add_field(name="🎯 Jeux joués", value=f"**{len(rows)}**", inline=True)

    if len(rows) > 1:
        autres = "\n".join(f"`{i+2}.` **{r[0]}** — {r[1]/60:.1f}h" for i, r in enumerate(rows[1:5]))
        embed.add_field(name="Autres jeux", value=autres, inline=False)

    await interaction.response.send_message(embed=embed)

# ─── /semaine ─────────────────────────────────────────────────────────────────
@tree.command(name="semaine", description="Graphique de ta semaine de jeu")
@app_commands.describe(membre="Membre (laisse vide = toi)")
async def semaine(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    user_id = str(target.id)

    conn = db()
    c = conn.cursor()
    days_data = []
    for i in range(6, -1, -1):
        day = datetime.utcnow() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0).isoformat()
        day_end   = day.replace(hour=23, minute=59, second=59).isoformat()
        c.execute("""
            SELECT SUM(duration_minutes) FROM sessions
            WHERE user_id = ? AND start_time >= ? AND start_time <= ?
        """, (user_id, day_start, day_end))
        total = c.fetchone()[0] or 0
        days_data.append((day.strftime("%a %d/%m"), total))
    conn.close()

    max_val = max(d[1] for d in days_data) or 1
    bars = []
    for day_name, minutes in days_data:
        bar_len = int((minutes / max_val) * 12)
        bar = "█" * bar_len + "░" * (12 - bar_len)
        bars.append(f"`{day_name}` {bar} **{minutes/60:.1f}h**")

    embed = discord.Embed(title=f"📅 Semaine de {target.display_name}", color=0x52B043)
    embed.description = "\n".join(bars)
    total_week = sum(d[1] for d in days_data)
    embed.set_footer(text=f"Total semaine : {total_week/60:.1f}h")

    await interaction.response.send_message(embed=embed)

# ─── /historique ──────────────────────────────────────────────────────────────
@tree.command(name="historique", description="Tes dernières sessions")
@app_commands.describe(jours="Nombre de jours (défaut: 7)", membre="Membre (laisse vide = toi)")
async def historique(interaction: discord.Interaction, jours: int = 7, membre: discord.Member = None):
    target = membre or interaction.user
    user_id = str(target.id)
    since = (datetime.utcnow() - timedelta(days=jours)).isoformat()

    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT game, start_time, duration_minutes FROM sessions
        WHERE user_id = ? AND start_time >= ?
        ORDER BY start_time DESC LIMIT 15
    """, (user_id, since))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message(f"❌ Aucune session dans les {jours} derniers jours.", ephemeral=True)
        return

    lines = []
    for game, start_str, duration in rows:
        date_str = datetime.fromisoformat(start_str).strftime("%d/%m %H:%M")
        lines.append(f"`{date_str}` **{game}** — {duration/60:.1f}h")

    embed = discord.Embed(title=f"📅 Historique {jours}j — {target.display_name}", color=0x52B043)
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Total : {sum(r[2] for r in rows)/60:.1f}h")

    await interaction.response.send_message(embed=embed)

# ─── /top ─────────────────────────────────────────────────────────────────────
@tree.command(name="top", description="Classement des joueurs du serveur")
async def top(interaction: discord.Interaction):
    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT username, SUM(duration_minutes) as total
        FROM sessions GROUP BY user_id ORDER BY total DESC LIMIT 10
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("❌ Aucune donnée.", ephemeral=True)
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (u, t) in enumerate(rows):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        lines.append(f"{medal} **{u}** — {t/60:.1f}h")
    embed = discord.Embed(title="🏆 Top joueurs du serveur", description="\n".join(lines), color=0x52B043)
    await interaction.response.send_message(embed=embed)

# ─── /ajouter_jeu ─────────────────────────────────────────────────────────────
@tree.command(name="ajouter_jeu", description="Ajoute un jeu manuellement à ta liste")
@app_commands.describe(nom="Nom du jeu (approximatif OK)")
async def ajouter_jeu(interaction: discord.Interaction, nom: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    rawg_key = os.getenv("RAWG_KEY", "")
    game_name = nom
    cover_url = None

    try:
        url = f"https://api.rawg.io/api/games?key={rawg_key}&search={nom}&page_size=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        game_name = results[0]["name"]
                        cover_url = results[0].get("background_image")
    except Exception:
        pass

    conn = db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM game_info WHERE user_id = ? AND LOWER(game) = LOWER(?)", (user_id, game_name))
    exists = c.fetchone()

    if exists:
        conn.close()
        await interaction.followup.send(f"⚠️ **{game_name}** est déjà dans ta liste !", ephemeral=True)
        return

    c.execute("""
        INSERT OR IGNORE INTO game_info (user_id, game, first_played, cover_url)
        VALUES (?, ?, ?, ?)
    """, (user_id, game_name, datetime.utcnow().isoformat(), cover_url))
    conn.commit()
    conn.close()

    embed = discord.Embed(title="✅ Jeu ajouté !", description=f"**{game_name}** a été ajouté à ta liste.", color=0x52B043)
    if cover_url:
        embed.set_thumbnail(url=cover_url)
    embed.set_footer(text="Utilise /ajouter_heures pour ajouter tes heures existantes")
    await interaction.followup.send(embed=embed)

# ─── /ajouter_heures ──────────────────────────────────────────────────────────
@tree.command(name="ajouter_heures", description="Ajoute des heures manuellement à un jeu")
@app_commands.describe(jeu="Nom du jeu", heures="Nombre d'heures à ajouter (ex: 40)")
async def ajouter_heures(interaction: discord.Interaction, jeu: str, heures: float):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    username = interaction.user.display_name

    if heures <= 0 or heures > 10000:
        await interaction.followup.send("❌ Nombre d'heures invalide.", ephemeral=True)
        return

    minutes = heures * 60
    rawg_key = os.getenv("RAWG_KEY", "")

    # Cherche le jeu dans game_info
    conn = db()
    c = conn.cursor()
    c.execute("SELECT game, cover_url FROM game_info WHERE user_id = ? AND LOWER(game) LIKE LOWER(?)", (user_id, f"%{jeu}%"))
    info = c.fetchone()
    conn.close()

    if info:
        game_name, cover_url = info
    else:
        # Cherche dans les sessions existantes
        conn = db()
        c = conn.cursor()
        c.execute("SELECT DISTINCT game FROM sessions WHERE user_id = ? AND LOWER(game) LIKE LOWER(?)", (user_id, f"%{jeu}%"))
        row = c.fetchone()
        conn.close()

        if row:
            game_name = row[0]
            cover_url = None
        else:
            # Jeu inconnu : cherche sur RAWG et crée l'entrée
            game_name = jeu
            cover_url = None
            try:
                url = f"https://api.rawg.io/api/games?key={rawg_key}&search={jeu}&page_size=1"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("results", [])
                            if results:
                                game_name = results[0]["name"]
                                cover_url = results[0].get("background_image")
            except Exception:
                pass

            conn = db()
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO game_info (user_id, game, first_played, cover_url)
                VALUES (?, ?, ?, ?)
            """, (user_id, game_name, datetime.utcnow().isoformat(), cover_url))
            conn.commit()
            conn.close()

    # Ajoute la session manuelle
    now = datetime.utcnow().isoformat()
    conn = db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO sessions (user_id, username, game, start_time, end_time, duration_minutes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username, game_name, now, now, minutes))
    conn.commit()
    c.execute("SELECT SUM(duration_minutes) FROM sessions WHERE user_id = ? AND game = ?", (user_id, game_name))
    total = c.fetchone()[0] or 0
    conn.close()

    embed = discord.Embed(title="✅ Heures ajoutées !", description=f"**+{heures}h** ajoutées à **{game_name}**", color=0x52B043)
    if cover_url:
        embed.set_thumbnail(url=cover_url)
    embed.add_field(name="⏱ Total maintenant", value=f"**{total/60:.1f}h**", inline=True)
    await interaction.followup.send(embed=embed)

# ─── LANCEMENT ────────────────────────────────────────────────────────────────
bot.run(TOKEN)
