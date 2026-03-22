import random
import time
import os
import string
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trophy_race_secret_777'
socketio = SocketIO(app, cors_allowed_origins="*")

# Tracks all active games: { "CODE": { "p1": {}, "p2": {}, "start_time": float } }
rooms = {}

def create_board():
    size = 10
    board = [[0 for _ in range(size)] for _ in range(size)]
    # Place 15 Bombs
    for _ in range(15):
        while True:
            r, c = random.randint(0, 9), random.randint(0, 9)
            if board[r][c] == 0:
                board[r][c] = "B"; break
    # Place 1 Trophy
    while True:
        r, c = random.randint(0, 9), random.randint(0, 9)
        if board[r][c] == 0:
            board[r][c] = "T"; break
    # Calculate Numbers
    for r in range(10):
        for c in range(10):
            if board[r][c] in ["B", "T"]: continue
            count = 0
            for dr in [-1,0,1]:
                for dc in [-1,0,1]:
                    nr, nc = r+dr, c+dc
                    if 0<=nr<10 and 0<=nc<10 and board[nr][nc] == "B":
                        count += 1
            board[r][c] = count
    return board

@app.route('/')
def index():
    return render_template('design.html')

@socketio.on('create_room')
def on_create(data):
    # Generate 4-digit code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    rooms[code] = {
        "p1": {"id": request.sid, "name": data['name'], "board": create_board()},
        "p2": {"id": None, "name": None, "board": None},
        "start_time": None
    }
    join_room(code)
    emit('room_joined', {'code': code, 'role': 'p1'})

@socketio.on('join_room_request')
def on_join(data):
    code = data['code'].upper()
    if code in rooms and rooms[code]["p2"]["id"] is None:
        rooms[code]["p2"] = {"id": request.sid, "name": data['name'], "board": create_board()}
        join_room(code)
        emit('room_joined', {'code': code, 'role': 'p2'}, room=request.sid)
        
        # Start game for both
        rooms[code]["start_time"] = time.time()
        emit('update_names', {'p1': rooms[code]['p1']['name'], 'p2': rooms[code]['p2']['name']}, to=code)
        emit('start_timer', to=code)
    else:
        emit('error_msg', {'msg': 'Room not found or full!'})

@socketio.on('cell_clicked')
def handle_click(data):
    code, p, r, c = data['code'], data['player'], data['row'], data['col']
    if code not in rooms: return
    
    val = rooms[code][p]["board"][r][c]
    if val == "T":
        emit('reveal_batch', {'player': p, 'cells': [{'r': r, 'c': c, 'v': 'T'}]}, to=code)
        elapsed = round(time.time() - rooms[code]["start_time"], 2)
        socketio.sleep(0.5)
        emit('game_over', {'winner_name': rooms[code][p]['name'], 'winner_role': p, 'time': elapsed}, to=code)
    elif val == "B":
        rooms[code][p]["board"] = create_board() # Reset their board
        emit('player_reset', {'player': p, 'name': rooms[code][p]['name']}, to=code)
    else:
        emit('reveal_batch', {'player': p, 'cells': [{'r': r, 'c': c, 'v': val}]}, to=code)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)