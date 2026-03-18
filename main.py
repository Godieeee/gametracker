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
    lines = [
        f"{medals[i] if i < 3 else f'`{i+1}.'}`} **{u}** — {t/60:.1f}h"
        for i, (u, t) in enumerate(rows)
    ]
    embed = discord.Embed(title="🏆 Top joueurs du serveur", description="\n".join(lines), color=0x52B043)
    await interaction.response.send_message(embed=embed)
 
# ─── LANCEMENT ────────────────────────────────────────────────────────────────
bot.run(TOKEN)
