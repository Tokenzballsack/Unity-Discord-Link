#     _____     _                  _   _     _       _    
#    |_   _|__ | | _____ _ __  ___( ) | |   (_)_ __ | | __
#      | |/ _ \| |/ / _ \ '_ \|_  //  | |   | | '_ \| |/ /
#      | | (_) |   <  __/ | | |/ /    | |___| | | | |   < 
#      |_|\___/|_|\_\___|_| |_/___|   |_____|_|_| |_|_|\_\

import discord
from discord import app_commands
import aiohttp, os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN  = os.getenv("DISCORD_TOKEN") # put ya discord token here
API_BASE       = os.getenv("API_BASE", "http://localhost:8000")
STAFF_SECRET   = os.getenv("STAFF_SECRET", "change-me-in-production")
STAFF_ROLE_ID  = int(os.getenv("STAFF_ROLE_ID", "0"))  # staff role ID (the role of members that can edit people roles in game)

intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)

COLOUR_MAP = {
    "grey":   "#808080",
    "gray":   "#808080",
    "red":    "#FF4444",
    "green":  "#44FF44",
    "blue":   "#4444FF",
    "gold":   "#FFD700",
    "purple": "#9B59B6",
    "orange": "#FF8C00",
    "white":  "#FFFFFF",
}

def resolve_colour(value: str) -> str:
    """Accept colour names or #hex values."""
    v = value.strip().lower()
    if v in COLOUR_MAP:
        return COLOUR_MAP[v]
    if v.startswith("#") and len(v) in (4, 7):
        return v.upper()
    return "#808080"

def label_to_discord_colour(hex_colour: str) -> discord.Colour:
    try:
        return discord.Colour(int(hex_colour.lstrip("#"), 16))
    except Exception:
        return discord.Colour.greyple()

@tree.command(name="link", description="Link your in-game account using the code shown in game.")
@app_commands.describe(code="the 8-character code displayed in game")
async def link(interaction: discord.Interaction, code: str):
    await interaction.response.defer(ephemeral=True)

    payload = {
        "code": code.upper().strip(),
        "discord_id": str(interaction.user.id),
        "discord_name": str(interaction.user.name)
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/link", json=payload) as resp:
            data = await resp.json()
            if resp.status == 200:
                embed = discord.Embed(
                    title="[GAME NAME] Account Linked!",
                    description=data["message"],
                    colour=discord.Colour.green()
                )
                embed.add_field(name="Status", value="MEMBER", inline=True)
                embed.add_field(name="Colour", value="Grey", inline=True)
                await interaction.followup.send(embed=embed, ephemeral=True)
            elif resp.status == 409:
                await interaction.followup.send("your Discord account is already linked.", ephemeral=True)
            elif resp.status == 404:
                await interaction.followup.send("that code is invalid or has expired. Generate a new one.", ephemeral=True)
            else:
                await interaction.followup.send(f"Something went wrong: {data.get('detail', 'Unknown error')}", ephemeral=True)

@tree.command(name="mystatus", description="Check your link status.")
async def mystatus(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/lookup-discord/{interaction.user.id}") as resp:
            if resp.status == 404:
                await interaction.followup.send("You don't have a linked game account yet. Use `/link <code>`", ephemeral=True)
                return
            data = await resp.json()

    embed = discord.Embed(
        title="Your Linked Account",
        colour=label_to_discord_colour(data["colour"])
    )
    embed.add_field(name="Status Label", value=data["label"], inline=True)
    embed.add_field(name="Colour",       value=data["colour"], inline=True)
    embed.add_field(name="Linked Since", value=data["linked_at"][:10], inline=True)
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.command(name="setstatus", description="[Staff] Set a linked player's in-game status label and colour.")
@app_commands.describe(
    discord_name="The player's Discord username (without #tag)",
    label="New status label e.g. ADMIN, VIP, BANNED",
    colour="Colour name (red/green/blue/gold/purple/grey/orange/white) or #hex"
)
async def setstatus(interaction: discord.Interaction, discord_name: str, label: str, colour: str = "grey"):
    await interaction.response.defer(ephemeral=True)

    staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
    if staff_role not in interaction.user.roles:
        await interaction.followup.send("❌ You don't have permission to use this command.", ephemeral=True)
        return

    resolved_colour = resolve_colour(colour)

    payload = {
        "discord_name": discord_name,
        "label": label.upper(),
        "colour": resolved_colour
    }

    async with aiohttp.ClientSession() as session:
        async with session.patch(
            f"{API_BASE}/set-status",
            json=payload,
            headers={"x-staff-secret": STAFF_SECRET}
        ) as resp:
            data = await resp.json()
            if resp.status == 200:
                embed = discord.Embed(
                    title="✅ Status Updated",
                    colour=label_to_discord_colour(resolved_colour)
                )
                embed.add_field(name="Player",    value=discord_name,      inline=True)
                embed.add_field(name="New Label", value=label.upper(),     inline=True)
                embed.add_field(name="Colour",    value=resolved_colour,   inline=True)
                embed.set_footer(text=f"Updated by {interaction.user.name}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            elif resp.status == 404:
                await interaction.followup.send(f"❌ No linked player found with Discord name `{discord_name}`.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {data.get('detail', 'Unknown error')}", ephemeral=True)

@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot ready as {client.user} — slash commands synced.")


client.run(DISCORD_TOKEN)
