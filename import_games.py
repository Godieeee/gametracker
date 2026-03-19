import sqlite3

# ─── TON USER ID DISCORD ──────────────────────────────────────────────────────
# Pour trouver ton ID : Discord > Paramètres > Avancé > active Mode développeur
# Puis clic droit sur ton pseudo > Copier l'identifiant
USER_ID  = "276789457917575178"
USERNAME = "Amineeeee"
DB_FILE  = "gaming_sessions.db"

# ─── TES JEUX (nom, heures, date_debut, date_fin) ────────────────────────────
games = [
    ("EA SPORTS FC 24", 304.0, "2024-08-19T00:00:00", "2025-04-11T00:00:00"),
    ("EA SPORTS FC 25", 93.4, "2025-06-11T00:00:00", "2025-09-29T00:00:00"),
    ("The Witcher 3: Wild Hunt - Complete Edition", 90.7, "2024-10-17T00:00:00", "2024-11-24T00:00:00"),
    ("Kingdom Come: Deliverance II", 89.0, "2026-03-03T00:00:00", "2026-03-16T00:00:00"),
    ("Minecraft", 83.6, "2024-11-08T00:00:00", "2025-12-28T00:00:00"),
    ("Clair Obscur: Expedition 33", 80.3, "2025-04-24T00:00:00", "2025-05-23T00:00:00"),
    ("Minecraft (Windows)", 73.2, "2024-12-28T00:00:00", "2024-12-28T00:00:00"),
    ("Yakuza: Like a Dragon", 70.8, "2025-01-08T00:00:00", "2025-02-23T00:00:00"),
    ("Balatro", 67.6, "2025-02-26T00:00:00", "2025-04-18T00:00:00"),
    ("ELDEN RING", 59.7, "2024-11-28T00:00:00", "2025-02-12T00:00:00"),
    ("INAZUMA ELEVEN: Victory Road", 46.6, "2025-11-24T00:00:00", "2025-12-22T00:00:00"),
    ("Cyberpunk 2077", 45.2, "2024-11-07T00:00:00", "2025-09-16T00:00:00"),
    ("Fallout 4", 40.2, "2024-08-20T00:00:00", "2024-09-10T00:00:00"),
    ("Vampire Survivors", 39.1, "2024-12-22T00:00:00", "2026-03-12T00:00:00"),
    ("FIFA 22 (Xbox One)", 38.2, "2022-05-12T00:00:00", "2022-12-26T00:00:00"),
    ("DEATH STRANDING DIRECTOR'S CUT", 38.2, "2026-01-21T00:00:00", "2026-02-04T00:00:00"),
    ("Grand Theft Auto V (Xbox One)", 38.0, "2024-10-13T00:00:00", "2024-10-24T00:00:00"),
    ("EA SPORTS FC 26", 35.4, "2025-12-22T00:00:00", "2026-01-04T00:00:00"),
    ("Dragon Ball Xenoverse 2", 30.2, "2025-02-28T00:00:00", "2025-03-06T00:00:00"),
    ("Brotato", 26.7, "2025-07-15T00:00:00", "2025-08-06T00:00:00"),
    ("Marvel Rivals", 26.5, "2024-12-16T00:00:00", "2025-01-12T00:00:00"),
    ("The Elder Scrolls V: Skyrim Special Edition", 24.3, "2024-09-14T00:00:00", "2024-09-14T00:00:00"),
    ("Grand Theft Auto V", 22.2, "2025-04-16T00:00:00", "2025-08-14T00:00:00"),
    ("Inscryption", 21.8, "2024-12-20T00:00:00", "2025-07-23T00:00:00"),
    ("The Sims 4", 21.8, "2025-09-07T00:00:00", "2025-09-07T00:00:00"),
    ("Split Fiction", 20.5, "2025-04-05T00:00:00", "2025-07-12T00:00:00"),
    ("Indiana Jones and the Great Circle", 16.7, "2024-12-22T00:00:00", "2024-12-26T00:00:00"),
    ("Yakuza 0", 15.7, "2025-02-23T00:00:00", "2026-01-28T00:00:00"),
    ("F1 24", 14.6, "2025-08-06T00:00:00", "2025-08-08T00:00:00"),
    ("Like a Dragon: Infinite Wealth", 13.4, "2025-12-15T00:00:00", "2025-12-16T00:00:00"),
    ("Dead Cells", 12.0, "2024-11-13T00:00:00", "2025-08-26T00:00:00"),
    ("The Elder Scrolls IV: Oblivion Remastered", 11.7, "2025-04-22T00:00:00", "2025-04-24T00:00:00"),
    ("TCG Card Shop Simulator", 10.1, "2026-02-24T00:00:00", "2026-02-25T00:00:00"),
    ("The Alters", 9.1, "2025-06-15T00:00:00", "2025-06-23T00:00:00"),
    ("Mortal Kombat 1", 9.0, "2026-02-28T00:00:00", "2026-03-02T00:00:00"),
    ("Call of Duty", 8.7, "2024-12-19T00:00:00", "2024-12-19T00:00:00"),
    ("Tekken 8", 8.1, "2025-03-06T00:00:00", "2026-01-21T00:00:00"),
    ("Phoenix Wright: Ace Attorney Trilogy", 7.6, "2024-09-12T00:00:00", "2024-09-17T00:00:00"),
    ("Minecraft (iOS)", 7.4, "2020-12-11T00:00:00", "2021-03-12T00:00:00"),
    ("Resident Evil 2", 7.3, "2024-08-20T00:00:00", "2026-02-14T00:00:00"),
    ("A Way Out", 7.1, "2025-08-05T00:00:00", "2025-08-05T00:00:00"),
    ("Dark Souls: Remastered", 6.3, "2025-01-08T00:00:00", "2025-01-08T00:00:00"),
    ("Hollow Knight: Silksong", 5.7, "2025-12-26T00:00:00", "2025-12-29T00:00:00"),
    ("LEGO Star Wars: The Skywalker Saga", 5.0, "2024-09-03T00:00:00", "2024-09-06T00:00:00"),
    ("Firewatch", 4.5, "2025-12-30T00:00:00", "2026-01-02T00:00:00"),
    ("Street Fighter 6", 4.5, "2025-03-01T00:00:00", "2025-10-08T00:00:00"),
    ("VALORANT", 4.5, "2025-08-05T00:00:00", "2025-08-05T00:00:00"),
    ("Overcooked! 2", 4.5, "2024-12-29T00:00:00", "2025-07-07T00:00:00"),
    ("Assassin's Creed Shadows", 4.4, "2025-03-24T00:00:00", "2025-03-29T00:00:00"),
    ("ROBLOX", 4.3, "2021-10-14T00:00:00", "2021-10-14T00:00:00"),
    ("Medieval Dynasty", 4.2, "2024-09-18T00:00:00", "2024-09-20T00:00:00"),
    ("Unravel Two", 3.9, "2024-11-07T00:00:00", "2024-11-07T00:00:00"),
    ("Forza Horizon 5", 3.8, "2024-09-09T00:00:00", "2024-09-30T00:00:00"),
    ("Mortal Kombat 11", 3.7, "2025-07-19T00:00:00", "2025-07-19T00:00:00"),
    ("The Rogue Prince of Persia", 3.7, "2025-08-20T00:00:00", "2025-08-23T00:00:00"),
    ("PlateUp!", 3.6, "2025-07-22T00:00:00", "2025-07-26T00:00:00"),
    ("Human Fall Flat", 3.6, "2024-09-04T00:00:00", "2025-08-03T00:00:00"),
    ("BALL x PIT", 3.5, "2025-12-19T00:00:00", "2025-12-28T00:00:00"),
    ("A Game About Digging A Hole", 3.4, "2026-01-21T00:00:00", "2026-01-21T00:00:00"),
]

# ─── IMPORT ───────────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
imported = 0
skipped  = 0

for game_name, hours, start_time, end_time in games:
    minutes = hours * 60

    # Vérifie si déjà importé
    c.execute("SELECT SUM(duration_minutes) FROM sessions WHERE user_id = ? AND game = ?", (USER_ID, game_name))
    existing = c.fetchone()[0] or 0
    if existing > 0:
        print(f"⏭ Ignoré (déjà {existing/60:.1f}h) : {game_name}")
        skipped += 1
        continue

    # Ajoute la session avec les vraies dates
    c.execute("""
        INSERT INTO sessions (user_id, username, game, start_time, end_time, duration_minutes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (USER_ID, USERNAME, game_name, start_time, end_time, minutes))

    # Ajoute dans game_info
    c.execute("""
        INSERT OR IGNORE INTO game_info (user_id, game, first_played, cover_url)
        VALUES (?, ?, ?, NULL)
    """, (USER_ID, game_name, start_time))

    print(f"✅ {game_name} ({hours}h) — {start_time[:10]} → {end_time[:10]}")
    imported += 1

conn.commit()
conn.close()
print(f"\n🎮 Import terminé ! {imported} jeux importés, {skipped} ignorés.")
