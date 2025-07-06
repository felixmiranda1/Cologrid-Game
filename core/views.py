from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.urls import reverse
from .models import GameSession, Player
import uuid
import random
import string

# -------------------------------------------------------------
# Global in-memory storage for active game sessions.
# Each key is a session code and the value stores information
# such as mode, players, rounds and status.
# -------------------------------------------------------------
ACTIVE_SESSIONS = {}

# Utility helpers
GRID_MAP = {
    'A1': '#33FF57', 'A2': '#3357FF', 'A3': '#F39C12', 'A4': '#8E44AD', 'A5': '#1ABC9C',
    'B1': '#2ECC71', 'B2': '#E74C3C', 'B3': '#3498DB', 'B4': '#9B59B6', 'B5': '#E67E22',
    'C1': '#BDC3C7', 'C2': '#34495E', 'C3': '#16A085', 'C4': '#27AE60', 'C5': '#2980B9',
    'D1': '#D35400', 'D2': '#7F8C8D', 'D3': '#C0392B', 'D4': '#F1C40F', 'D5': '#E84393',
    'E1': '#6C5CE7', 'E2': '#00CEC9', 'E3': '#FD79A8', 'E4': '#FAB1A0', 'E5': '#FFFFFF'
}

def generate_session_code():
    """Return a unique 6-8 char session code."""
    length = random.randint(6, 8)
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=length))
        if code not in ACTIVE_SESSIONS:
            return code


def rotate_explainer(players, previous_explainer_id=None):
    """Return the id of the next explainer in the list of non-host players."""
    if not players:
        return None

    eligible_ids = [p["id"] for p in players if not p.get("is_host")]
    if not eligible_ids:
        return None

    if previous_explainer_id in eligible_ids:
        next_idx = (eligible_ids.index(previous_explainer_id) + 1) % len(eligible_ids)
    else:
        next_idx = 0
    return eligible_ids[next_idx]

def is_round_over(session, current_round):
    explainer_id = current_round["explainer_id"]
    expected_players = [p["id"] for p in session["players"] if p["id"] != explainer_id]
    moves = current_round.get("moves", [])

    players_with_two_moves = {
        pid for pid in expected_players
        if len([m for m in moves if m["player_id"] == pid]) == 2
    }

    return len(players_with_two_moves) == len(expected_players)

def remote_game(request):
    return render(request, "core/remote_game.html")

def home(request):
    return render(request, 'core/home.html')

def new_game(request):
    if request.method == "POST":
        mode = request.POST.get('mode')
        names = request.POST.get('names').strip().splitlines()

        players = [
            {"id": str(uuid.uuid4())[:5], "name": name.strip(), "points": 0}
            for name in names if name.strip()
        ]

        request.session['game'] = {
            "mode": mode,
            "players": players,
            "round": 0,
            "current_player_index": 0,
            "state": "waiting_for_clue",
        }

        if mode == "local":
            return redirect("lobby")
        else:
            return redirect("remote_game")

    return redirect("home")

def board(request, code):
    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sessão não encontrada", status=404)

    round_number = session.get("current_round")
    round_data = next((r for r in session["rounds"] if r["round_number"] == round_number), None)
    if not round_data:
        return HttpResponse("Rodada não encontrada", status=404)

    color_map = GRID_MAP

    context = {
        "code": code,
        "round": round_data,
        "players": session["players"],
        "is_round_over": is_round_over(session, round_data),
        "color_map": color_map,
        "LETTERS": ["A", "B", "C", "D", "E"],
        "NUMBERS": ["1", "2", "3", "4", "5"],
    }
    return render(request, "core/board.html", context)


# -------------------------------------------------------------
# New multiplayer session views
# -------------------------------------------------------------

def create_session_view(request):
    
    """Create a new game session and store it in memory."""
    if request.method == "POST":
        # Mode defaults to "local" if not provided
        mode = request.POST.get("mode", "local")
        name = request.POST.get("name", "Host")

        code = generate_session_code()
        player_id = str(uuid.uuid4())

        ACTIVE_SESSIONS[code] = {
            "mode": mode,
            "players": [
                {
                    "id": player_id,
                    "name": name,
                    "device": "tv",
                    "is_host": True,
                }
            ],
            "rounds": [],
            "status": "lobby",
        }

        request.session["player_id"] = player_id
        request.session["name"] = name
        request.session["device"] = "tv"
        request.session["code"] = code

        return redirect("lobby")

    return redirect("home")


