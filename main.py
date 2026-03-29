# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import uuid

# ייבוא הלוגיקה והמילונים שיצרנו
from game_logic import QuartetsGame
from terms import get_flat_deck as get_fintech_deck
from terms2 import get_cyber_deck

app = FastAPI(title="Quartets Multiplayer")

# הגדרת תיקיות לקבצים סטטיים (CSS/JS) ותבניות (HTML)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# מאגר זיכרון לניהול החדרים והחיבורים
games = {}         # room_id -> QuartetsGame
connections = {}   # room_id -> [WebSocket, ...]

class ConnectionManager:
    """מחלקה לניהול חיבורי ה-WebSockets של השחקנים"""
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
                # אופציונלי: מחיקת המשחק אם החדר ריק לגמרי
                if room_id in games:
                    del games[room_id]

    async def broadcast_game_state(self, room_id: str):
        """שליחת מצב המשחק המעודכן לכל שחקן בחדר (כל אחד מקבל מידע מותאם אישית)"""
        if room_id not in self.active_connections or room_id not in games:
            return
            
        game = games[room_id]
        for ws in self.active_connections[room_id]:
            # חילוץ ה-ID של השחקן מתוך אובייקט החיבור (שמרנו אותו בשלב ההתחברות)
            player_id = getattr(ws, "player_id", None)
            if player_id:
                state = game.get_game_state_for_player(player_id)
                await ws.send_json({"type": "game_state", "data": state})

    async def broadcast_message(self, room_id: str, message: str, msg_type: str = "info"):
        """שליחת הודעת טקסט לכל יושבי החדר (למשל: 'שחקן 1 חילק קלפים')"""
        if room_id in self.active_connections:
            for ws in self.active_connections[room_id]:
                await ws.send_json({"type": "chat", "msg_type": msg_type, "message": message})

manager = ConnectionManager()

@app.get("/")
async def get_home(request: Request):
    """הגשת דף המשחק הראשי"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/{room_id}/{player_name}/{theme}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str, theme: str):
    """
    נקודת הקצה שאליה מתחברים השחקנים.
    theme יכול להיות 'cyber' או 'fintech'.
    """
    await manager.connect(websocket, room_id)
    
    # ייצור מזהה ייחודי לשחקן
    player_id = str(uuid.uuid4())[:8]
    websocket.player_id = player_id # שמירת ה-ID על אובייקט החיבור
    
    # יצירת חדר חדש אם הוא לא קיים
    if room_id not in games:
        # טעינת החפיסה המתאימה לפי בחירת השחקן הראשון
        if theme == "cyber":
            deck = get_cyber_deck()
        else:
            deck = get_fintech_deck()
            
        games[room_id] = QuartetsGame(room_id, deck)
        await manager.broadcast_message(room_id, f"חדר {room_id} נוצר עם חפיסת {theme}.", "success")

    game = games[room_id]
    
    # הוספת השחקן למנוע המשחק
    success, msg = game.add_player(player_id, player_name)
    if not success:
        await websocket.send_json({"type": "error", "message": msg})
        manager.disconnect(websocket, room_id)
        return

    await manager.broadcast_message(room_id, f"{player_name} הצטרף לחדר.")
    await manager.broadcast_game_state(room_id)

    try:
        # לולאת האזנה להודעות מהדפדפן
        while True:
            data = await websocket.receive_text()
            parsed_data = json.loads(data)
            action = parsed_data.get("action")

            if action == "start_game":
                success, msg = game.start_game()
                if success:
                    await manager.broadcast_message(room_id, "המשחק מתחיל! הקלפים חולקו.", "success")
                else:
                    await manager.broadcast_message(room_id, msg, "error")
                await manager.broadcast_game_state(room_id)

            elif action == "ask_card":
                target_id = parsed_data.get("target_id")
                series_name = parsed_data.get("series_name")
                requested_card_id = parsed_data.get("card_id")
                
                # ביצוע המהלך בלוגיקה
                result = game.process_request(player_id, target_id, series_name, requested_card_id)
                
                if result["status"] == "error":
                    await websocket.send_json({"type": "error", "message": result["message"]})
                else:
                    # שידור תוצאת המהלך לכולם
                    target_name = game.players[target_id]["name"]
                    await manager.broadcast_message(room_id, f"{player_name} ביקש קלף מ-{target_name}... {result['message']}")
                    await manager.broadcast_game_state(room_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        if room_id in games and player_id in game.players:
            await manager.broadcast_message(room_id, f"{player_name} התנתק.", "error")
            # במערכת מלאה נרצה לטפל בשחקן שעוזב באמצע (למשל להחזיר את קלפיו לקופה)
            await manager.broadcast_game_state(room_id)