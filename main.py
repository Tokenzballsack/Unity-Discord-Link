from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
import os, secrets, string
from datetime import datetime

app = FastAPI(title="Unity-Discord Linker API")

# ── MongoDB ──────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
STAFF_SECRET = os.getenv("STAFF_SECRET", "change-me-in-production")

client = AsyncIOMotorClient(MONGO_URI)
db = client["unity_discord"]
players_col = db["players"]
codes_col    = db["pending_codes"]

# ── Helpers ──────────────────────────────────────────────────────────────────
def generate_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

# ── Models ───────────────────────────────────────────────────────────────────
class GenerateCodeRequest(BaseModel):
    game_player_id: str          # unique ID from Unity (e.g. Steam ID, GUID)

class LinkRequest(BaseModel):
    code: str
    discord_id: str
    discord_name: str

class StatusUpdateRequest(BaseModel):
    discord_name: str            # staff targets player by Discord name
    label: str                   # e.g. "ADMIN", "VIP", "BANNED"
    colour: str                  # hex string, e.g. "#FF0000"

# ─────────────────────────────────────────────────────────────────────────────
# UNITY ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/generate-code")
async def generate_link_code(req: GenerateCodeRequest):
    """
    Unity calls this when a player opens the linking screen.
    Returns a fresh 8-character code (or the existing one if not yet used).
    """
    # Reuse existing pending code if one already exists for this player
    existing = await codes_col.find_one({"game_player_id": req.game_player_id})
    if existing:
        return {"code": existing["code"]}

    code = generate_code()
    # Ensure uniqueness
    while await codes_col.find_one({"code": code}):
        code = generate_code()

    await codes_col.insert_one({
        "code": code,
        "game_player_id": req.game_player_id,
        "created_at": datetime.utcnow()
    })
    return {"code": code}


@app.get("/player-status/{game_player_id}")
async def get_player_status(game_player_id: str):
    """
    Unity polls this to get the player's current label & colour.
    Returns link status so Unity knows whether to show the code or the label.
    """
    player = await players_col.find_one({"game_player_id": game_player_id})
    if not player:
        # Check if a pending code exists (i.e. not yet linked)
        pending = await codes_col.find_one({"game_player_id": game_player_id})
        return {
            "linked": False,
            "has_pending_code": pending is not None,
            "label": None,
            "colour": None,
            "discord_name": None
        }

    return {
        "linked": True,
        "has_pending_code": False,
        "label": player.get("label", "MEMBER"),
        "colour": player.get("colour", "#808080"),
        "discord_name": player.get("discord_name")
    }

# ─────────────────────────────────────────────────────────────────────────────
# DISCORD BOT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/link")
async def link_player(req: LinkRequest):
    """
    Discord bot calls this when a user runs /link <code>.
    Validates the code, creates the player record, removes the pending code.
    """
    pending = await codes_col.find_one({"code": req.code.upper()})
    if not pending:
        raise HTTPException(status_code=404, detail="Invalid or expired code.")

    # Check this Discord account isn't already linked to another player
    already = await players_col.find_one({"discord_id": req.discord_id})
    if already:
        raise HTTPException(status_code=409, detail="Your Discord is already linked to a game account.")

    await players_col.insert_one({
        "game_player_id": pending["game_player_id"],
        "discord_id": req.discord_id,
        "discord_name": req.discord_name,
        "label": "MEMBER",
        "colour": "#808080",
        "linked_at": datetime.utcnow()
    })

    await codes_col.delete_one({"code": req.code.upper()})
    return {"success": True, "message": f"Linked! Your in-game status is now **MEMBER**."}


@app.patch("/set-status")
async def set_player_status(req: StatusUpdateRequest, x_staff_secret: str = Header(...)):
    """
    Discord bot calls this when a staff member runs /setstatus <user> <label> <colour>.
    Protected by a shared secret header.
    """
    if x_staff_secret != STAFF_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden.")

    result = await players_col.update_one(
        {"discord_name": req.discord_name},
        {"$set": {"label": req.label.upper(), "colour": req.colour}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"No linked player found for Discord name '{req.discord_name}'.")

    return {"success": True, "message": f"Status updated to {req.label.upper()} ({req.colour})."}


@app.get("/lookup-discord/{discord_id}")
async def lookup_by_discord(discord_id: str):
    """
    Discord bot can call this to show a user their own linked info.
    """
    player = await players_col.find_one({"discord_id": discord_id})
    if not player:
        raise HTTPException(status_code=404, detail="No linked game account found.")
    return {
        "game_player_id": player["game_player_id"],
        "label": player["label"],
        "colour": player["colour"],
        "linked_at": player["linked_at"].isoformat()
    }
