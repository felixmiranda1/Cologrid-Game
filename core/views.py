from django.shortcuts import render, redirect
import uuid

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
            return redirect("board")
        else:
            return redirect("remote_game")

    return redirect("home")

def board(request):
    return render(request, "board.html")

def remote_game(request):
    return render(request, "remote_game.html")
