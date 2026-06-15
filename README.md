# Unity ↔ Discord Linker

A system that lets players link their Unity game account to Discord,
and lets staff update a visible in-game status label via a Discord bot command.

---

## Folder Structure

```
discord-unity-linker/
├── backend/
│   ├── main.py            ← FastAPI server
│   └── requirements.txt
├── bot/
│   ├── bot.py             ← discord.py bot
│   └── requirements.txt
├── unity/
│   └── DiscordLinker.cs   ← Unity C# MonoBehaviour
└── .env.example           ← copy to .env and fill in
```

---

## 1. MongoDB

Install MongoDB locally or use [MongoDB Atlas](https://www.mongodb.com/atlas) (free tier).
The backend creates the `unity_discord` database automatically on first use.

---

## 2. Backend (FastAPI)

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example ../.env   # fill in your values
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Endpoints summary

| Method | Path | Who calls it | Purpose |
|--------|------|--------------|---------|
| POST | `/generate-code` | Unity | Get/create the player's link code |
| GET  | `/player-status/{id}` | Unity | Poll for linked status + label |
| POST | `/link` | Discord bot | Player submits their code |
| PATCH| `/set-status` | Discord bot (staff) | Change a player's label/colour |
| GET  | `/lookup-discord/{discord_id}` | Discord bot | Player checks own info |

---

## 3. Discord Bot

```bash
cd bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

### Slash commands

| Command | Who | Description |
|---------|-----|-------------|
| `/link <code>` | Any player | Links Discord to game using the 8-char code |
| `/mystatus` | Any linked player | Shows their current label and colour |
| `/setstatus <discord_name> <label> <colour>` | Staff role only | Changes a player's in-game status |

**Colour values accepted by `/setstatus`:**
`grey`, `red`, `green`, `blue`, `gold`, `purple`, `orange`, `white`, or any `#RRGGBB` hex code.

---

## 4. Unity

1. Drop `DiscordLinker.cs` into your Unity project's `Scripts` folder.
2. Create a Canvas with:
   - A **Linking Panel** (shown before linking) containing:
     - `TextMeshPro` for the code (assign to `codeText`)
     - `TextMeshPro` for instructions (assign to `instructionText`)
   - A **Linked Panel** (shown after linking) containing:
     - `TextMeshPro` for the label (assign to `statusLabelText`)
3. Attach `DiscordLinker` to a GameObject and assign all references in the Inspector.
4. Set `apiBaseUrl` to wherever your FastAPI server is hosted.

The script auto-polls every 5 seconds (configurable). Once linked, the panel
switches and shows the player's label with the correct colour.

---

## 5. .env values

| Key | Description |
|-----|-------------|
| `MONGO_URI` | MongoDB connection string |
| `STAFF_SECRET` | Shared secret between bot and API — use a long random string |
| `DISCORD_TOKEN` | Your bot's token from the Discord Developer Portal |
| `API_BASE` | URL of your FastAPI server |
| `STAFF_ROLE_ID` | Numeric ID of the Discord role allowed to use `/setstatus` |

---

## Flow Diagram

```
Player opens linking screen in Unity
        │
        ▼
Unity → POST /generate-code  →  Gets "AB12CD34"
        │
        ▼
Player sees: "Run /link AB12CD34 in Discord"
        │
        ▼
Player runs /link AB12CD34 in Discord
        │
        ▼
Bot → POST /link  →  Creates player record (label: MEMBER, colour: #808080)
        │
        ▼
Unity polls /player-status  →  linked: true  →  Shows "MEMBER" in grey
        │
        ▼
Staff runs /setstatus PlayerName VIP gold in Discord
        │
        ▼
Bot → PATCH /set-status  →  Updates label + colour in MongoDB
        │
        ▼
Unity next poll  →  Shows "VIP" in gold
```
