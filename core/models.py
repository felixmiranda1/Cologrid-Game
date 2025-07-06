from django.db import models

class GameSession(models.Model):
    code = models.CharField(max_length=8, unique=True)
    mode = models.CharField(max_length=10, choices=[
        ('local', 'Local'),
        ('remote', 'Remote')
    ])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Partida {self.code} ({self.mode})"

class Player(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name='players')
    name = models.CharField(max_length=50)
    score = models.IntegerField(default=0)
    device_type = models.CharField(max_length=10, choices=[
        ('tv', 'TV'),
        ('mobile', 'Mobile'),
        ('desktop', 'Desktop')
    ])
    is_host = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.session.code})"
    
class GameRound(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name='rounds')
    round_number = models.IntegerField()
    target_color = models.CharField(max_length=7)  # Ex: '#FFAABB'
    explainer = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='rounds_as_explainer'
    )
    short_hint = models.CharField(max_length=20, blank=True)
    long_hint = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'round_number')

    def __str__(self):
        return f"Rodada {self.round_number} da sessão {self.session.code}"

class PlayerMove(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='moves')
    round = models.ForeignKey(GameRound, on_delete=models.CASCADE, related_name='moves')
    attempt_number = models.PositiveSmallIntegerField(choices=[
        (1, 'Primeira tentativa'),
        (2, 'Segunda tentativa')
    ])
    chosen_color = models.CharField(max_length=7)
    color_distance = models.FloatField()
    score = models.IntegerField(default=0)
    played_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('player', 'round', 'attempt_number')

    def __str__(self):
        return f"Tentativa {self.attempt_number} de {self.player.name} na rodada {self.round.round_number}"
