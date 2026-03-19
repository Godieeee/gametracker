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
TOKEN        = os.getenv("TOKEN")
RAWG_KEY     = os.getenv("RAWG_KEY", "")
ANNOUNCE_ID  = int(os.getenv("ANNOUNCE_CHANNEL_ID", "0"))  # Channel annonce jeu en cours
DB_FILE      = "gaming_sessions.db"

# ─── FLASK (anti-sleep) ───────────────────────────────────────────────────────
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS active_sessions (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            game TEXT NOT NULL,
            start_time TEXT NOT NULL
        )
    """)
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

# ─── RAWG ─────────────────────────────────────────────────────────────────────
async def fetch_game_info(query: str):
    try:
        url = f"https://api.rawg.io/api/games?key={RAWG_KEY}&search={query}&page_size=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        return results[0]["name"], results[0].get("background_image")
    except Exception:
        pass
    return query, None

# ─── ENREGISTREMENT PREMIÈRE FOIS ─────────────────────────────────────────────
async def register_first_play(user_id: str, username: str, game: str):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM game_info WHERE user_id = ? AND game = ?", (user_id, game))
    exists = c.fetchone()
    conn.close()
    if not exists:
        _, cover = await fetch_game_info(game)
        conn = db()
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO game_info (user_id, game, first_played, cover_url)
            VALUES (?, ?, ?, ?)
        """, (user_id, game, datetime.utcnow().isoformat(), cover))
        conn.commit()
        conn.close()

# ─── TÂCHES PLANIFIÉES ────────────────────────────────────────────────────────
async def scheduler():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.utcnow()
        if now.weekday() == 6 and now.hour == 20 and now.minute == 0:
            await send_weekly_summary()
        if now.day == 1 and now.hour == 20 and now.minute == 0:
            await send_monthly_summary()
        await asyncio.sleep(60)

async def send_weekly_summary():
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT game, SUM(duration_minutes) as total
        FROM sessions WHERE start_time >= ?
        GROUP BY game ORDER BY total DESC LIMIT 5
    """, (since,))
    rows = c.fetchall()
    c.execute("SELECT SUM(duration_minutes) FROM sessions WHERE start_time >= ?", (since,))
    total = c.fetchone()[0] or 0
    conn.close()
    if not rows:
        return
    embed = discord.Embed(title="📅 Résumé de la semaine", color=0x52B043)
    embed.add_field(name="⏱ Total", value=f"**{total/60:.1f}h**", inline=False)
    top = "\n".join(f"`{i+1}.` **{r[0]}** — {r[1]/60:.1f}h" for i, r in enumerate(rows))
    embed.add_field(name="🏆 Top jeux", value=top, inline=False)
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await channel.send(embed=embed)
                break
            except Exception:
                pass

async def send_monthly_summary():
    now        = datetime.utcnow()
    last_month = (now.replace(day=1) - timedelta(days=1))
    month_start = last_month.replace(day=1, hour=0, minute=0, second=0).isoformat()
    month_end   = now.replace(day=1, hour=0, minute=0, second=0).isoformat()
    mois_nom    = last_month.strftime("%B %Y")
    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT s.game, SUM(s.duration_minutes) as total, gi.cover_url
        FROM sessions s
        LEFT JOIN game_info gi ON gi.user_id = s.user_id AND gi.game = s.game
        WHERE s.start_time >= ? AND s.start_time < ?
        GROUP BY s.game ORDER BY total DESC LIMIT 5
    """, (month_start, month_end))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return
    top_game, top_time, cover_url = rows[0]
    total_mois = sum(r[1] for r in rows)
    embed = discord.Embed(
        title=f"📊 Résumé de {mois_nom}",
        description=f"🏆 Jeu du mois : **{top_game}** avec **{top_time/60:.1f}h** !",
        color=0x52B043
    )
    if cover_url:
        embed.set_thumbnail(url=cover_url)
    embed.add_field(name="⏱ Total", value=f"**{total_mois/60:.1f}h**", inline=True)
    embed.add_field(name="🎮 Jeux joués", value=f"**{len(rows)}**", inline=True)
    if len(rows) > 1:
        autres = "\n".join(f"`{i+2}.` **{r[0]}** — {r[1]/60:.1f}h" for i, r in enumerate(rows[1:]))
        embed.add_field(name="Autres jeux", value=autres, inline=False)
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                await channel.send(embed=embed)
                break
            except Exception:
                pass

# ─── DÉTECTION ACTIVITÉ ───────────────────────────────────────────────────────
@bot.event
async def on_ready():
    init_db()
    await tree.sync()
    bot.loop.create_task(scheduler())
    print(f"✅ Bot connecté : {bot.user}")
    print("📡 Surveillance des activités activée")