def join_session_view(request, code):
    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sessão não encontrada", status=404)

    if request.method == "POST":
        name = request.POST.get("name")
        if not name:
            return redirect("join_session", code=code)

        player_id = str(uuid.uuid4())
        device = request.POST.get("device", "mobile")

        session["players"].append({
            "id": player_id,
            "name": name,
            "device": device,
            "is_host": False,
        })

        request.session["player_id"] = player_id
        request.session["name"] = name
        request.session["device"] = device
        request.session["code"] = code

        return redirect("lobby")

    # NOVO: Exibe o formulário se o request for GET
    return render(request, "core/join.html", {"code": code})


def lobby_view(request):
    """Display the waiting room with current players."""
    code = request.session.get("code")
    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sess\u00e3o inexistente", status=404)

    context = {
        "code": code,
        "players": session["players"],
    }
    return render(request, "core/lobby.html", context)


def players_list_partial(request):
    """Return a partial HTML list of connected players."""
    code = request.session.get("code")
    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("", status=404)

    items = "".join(f"<li>{p['name']}</li>" for p in session["players"])
    return HttpResponse(f"<ul>{items}</ul>")


def start_game_view(request):

    """Start the game or redirect players to the correct screen."""
    code = request.session.get("code")
    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sessão inexistente", status=404)

    player_id = request.session.get("player_id")
    player = next((p for p in session["players"] if p["id"] == player_id), None)
    if not player:
        return HttpResponseForbidden("Jogador inválido")

    # Se o jogo já iniciou, apenas redireciona corretamente cada jogador
    if session.get("status") == "in_game" and session.get("current_round"):
        current_round = next(
            (r for r in session["rounds"] if r["round_number"] == session["current_round"]),
            None,
        )
        explainer_id = current_round["explainer_id"] if current_round else None

        if player_id == explainer_id:
            return redirect("submit_hint", session_code=code)
        elif player.get("is_host"):
            return redirect("waiting_hint")
        else:
            return redirect("waiting_hint")

    # Somente o host pode iniciar a primeira rodada
    if not player.get("is_host"):
        return HttpResponseForbidden("Apenas o host pode iniciar a partida")

    round_number = len(session["rounds"]) + 1
    explainer_id = rotate_explainer(session["players"])
    grid_size = 5
    key, color = random.choice(list(GRID_MAP.items()))
    target_row = ["A", "B", "C", "D", "E"].index(key[0])
    target_col = ["1", "2", "3", "4", "5"].index(key[1])

    session["rounds"].append(
        {
            "round_number": round_number,
            "explainer_id": explainer_id,
            "target_color": color,
            "target_position": {"row": target_row, "col": target_col},
            "short_hint": "",
            "long_hint": "",
            "moves": [],
        }
    )
    session["grid_size"] = grid_size
    session["current_round"] = round_number
    session["status"] = "in_game"
    print("DEBUG ACTIVE_SESSIONS:", ACTIVE_SESSIONS)
    # Replicando a lógica de player_redirect_status_view
    current_round = next(
        (r for r in session["rounds"] if r["round_number"] == session["current_round"]),
        None,
    )
    explainer_id = current_round["explainer_id"] if current_round else None

    if player_id == explainer_id:
        return redirect("submit_hint", session_code=code)
    elif player.get("is_host"):
        return redirect("board", code=code)
    else:
        return redirect("waiting_hint")

