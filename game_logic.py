# game_logic.py
import random

class QuartetsGame:
    def __init__(self, room_id, theme_deck):
        self.room_id = room_id
        self.players = {}           
        self.player_order = []      
        self.current_turn_idx = 0   
        self.bank = theme_deck.copy()
        
        # שמירת קטלוג הקלפים המלא כדי שהדפדפן יוכל לבנות את הרשימות הנפתחות
        self.full_catalog = theme_deck.copy() 
        
        self.is_started = False
        self.game_over = False

    def add_player(self, player_id, player_name):
        if self.is_started:
            return False, "המשחק כבר התחיל."
        if len(self.players) >= 4:
            return False, "החדר מלא (מקסימום 4 שחקנים)."
        
        self.players[player_id] = {
            "name": player_name,
            "hand": [],
            "score": 0,
            "completed_series": []
        }
        self.player_order.append(player_id)
        return True, "שחקן הצטרף בהצלחה."

    def start_game(self):
        if len(self.players) < 2:
            return False, "דרושים לפחות 2 שחקנים כדי להתחיל."
        
        self.is_started = True
        random.shuffle(self.bank)
        
        for _ in range(4):
            for pid in self.player_order:
                if self.bank:
                    self.players[pid]["hand"].append(self.bank.pop())
                    
        for pid in self.player_order:
            self.check_for_quartet(pid)
            
        return True, "המשחק התחיל!"

    def is_legal_request(self, asker_id, target_id, series_name):
        if self.player_order[self.current_turn_idx] != asker_id:
            return False, "זה לא התור שלך!"
        if target_id not in self.players or target_id == asker_id:
            return False, "שחקן מטרה לא חוקי."
            
        asker_hand = self.players[asker_id]["hand"]
        has_base_card = any(card["series"] == series_name for card in asker_hand)
        
        if not has_base_card:
            return False, "מהלך לא חוקי: אין לך נציגות של הסדרה הזו ביד."
            
        return True, "מהלך חוקי."

    def process_request(self, asker_id, target_id, series_name, requested_card_id):
        legal, msg = self.is_legal_request(asker_id, target_id, series_name)
        if not legal:
            return {"status": "error", "message": msg}

        target_hand = self.players[target_id]["hand"]
        asker_hand = self.players[asker_id]["hand"]
        
        found_card = next((c for c in target_hand if c["id"] == requested_card_id), None)
        
        if found_card:
            target_hand.remove(found_card)
            asker_hand.append(found_card)
            
            completed = self.check_for_quartet(asker_id)
            self.check_game_over()
            
            return {
                "status": "success", 
                "message": f"בול! קיבלת את הקלף מ-{self.players[target_id]['name']}.",
                "got_card": True,
                "completed_quartet": completed
            }
        else:
            drawn_card = None
            if self.bank:
                drawn_card = self.bank.pop()
                asker_hand.append(drawn_card)
                self.check_for_quartet(asker_id)
                
            self.next_turn()
            self.check_game_over()
            
            return {
                "status": "success", 
                "message": f"אין ל-{self.players[target_id]['name']} את הקלף. לקחת מהקופה והתור עבר.",
                "got_card": False,
                "drawn_from_bank": drawn_card is not None
            }

    def check_for_quartet(self, player_id):
        hand = self.players[player_id]["hand"]
        series_count = {}
        
        for card in hand:
            s_name = card["series"]
            series_count[s_name] = series_count.get(s_name, 0) + 1
            
        completed_this_turn = None
        for s_name, count in series_count.items():
            if count == 4:
                self.players[player_id]["hand"] = [c for c in hand if c["series"] != s_name]
                self.players[player_id]["score"] += 1
                self.players[player_id]["completed_series"].append(s_name)
                completed_this_turn = s_name
                break 
                
        if len(self.players[player_id]["hand"]) == 0 and self.bank:
            self.players[player_id]["hand"].append(self.bank.pop())
            
        return completed_this_turn

    def next_turn(self):
        if self.game_over:
            return
            
        start_idx = self.current_turn_idx
        while True:
            self.current_turn_idx = (self.current_turn_idx + 1) % len(self.player_order)
            next_pid = self.player_order[self.current_turn_idx]
            
            if len(self.players[next_pid]["hand"]) > 0 or len(self.bank) > 0:
                break
                
            if self.current_turn_idx == start_idx:
                self.check_game_over()
                break

    def check_game_over(self):
        total_quartets_possible = (len(self.bank) + sum(len(p["hand"]) for p in self.players.values()) + sum(p["score"]*4 for p in self.players.values())) / 4
        current_quartets = sum(p["score"] for p in self.players.values())
        
        if current_quartets == total_quartets_possible or (len(self.bank) == 0 and all(len(p["hand"]) == 0 for p in self.players.values())):
            self.game_over = True

    def get_game_state_for_player(self, player_id):
        state = {
            "room_id": self.room_id,
            "is_started": self.is_started,
            "game_over": self.game_over,
            "turn_player_id": self.player_order[self.current_turn_idx] if self.is_started else None,
            "turn_player_name": self.players[self.player_order[self.current_turn_idx]]["name"] if self.is_started else None,
            "is_my_turn": self.is_started and self.player_order[self.current_turn_idx] == player_id,
            "full_catalog": self.full_catalog,
            "bank_cards_left": len(self.bank),
            "my_hand": self.players[player_id]["hand"] if player_id in self.players else [],
            "opponents": []
        }
        
        for pid, pdata in self.players.items():
            if pid != player_id:
                state["opponents"].append({
                    "id": pid,
                    "name": pdata["name"],
                    "cards_count": len(pdata["hand"]),
                    "score": pdata["score"],
                    "completed_series": pdata["completed_series"]
                })
            else:
                state["my_score"] = pdata["score"]
                state["my_completed_series"] = pdata["completed_series"]
                
        return state