@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    user_id  = str(after.id)
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

        if ANNOUNCE_ID:
            channel = bot.get_channel(ANNOUNCE_ID)
            if channel:
                conn2 = db()
                c2 = conn2.cursor()
                c2.execute("SELECT cover_url FROM game_info WHERE user_id = ? AND game = ?", (user_id, game))
                info = c2.fetchone()
                conn2.close()
                embed = discord.Embed(
                    title="🎮 En train de jouer",
                    description=f"**{username}** vient de lancer **{game}** !",
                    color=0x52B043
                )
                if info and info[0]:
                    embed.set_thumbnail(url=info[0])
                embed.timestamp = datetime.utcnow()
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

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
    target  = membre or interaction.user
    user_id = str(target.id)
    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT s.game, SUM(s.duration_minutes) as total, gi.first_played, gi.cover_url
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

    embed = discord.Embed(title=f"🎮 Stats de {target.display_name}", color=0x52B043)
    if rows and rows[0][3]:
        embed.set_thumbnail(url=rows[0][3])
    if active:
        game, start_str = active
        elapsed = (datetime.utcnow() - datetime.fromisoformat(start_str)).total_seconds() / 60
        embed.add_field(name="🟢 En train de jouer", value=f"**{game}** — {elapsed:.0f} min", inline=False)
    if rows:
        total_all = sum(r[1] for r in rows)
        embed.add_field(name="⏱ Temps total", value=f"**{total_all/60:.1f}h**", inline=True)
        embed.add_field(name="🎯 Jeux différents", value=f"**{len(rows)}**", inline=True)
        top_lines = []
        for i, (game, total, first_played, _) in enumerate(rows[:8]):
            first = f" *(depuis le {datetime.fromisoformat(first_played).strftime('%d/%m/%Y')})*" if first_played else ""
            top_lines.append(f"`{i+1}.` **{game}** — {total/60:.1f}h{first}")
        embed.add_field(name="🏆 Top jeux", value="\n".join(top_lines), inline=False)
    await interaction.response.send_message(embed=embed)

# ─── /jeu ─────────────────────────────────────────────────────────────────────
@tree.command(name="jeu", description="Détails sur un jeu spécifique")
@app_commands.describe(nom="Nom du jeu", membre="Membre (laisse vide = toi)")
async def jeu(interaction: discord.Interaction, nom: str, membre: discord.Member = None):
    target  = membre or interaction.user
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
    game_name    = info[0] if info else nom
    first_played = info[1] if info else None
    cover_url    = info[2] if info else None
    embed = discord.Embed(title=f"🎮 {game_name}", color=0x52B043)
    if cover_url:
        embed.set_image(url=cover_url)
    embed.add_field(name="⏱ Temps total", value=f"**{total_min/60:.1f}h** ({total_min:.0f} min)", inline=True)
    embed.add_field(name="🔁 Sessions", value=f"**{nb_sessions}**", inline=True)
    if first_played:
        embed.add_field(name="🆕 Première fois", value=f"**{datetime.fromisoformat(first_played).strftime('%d/%m/%Y à %H:%M')}**", inline=False)
    await interaction.response.send_message(embed=embed)