@csrf_exempt
def submit_hint_view(request, session_code):
    code = session_code  
    player_id = request.session.get("player_id")

    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sessão não encontrada", status=404)

    round_number = session.get("current_round")
    current_round = next((r for r in session["rounds"] if r["round_number"] == round_number), None)
    if not current_round:
        return HttpResponse("Rodada não encontrada", status=404)

    # Verifica se é o explicador
    if current_round["explainer_id"] != player_id:
        return HttpResponseForbidden("Apenas o explicador pode enviar dicas.")

    if request.method == "POST":
        short_hint = request.POST.get("short_hint", "").strip()
        long_hint = request.POST.get("long_hint", "").strip()

        if not short_hint or " " in short_hint:
            return HttpResponse("A dica curta deve ser uma única palavra.", status=400)
        if not long_hint or len(long_hint) > 50:
            return HttpResponse("A dica longa deve ter até 50 caracteres.", status=400)

        current_round["short_hint"] = short_hint
        current_round["long_hint"] = long_hint
        print('AAAAAAAAAAA')
        return redirect("waiting_hint")
    print('BBBBBBBBBBBBBBBB')
    return render(request, "core/submit_hint.html", {
        "code": code,
        "short_hint": current_round.get("short_hint", ""),
        "long_hint": current_round.get("long_hint", "")
    })


# --- NOVA FUNÇÃO: submit_move_view ---
@csrf_exempt
def submit_move_view(request):
    code = request.session.get("code")
    player_id = request.session.get("player_id")

    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sessão não encontrada", status=404)

    if session.get("status") != "in_game":
        return HttpResponse("O jogo ainda não começou.", status=400)

    round_number = session.get("current_round")
    current_round = next((r for r in session["rounds"] if r["round_number"] == round_number), None)
    if not current_round:
        return HttpResponse("Rodada não encontrada", status=404)

    if player_id == current_round["explainer_id"]:
        return redirect("submit_hint", session_code=code)

    moves = current_round.get("moves", [])
    player_moves = [m for m in moves if m["player_id"] == player_id]
    attempt_1_done = any(m["attempt_number"] == 1 for m in player_moves)
    attempt_2_done = any(m["attempt_number"] == 2 for m in player_moves)

    has_short = bool(current_round.get("short_hint"))
    has_long = bool(current_round.get("long_hint"))

    if has_short and not attempt_1_done:
        current_attempt = 1
    elif has_long and attempt_1_done and not attempt_2_done:
        current_attempt = 2
    else:
        return redirect("round_results")

    if request.method == "POST":
        try:
            guess_row = int(request.POST.get("row"))
            guess_col = int(request.POST.get("col"))
        except (TypeError, ValueError):
            return HttpResponse("Coordenadas inválidas.", status=400)

        target = current_round["target_position"]
        dr = abs(target["row"] - guess_row)
        dc = abs(target["col"] - guess_col)
        dist = max(dr, dc)

        if dist == 0:
            score = 4
        elif dist == 1:
            score = 3
        elif dist == 2:
            score = 2
        else:
            score = 0

        move = {
            "player_id": player_id,
            "attempt_number": current_attempt,
            "row": guess_row,
            "col": guess_col,
            "distance": dist,
            "score": score,
        }

        current_round["moves"].append(move)

        # Award bonus points to the explainer
        if score > 0:
            explainer_id = current_round["explainer_id"]
            explainer = next((p for p in session["players"] if p["id"] == explainer_id), None)
            if explainer:
                explainer_bonus = max(score - 1, 0)
                explainer["points"] = explainer.get("points", 0) + explainer_bonus

        # Redirect based on player role
        if player_id == current_round["explainer_id"]:
            return redirect("submit_hint", session_code=code)
        elif any(
            len([m for m in current_round["moves"] if m["player_id"] == p["id"]]) < 2
            for p in session["players"] if p["id"] != current_round["explainer_id"]
        ):
            return redirect("waiting_hint")
        else:
            return redirect("waiting_hint")

    return render(request, "core/submit_move.html", {
        "attempt": current_attempt,
        "code": code,
        "grid_size": session.get("grid_size", 5)
    })

