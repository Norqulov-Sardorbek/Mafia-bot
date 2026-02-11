import json
from datetime import timedelta
from django.db import models
from django.utils import timezone
from core.models.basemodel import SafeBaseModel
from core.constants import LANGUAGE_CHOICES,MONEY_FOR_STAR,STONE_FOR_STAR
# Create your models here.




class User(SafeBaseModel):
    USER_ROLES = [
        ('user', 'User'),
        ('admin', 'Admin'),
    ]
    telegram_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=255,null=True, blank=True)
    username = models.CharField(max_length=255,null=True, blank=True)
    lang = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='uz')
    coin=models.IntegerField(default=0)
    stones = models.IntegerField(default=0)
    protection=models.IntegerField(default=0)
    hang_protect=models.IntegerField(default=0)
    docs=models.IntegerField(default=0)
    active_role=models.IntegerField(default=0)
    role = models.CharField(max_length=50, choices=USER_ROLES, default='user')
    is_vip=models.BooleanField(default=False)
    is_hero = models.BooleanField(default=False)
    hero_level = models.IntegerField(default=1)
    geroy_protection = models.IntegerField(default=0)
    is_protected = models.BooleanField(default=True)
    is_hang_protected = models.BooleanField(default=True)
    is_doc = models.BooleanField(default=True)
    is_geroy_protected = models.BooleanField(default=True)
    is_active_role_use = models.BooleanField(default=True)
    is_geroy_use = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.username} - {self.telegram_id}"
class UserRole(SafeBaseModel):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    role_key = models.CharField(max_length=50)
    
    def __str__(self):
        return f"UserRole {self.user.username} - Role {self.role_key}"
    
class Game(SafeBaseModel):
    GAME_TYPE =[
        ('classic','Classic'),
        ('turnir','Turnir'),
    ]
    lang = models.CharField(max_length=2,choices=LANGUAGE_CHOICES,default="uz")
    chat_id = models.BigIntegerField()
    game_type = models.CharField(max_length=50,default="classic",choices=GAME_TYPE)
    is_started = models.BooleanField(default=False)
    is_ended=models.BooleanField(default=False)
    is_active_game=models.BooleanField(default=True)
    
    def __str__(self):
        return f"Game {self.id} - Chat {self.chat_id}"
    
    
class PrizeHistory(models.Model):
    PERIOD_DAILY = "daily"
    PERIOD_WEEKLY = "weekly"
    PERIOD_MONTHLY = "monthly"

    PERIOD_CHOICES = (
        (PERIOD_DAILY, "Daily"),
        (PERIOD_WEEKLY, "Weekly"),
        (PERIOD_MONTHLY, "Monthly"),
    )

    group = models.BigIntegerField()
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)

    start_date = models.DateField()
    end_date = models.DateField()


    class Meta:
        unique_together = ("group", "period", "start_date", "end_date")

    def __str__(self):
        return f"{self.group} {self.period} {self.start_date}..{self.end_date}"

class MostActiveUser(SafeBaseModel):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    group = models.BigIntegerField()
    games_played = models.IntegerField(default=0)
    games_win = models.IntegerField(default=0)
    
    def __str__(self):
        return f"MostActiveUser {self.user.username} - Games Played {self.games_played}"

class BotMessages(SafeBaseModel):
    game = models.ForeignKey(Game,on_delete=models.CASCADE)
    message_id= models.BigIntegerField()
    is_deleted=models.BooleanField(default=False)
    is_main = models.BooleanField(default=False)
    
    def __str__(self):
        return f"BotMessage {self.id} - Game {self.game.id} - MessageID {self.message_id}"
    
    
class PremiumGroup(SafeBaseModel):
    group_id = models.BigIntegerField(unique=True,default=0)
    name = models.CharField(max_length=255)
    link = models.CharField(max_length=255)
    stones_for = models.IntegerField(default=0)
    ends_date = models.DateTimeField()
    
    def __str__(self):
        return f"PremiumGroup {self.name}"
    
class CasesOpened(SafeBaseModel):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    money_case=models.BooleanField(default=False)
    stone_case=models.BooleanField(default=False)
    
    
    def __str__(self):
        return f"CasesOpened {self.user.username} - Type {self.case_type} - Amount {self.amount_won}"
    
