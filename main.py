# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import json
from game_logic import QuartetsGame

# הייבוא המדויק לפי הקבצים והמשתנים שלך:
from terms import QUARTETS_DATA as FINTECH_DECK
from terms2 import CYBER_QUARTETS_DATA as CYBER_DECK

app = FastAPI()
# ... שאר הקוד נשאר ללא שינוי ...


# הגדרת נתיבים לקבצים סטטיים ותבניות
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ניהול חדרים
rooms = {}

@app.websocket("/ws/{room_id}/{player_name}/{theme}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str, theme: str):
    await websocket.accept()
    
    if room_id not in rooms:
        deck = CYBER_DECK if theme == "cyber" else FINTECH_DECK
        rooms[room_id] = QuartetsGame(room_id, deck)
    
    game = rooms[room_id]
    player_id = str(id(websocket))
    
    success, message = game.add_player(player_id, player_name)
    if not success:
        await websocket.send_json({"type": "error", "message": message})
        await websocket.close()
        return

    game.players[player_id]["socket"] = websocket
    
    await broadcast_state(room_id)
    await broadcast_chat(room_id, f" השחקן {player_name} הצטרף לחדר!", "success")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["action"] == "start_game":
                success, msg = game.start_game()
                if success:
                    await broadcast_chat(room_id, "🚀 המשחק מתחיל! הקלפים חולקו.", "info")
                    await broadcast_state(room_id)
                else:
                    await websocket.send_json({"type": "error", "message": msg})
            
            elif message["action"] == "ask_card":
                res = game.process_request(
                    player_id, 
                    message["target_id"], 
                    message["series_name"], 
                    message["card_id"]
                )
                await broadcast_chat(room_id, res["message"], "info" if res["status"]=="success" else "error")
                await broadcast_state(room_id)

    except WebSocketDisconnect:
        if player_id in game.players:
            del game.players[player_id]
            if not game.players:
                del rooms[room_id]
            else:
                await broadcast_chat(room_id, f"השחקן {player_name} עזב את המשחק.", "error")
                await broadcast_state(room_id)

async def broadcast_state(room_id):
    game = rooms[room_id]
    for pid, pdata in game.players.items():
        state = game.get_game_state_for_player(pid)
        await pdata["socket"].send_json({"type": "game_state", "data": state})

async def broadcast_chat(room_id, message, msg_type="info"):
    game = rooms[room_id]
    for pdata in game.players.values():
        await pdata["socket"].send_json({
            "type": "chat", 
            "message": message, 
            "msg_type": msg_type
        })