def round_results_view(request):
    code = request.session.get("code")
    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sessão não encontrada", status=404)

    round_number = session.get("current_round")
    current_round = next((r for r in session["rounds"] if r["round_number"] == round_number), None)
    if not current_round:
        return HttpResponse("Rodada não encontrada", status=404)

    if not is_round_over(session, current_round):
        return HttpResponse("A rodada ainda não terminou.", status=400)

    player_id = request.session.get("player_id")
    is_explainer = player_id == current_round["explainer_id"]

    # Organiza ranking da rodada e geral
    players_data = []
    for player in session["players"]:
        player_moves = [m for m in current_round["moves"] if m["player_id"] == player["id"]]
        total_score = sum(m["score"] for m in player_moves)
        players_data.append({
            "name": player["name"],
            "round_score": total_score,
            "total_score": player.get("points", 0),
        })

    context = {
        "code": code,
        "target_color": current_round["target_color"],
        "target_position": current_round["target_position"],
        "short_hint": current_round.get("short_hint", ""),
        "long_hint": current_round.get("long_hint", ""),
        "players_data": players_data,
        "is_explainer": is_explainer,
    }

    return render(request, "core/round_results.html", context)

def next_round_view(request):
    code = request.session.get("code")
    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sessão não encontrada", status=404)

    current_round_number = session.get("current_round", 0)
    current_round = next((r for r in session["rounds"] if r["round_number"] == current_round_number), None)
    if not current_round:
        return HttpResponse("Rodada atual não encontrada", status=404)

    if request.session.get("player_id") != current_round["explainer_id"]:
        return HttpResponse("Apenas o explicador pode iniciar a próxima rodada.", status=403)

    # Novo explicador
    next_explainer_id = rotate_explainer(
        session["players"], current_round.get("explainer_id")
    )

    # Nova cor e posição alvo
    grid_size = session.get("grid_size", 5)
    key, target_color = random.choice(list(GRID_MAP.items()))
    target_position = {
        "row": ["A", "B", "C", "D", "E"].index(key[0]),
        "col": ["1", "2", "3", "4", "5"].index(key[1])
    }

    new_round = {
        "round_number": current_round_number + 1,
        "explainer_id": next_explainer_id,
        "target_color": target_color,
        "target_position": target_position,
        "short_hint": "",
        "long_hint": "",
        "moves": [],
    }

    session["current_round"] = current_round_number + 1
    session["rounds"].append(new_round)

    return redirect("board", code=code)


# --- NOVA VIEW: waiting_hint_view ---
def waiting_hint_view(request):
    code = request.session.get("code")
    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse("Sessão não encontrada", status=404)

    round_number = session.get("current_round")
    current_round = next((r for r in session["rounds"] if r["round_number"] == round_number), None)
    if not current_round:
        return HttpResponse("Rodada não encontrada", status=404)

    # Redireciona para submit_move apenas se o jogador não for o explicador
    # e ambas as dicas (curta e longa) já estiverem presentes.
    player_id = request.session.get("player_id")
    if player_id != current_round["explainer_id"]:
        if current_round.get("short_hint") and current_round.get("long_hint"):
            return redirect("submit_move")

    # Verifica se a rodada acabou e redireciona para round_results se necessário
    if is_round_over(session, current_round):
        return redirect("round_results")

    return render(request, "core/waiting_hint.html", {"code": code})

def player_redirect_status_view(request, code):
    player_id = request.session.get("player_id")
    if not player_id:
        return HttpResponseForbidden("Sem jogador identificado.")

    session = ACTIVE_SESSIONS.get(code)
    if not session:
        return HttpResponse(status=404)

    if session.get("status") != "in_game":
        return HttpResponse(status=204)

    # Se o jogo já começou, define para onde redirecionar o jogador
    round_number = session.get("current_round")
    current_round = next((r for r in session["rounds"] if r["round_number"] == round_number), None)
    if not current_round:
        return HttpResponse(status=404)

    explainer_id = current_round["explainer_id"]

    player = next((p for p in session["players"] if p["id"] == player_id), None)
    if not player:
        return HttpResponseForbidden("Jogador inválido.")

    if player["id"] == explainer_id:
        redirect_url = reverse("submit_hint", args=[code])
    elif player.get("is_host"):
        redirect_url = reverse("waiting_hint")
    else:
        redirect_url = reverse("waiting_hint")

    return HttpResponse(f'<meta http-equiv="refresh" content="0; URL={redirect_url}" />')