def default_end_date():
    return timezone.now() + timedelta(days=30)
class GroupTrials(SafeBaseModel):
    group_id = models.BigIntegerField(unique=True)
    group_name = models.CharField(max_length=255)
    group_username = models.CharField(max_length=255,null=True, blank=True)
    coins = models.IntegerField(default=0)
    stones = models.IntegerField(default=0)
    premium_stones = models.IntegerField(default=0)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(default=default_end_date)
    lang = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='uz')
    prem_ends_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"GroupTrial {self.group_id} - From {self.start_date} to {self.end_date}"
    
  
money_in_money_default = (
    "77 Рубль | 10 000 UZS - 💶 13 000\n"
"385 Рубль | 50 000 UZS - 💶 65 000\n"
"770 Рубль | 100 000 UZS - 💶 130 000\n"
"3850 Рубль | 500 000 UZS - 💶 650 000\n"
"7700 Рубль | 1 000 000 UZS - 💶 1 300 000"
)

stone_in_money_default = (
    "77 Рубль | 10 000 UZS - 💎 10\n"
    "208 Рубль | 27 000 UZS - 💎 30\n"
    "323 Рубль | 42 000 UZS - 💎 50\n"
    "431 Рубль | 56 000 UZS - 💎 70\n"
    "577 Рубль | 75 000 UZS - 💎 100\n"
    "1154 Рубль | 150 000 UZS - 💎 200\n"
    "1731 Рубль | 225 000 UZS - 💎 300\n"
    "2770 Рубль | 360 000 UZS - 💎 500\n"
    "5834 Рубль | 700 000 UZS - 💎 1000\n"
    "10154 Рубль | 1 320 000 UZS - 💎 2000\n"
    "14308 Рубль | 1 860 000 UZS - 💎 3000"
)


def money_in_star_default():
    return json.dumps(MONEY_FOR_STAR)


def stone_in_star_default():
    return json.dumps(STONE_FOR_STAR)


class PriceStones(SafeBaseModel):
    money_in_money = models.TextField(blank=True, default=money_in_money_default)
    money_in_star = models.TextField(blank=True, default=money_in_star_default)

    stone_in_money = models.TextField(blank=True, default=stone_in_money_default)
    stone_in_star = models.TextField(blank=True, default=stone_in_star_default)

    def __str__(self):
        return "PriceStones"

class MoneySendHistory(SafeBaseModel):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_money')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_money')
    amount = models.TextField()
    
    def __str__(self):
        return f"MoneySendHistory from {self.sender.username} to {self.receiver.username} - Amount {self.amount}"
    

# class GroupMember(models.Model):
#     group = models.ForeignKey(GroupTrials, on_delete=models.CASCADE)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)

#     class Meta:
#         unique_together = ("group", "user")

class GameSettings(SafeBaseModel):
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    group_id = models.BigIntegerField(unique=True)
    begin_instance=models.BooleanField(default=False)
    begin_instance_time=models.IntegerField(default=300)  
    number_of_players = models.IntegerField(default=30)
    begin_after_end = models.BooleanField(default=True)
    
    
class BotCredentials(SafeBaseModel):
    login = models.CharField(max_length=255,default="admin")
    password = models.CharField(max_length=255,default="1234")
    
    def __str__(self):
        return f"BotCredentials Admin {self.admin.username}"
    
    
class LoginAttempts(SafeBaseModel):
    admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name="login_attempts")
    attempts = models.IntegerField(default=0)
    last_attempt = models.DateTimeField(null=True, blank=True)

    ban_until = models.DateTimeField(null=True, blank=True)
    permanent_ban = models.BooleanField(default=False)
    def __str__(self):
        return f"LoginAttempts tg_id={self.admin.telegram_id} attempts={self.attempts}"

    def is_banned(self):
        if self.permanent_ban:
            return True
        if self.ban_until and self.ban_until > timezone.now():
            return True
        return False

    def ban_for_1_day(self):
        self.ban_until = timezone.now() + timedelta(days=1)
        self.last_attempt = timezone.now()
        self.save(update_fields=["ban_until", "last_attempt"])

    def ban_forever(self):
        self.permanent_ban = True
        self.ban_until = None
        self.last_attempt = timezone.now()
        self.save(update_fields=["permanent_ban", "ban_until", "last_attempt"])