# ─── /ajouter_jeu ─────────────────────────────────────────────────────────────
@tree.command(name="ajouter_jeu", description="Ajoute un jeu manuellement à ta liste")
@app_commands.describe(nom="Nom du jeu (approximatif OK)")
async def ajouter_jeu(interaction: discord.Interaction, nom: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    game_name, cover_url = await fetch_game_info(nom)
    conn = db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM game_info WHERE user_id = ? AND LOWER(game) = LOWER(?)", (user_id, game_name))
    exists = c.fetchone()
    conn.close()
    if exists:
        await interaction.followup.send(f"⚠️ **{game_name}** est déjà dans ta liste !", ephemeral=True)
        return
    conn = db()
    c = conn.cursor()
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

# ─── /ajouter_heures (avec confirmation) ──────────────────────────────────────
class ConfirmView(discord.ui.View):
    def __init__(self, user_id, username, game_name, cover_url, minutes):
        super().__init__(timeout=30)
        self.user_id   = user_id
        self.username  = username
        self.game_name = game_name
        self.cover_url = cover_url
        self.minutes   = minutes

    @discord.ui.button(label="✅ Oui c'est ça !", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = datetime.utcnow().isoformat()
        conn = db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO sessions (user_id, username, game, start_time, end_time, duration_minutes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (self.user_id, self.username, self.game_name, now, now, self.minutes))
        conn.commit()
        c.execute("SELECT SUM(duration_minutes) FROM sessions WHERE user_id = ? AND game = ?", (self.user_id, self.game_name))
        total = c.fetchone()[0] or 0
        conn.close()
        embed = discord.Embed(
            title="✅ Heures ajoutées !",
            description=f"**+{self.minutes/60:.1f}h** ajoutées à **{self.game_name}**",
            color=0x52B043
        )
        if self.cover_url:
            embed.set_thumbnail(url=self.cover_url)
        embed.add_field(name="⏱ Total maintenant", value=f"**{total/60:.1f}h**")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ Non mauvais jeu", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Annulé",
            description="Aucune heure ajoutée. Réessaie avec un nom plus précis.",
            color=0xFF0000
        )
        await interaction.response.edit_message(embed=embed, view=None)

@tree.command(name="ajouter_heures", description="Ajoute des heures manuellement à un jeu")
@app_commands.describe(jeu="Nom du jeu", heures="Nombre d'heures à ajouter (ex: 40)")
async def ajouter_heures(interaction: discord.Interaction, jeu: str, heures: float):
    await interaction.response.defer()
    user_id  = str(interaction.user.id)
    username = interaction.user.display_name
    if heures <= 0 or heures > 10000:
        await interaction.followup.send("❌ Nombre d'heures invalide.", ephemeral=True)
        return
    minutes = heures * 60
    conn = db()
    c = conn.cursor()
    c.execute("SELECT game, cover_url FROM game_info WHERE user_id = ? AND LOWER(game) LIKE LOWER(?)", (user_id, f"%{jeu}%"))
    info = c.fetchone()
    conn.close()
    if info:
        game_name, cover_url = info
    else:
        conn = db()
        c = conn.cursor()
        c.execute("SELECT DISTINCT game FROM sessions WHERE user_id = ? AND LOWER(game) LIKE LOWER(?)", (user_id, f"%{jeu}%"))
        row = c.fetchone()
        conn.close()
        if row:
            game_name = row[0]
            cover_url = None
        else:
            game_name, cover_url = await fetch_game_info(jeu)
            conn = db()
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO game_info (user_id, game, first_played, cover_url)
                VALUES (?, ?, ?, ?)
            """, (user_id, game_name, datetime.utcnow().isoformat(), cover_url))
            conn.commit()
            conn.close()
    embed = discord.Embed(
        title="❓ Confirmation",
        description=f"Tu veux ajouter **{heures}h** à ce jeu ?\n\n🎮 **{game_name}**",
        color=0xFFA500
    )
    if cover_url:
        embed.set_thumbnail(url=cover_url)
    view = ConfirmView(user_id, username, game_name, cover_url, minutes)
    await interaction.followup.send(embed=embed, view=view)

# ─── /supprimer_jeu ───────────────────────────────────────────────────────────
class ConfirmDeleteView(discord.ui.View):
    def __init__(self, user_id, game_name):
        super().__init__(timeout=30)
        self.user_id   = user_id
        self.game_name = game_name

    @discord.ui.button(label="✅ Oui supprimer", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db()
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE user_id = ? AND game = ?", (self.user_id, self.game_name))
        c.execute("DELETE FROM game_info WHERE user_id = ? AND game = ?", (self.user_id, self.game_name))
        c.execute("DELETE FROM active_sessions WHERE user_id = ? AND game = ?", (self.user_id, self.game_name))
        conn.commit()
        conn.close()
        embed = discord.Embed(
            title="🗑️ Jeu supprimé",
            description=f"**{self.game_name}** et toutes ses heures ont été supprimés.",
            color=0xFF0000
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="❌ Annulé", description="Aucune suppression effectuée.", color=0x888888)
        await interaction.response.edit_message(embed=embed, view=None)

@tree.command(name="supprimer_jeu", description="Supprime un jeu et toutes ses heures")
@app_commands.describe(nom="Nom du jeu à supprimer")
async def supprimer_jeu(interaction: discord.Interaction, nom: str):
    user_id = str(interaction.user.id)
    conn = db()
    c = conn.cursor()
    c.execute("SELECT game FROM game_info WHERE user_id = ? AND LOWER(game) LIKE LOWER(?)", (user_id, f"%{nom}%"))
    info = c.fetchone()
    if not info:
        c.execute("SELECT DISTINCT game FROM sessions WHERE user_id = ? AND LOWER(game) LIKE LOWER(?)", (user_id, f"%{nom}%"))
        info = c.fetchone()
    conn.close()
    if not info:
        await interaction.response.send_message(f"❌ Aucun jeu trouvé pour **{nom}**.", ephemeral=True)
        return
    game_name = info[0]
    embed = discord.Embed(
        title="⚠️ Confirmation suppression",
        description=f"Tu veux vraiment supprimer **{game_name}** et **toutes ses heures** ?",
        color=0xFF0000
    )
    view = ConfirmDeleteView(user_id, game_name)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ─── LANCEMENT ────────────────────────────────────────────────────────────────
import import_games
bot.run(TOKEN)

