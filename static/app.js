let ws;
let currentRoom = "";
let currentPlayerName = "";
let myCurrentHand = [];
let fullCatalog = [];

function showGameScreen() {
    document.getElementById('lobby-screen').classList.remove('active');
    document.getElementById('game-screen').classList.add('active');
}

function addLog(message, type="info") {
    const logDiv = document.getElementById('game-log');
    const msgDiv = document.createElement('div');
    msgDiv.className = `log-msg log-${type}`;
    msgDiv.innerText = `> ${message}`;
    logDiv.appendChild(msgDiv);
    logDiv.scrollTop = logDiv.scrollHeight; 
}

function joinRoom() {
    const roomId = document.getElementById('room-id').value.trim();
    const playerName = document.getElementById('player-name').value.trim();
    const theme = document.getElementById('theme-select').value;

    if (!roomId || !playerName) {
        alert("נא להזין שם חדר ושם שחקן!");
        return;
    }

    currentRoom = roomId;
    currentPlayerName = playerName;
    
    document.getElementById('display-room').innerText = roomId;
    document.getElementById('display-name').innerText = playerName;

    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";
    const wsUrl = `${protocol}${window.location.host}/ws/${roomId}/${playerName}/${theme}`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        showGameScreen();
        addLog("התחברת לשרת בהצלחה!", "success");
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "chat") {
            addLog(data.message, data.msg_type);
        } else if (data.type === "error") {
            addLog(`שגיאה: ${data.message}`, "error");
            alert(data.message);
        } else if (data.type === "game_state") {
            // תוקן: שולחים את data ישירות, כי השרת לא עוטף את זה בעוד data
            renderGameState(data);
        }
    };

    ws.onclose = () => {
        addLog("החיבור לשרת נותק.", "error");
    };
}

function startGame() {
    if(ws && ws.readyState === WebSocket.OPEN) {
        // תוקן: שונה מ-action ל-type
        ws.send(JSON.stringify({ type: "start_game" }));
    }
}

function renderGameState(state) {
    if (state.is_started) {
        document.getElementById('start-btn').style.display = 'none';
    }

    myCurrentHand = state.my_hand;
    if (state.full_catalog) {
        fullCatalog = state.full_catalog;
    }

    const turnDisplay = document.getElementById('turn-status');
    if (state.game_over) {
        turnDisplay.innerText = "המשחק הסתיים!";
        turnDisplay.style.color = "#10b981";
    } else if (state.turn_player_name) {
        turnDisplay.innerText = `תור ${state.turn_player_name}`;
    }

    document.getElementById('my-score').innerText = state.my_score || 0;

    // --- ציור ועדכון יריבים ---
    const oppArea = document.getElementById('opponents-area');
    const targetSelect = document.getElementById('ask-target');
    const prevTarget = targetSelect.value;
    
    oppArea.innerHTML = "";
    targetSelect.innerHTML = '<option value="">-- ממי לבקש? --</option>';

    state.opponents.forEach(opp => {
        oppArea.innerHTML += `
            <div class="opponent-card">
                <strong>${opp.name}</strong> 
                <span class="opponent-id">(ID: ${opp.id})</span><br>
                🎴 קלפים ביד: ${opp.cards_count}<br>
                ⭐ רביעיות שהשלים: ${opp.score}
            </div>
        `;
        if (opp.cards_count > 0) {
            targetSelect.innerHTML += `<option value="${opp.id}">${opp.name}</option>`;
        }
    });
    targetSelect.value = prevTarget;

    // --- ציור הקלפים שלי ---
    const cardsArea = document.getElementById('my-cards');
    cardsArea.innerHTML = "";
    state.my_hand.forEach(card => {
        cardsArea.innerHTML += `
            <div class="play-card">
                <div class="series">${card.series}</div>
                <div class="title">${card.he}</div>
                <div class="desc">${card.def}</div>
                <div class="cid">ID: ${card.id}</div>
            </div>
        `;
    });

    // --- עדכון רשימת הסדרות ---
    const seriesSelect = document.getElementById('ask-series');
    const prevSeries = seriesSelect.value;
    seriesSelect.innerHTML = '<option value="">-- איזו סדרה? --</option>';
    
    const mySeriesNames = [...new Set(myCurrentHand.map(c => c.series))];
    mySeriesNames.forEach(s => {
        seriesSelect.innerHTML += `<option value="${s}">${s}</option>`;
    });

    if (mySeriesNames.includes(prevSeries)) {
        seriesSelect.value = prevSeries;
    } else {
        document.getElementById('ask-card').innerHTML = '<option value="">-- איזה קלף? --</option>';
    }
    
    updateCardDropdown(); // רענון רשימת הקלפים בהתאם לסדרה

    // --- ניהול מצב הכפתור ---
    const askBtn = document.getElementById('btn-ask');
    if (state.is_my_turn && !state.game_over) {
        askBtn.disabled = false;
        askBtn.innerText = "בקש קלף!";
        askBtn.style.background = "#0ea5e9";
        askBtn.style.cursor = "pointer";
    } else {
        askBtn.disabled = true;
        askBtn.innerText = "לא התור שלך";
        askBtn.style.background = "#475569";
        askBtn.style.cursor = "not-allowed";
    }
}

function updateCardDropdown() {
    const seriesSelect = document.getElementById('ask-series');
    const cardSelect = document.getElementById('ask-card');
    const selectedSeries = seriesSelect.value;

    const prevCard = cardSelect.value;
    cardSelect.innerHTML = '<option value="">-- איזה קלף? --</option>';

    if (!selectedSeries) return;

    // שולף מהקטלוג השלם את קלפי הסדרה שנבחרה
    const seriesCards = fullCatalog.filter(c => c.series === selectedSeries);
    
    // מסנן החוצה את הקלפים שכבר יש לי ביד
    const myCardIds = myCurrentHand.map(c => c.id);
    const missingCards = seriesCards.filter(c => !myCardIds.includes(c.id));

    missingCards.forEach(c => {
        cardSelect.innerHTML += `<option value="${c.id}">${c.he} (${c.en})</option>`;
    });

    // ניסיון לשחזר בחירה אם עדיין רלוונטית
    if (missingCards.some(c => c.id === prevCard)) {
        cardSelect.value = prevCard;
    }
}

function askForCard() {
    const targetId = document.getElementById('ask-target').value;
    const seriesName = document.getElementById('ask-series').value;
    const cardId = document.getElementById('ask-card').value;

    if (!targetId || !seriesName || !cardId) {
        alert("יש לבחור שחקן, סדרה וקלף מתוך הרשימות!");
        return;
    }

    // תוקן: שמות המפתחות הותאמו בדיוק למה ש-main.py קורא
    ws.send(JSON.stringify({
        type: "ask_card",
        target: targetId,
        series: seriesName,
        card_id: cardId
    }));
    
    // איפוס בחירת הקלף כדי לא לבקש בטעות פעמיים את אותו הדבר
    document.getElementById('ask-card').value = "";
}