import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from game_logic import QuartetsGame

# ייבוא פונקציות העזר מהקבצים שלך
from terms import get_flat_deck as get_fintech_deck
from terms2 import get_cyber_deck

app = FastAPI()

# ניהול חדרים והחיבורים שלהם
rooms = {}
room_websockets = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# פונקציית העדכון - שולחת לכל אחד בחדר את המצב שלו
async def broadcast_game_state(room_id: str):
    if room_id not in rooms or room_id not in room_websockets:
        return
    
    game = rooms[room_id]
    for p_id, ws in list(room_websockets[room_id].items()):
        try:
            # שימוש בשם המדויק מה-game_logic.py שלך
            state = game.get_game_state_for_player(p_id)
            # חשוב: מוסיפים את ה-type כדי שהדפדפן ידע שזה עדכון מצב
            state["type"] = "game_state"
            await ws.send_json(state)
        except Exception as e:
            print(f"Error sending to {p_id}: {e}")
            # במקרה של שגיאה, נסיר את החיבור הספציפי אבל לא נקריס את השרת
            if p_id in room_websockets.get(room_id, {}):
                del room_websockets[room_id][p_id]

# --- התיקון הקריטי ל-Render ולגרסאות החדשות של FastAPI ---
@app.api_route("/", methods=["GET", "HEAD"])
async def get_index(request: Request):
    # ציון מפורש של שמות הפרמטרים פותר את בעיית ה-tuple as dict key
    return templates.TemplateResponse(request=request, name="index.html")

@app.websocket("/ws/{room_id}/{player_name}/{theme}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str, theme: str):
    await websocket.accept()
    
    # ניקוי רווחים משם החדר כדי למנוע טעויות
    room_id = room_id.strip()
    
    if room_id not in rooms:
        deck = get_cyber_deck() if theme == "cyber" else get_fintech_deck()
        rooms[room_id] = QuartetsGame(room_id, deck)
        room_websockets[room_id] = {}
        print(f"--- חדר חדש נוצר: {room_id} ---")

    game = rooms[room_id]
    
    # הוספת שחקן (משתמשים בשם שלו כמזהה ייחודי)
    success, msg = game.add_player(player_name, player_name)
    
    if not success:
        await websocket.send_json({"type": "error", "message": msg})
        await websocket.close()
        return

    # שמירת החיבור ועדכון הלובי
    room_websockets[room_id][player_name] = websocket
    print(f"שחקן הצטרף: {player_name} לחדר {room_id}. סה\"כ בחדר: {len(game.players)}")
    
    await broadcast_game_state(room_id)

    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
            except json.JSONDecodeError:
                print(f"התקבל מידע שאינו JSON תקין מהשחקן {player_name}. מתעלם...")
                continue # מדלגים על הודעה פגומה, השרת ממשיך לרוץ
            
            # התיקון המקורי ל- KeyError
            msg_type = message.get("type") or message.get("action")
            
            if not msg_type:
                print(f"אזהרה: התקבלה הודעה ללא שדה 'type' בחדר {room_id}: {message}")
                continue # מדלגים כדי לא להגיע ללוגיקה שדורשת את סוג ההודעה

            # ניתוב הלוגיקה לפי סוג ההודעה
            if msg_type == "start_game":
                success, start_msg = game.start_game()
                print(f"ניסיון התחלה ב-{room_id}: {success}, {start_msg}")
            
            elif msg_type == "ask_card":
                game.process_request(
                    player_name, 
                    message.get("target") or message.get("target_id"), 
                    message.get("series") or message.get("series_name"), 
                    message.get("card_id")
                )
            else:
                print(f"סוג הודעה לא מוכר '{msg_type}' מהשחקן {player_name}")
            
            await broadcast_game_state(room_id)

    except WebSocketDisconnect:
        print(f"שחקן עזב: {player_name}")
        if room_id in room_websockets and player_name in room_websockets[room_id]:
            del room_websockets[room_id][player_name]
        
        # ניקוי מהלוגיקה כדי למנוע קריסה בהתחלת משחק
        if player_name in game.players:
            del game.players[player_name]
        if player_name in game.player_order:
            game.player_order.remove(player_name)
        
        if room_id in room_websockets and not room_websockets[room_id]:
            del rooms[room_id]
            del room_websockets[room_id]
            print(f"--- חדר נסגר: {room_id} ---")
        else:
            await broadcast_game_state(room_id)