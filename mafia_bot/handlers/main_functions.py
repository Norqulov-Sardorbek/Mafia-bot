import re
import time
import random
import asyncio
from typing import Counter
from dispatcher import bot
from threading import Lock
from datetime import timedelta
from django.db import transaction
from aiogram.types import Message
from django.db.models import F as DF
from aiogram.enums import ChatMemberStatus
from core.constants import uz_texts,ROLES_BY_COUNT,ru_texts,en_texts,tr_texts,qz_texts
from mafia_bot.models import Game, GameSettings,User,MostActiveUser, UserRole, GroupTrials
from aiogram.types import ChatPermissions,ChatMemberAdministrator, ChatMemberOwner
from mafia_bot.utils import games_state, last_wishes,game_tasks, active_role_used,writing_allowed_groups,USER_LANG_CACHE,game_locks,chat_id_game_id
from mafia_bot.buttons.inline import cart_inline_btn, doc_btn, com_inline_btn, don_inline_btn, mafia_inline_btn, adv_inline_btn, spy_inline_btn, lab_inline_btn, action_inline_btn,use_hero_inline_btn

lock = Lock()
LANG_TEXTS = {
    "uz": uz_texts,
    "ru": ru_texts,
    "en": en_texts,
    "tr": tr_texts,
    "qz": qz_texts,
}

ROLE_LABELS = {
    "uz": dict(uz_texts["ROLES_CHOICES"]),
    "ru": dict(ru_texts["ROLES_CHOICES"]),
    "en": dict(en_texts["ROLES_CHOICES"]),
    "tr": dict(tr_texts["ROLES_CHOICES"]),
    "qz": dict(qz_texts["ROLES_CHOICES"]),
}

ACTIONS = {
    "uz": dict(uz_texts["ACTIONS"]),
    "ru": dict(ru_texts["ACTIONS"]),
    "en": dict(en_texts["ACTIONS"]),
    "tr": dict(tr_texts["ACTIONS"]),
    "qz": dict(qz_texts["ACTIONS"]),
}

WINNER_LABELS = {
    "uz": uz_texts["WINNER_LABEL"],
    "ru": ru_texts["WINNER_LABEL"],
    "en": en_texts["WINNER_LABEL"],
    "tr": tr_texts["WINNER_LABEL"],
    "qz": qz_texts["WINNER_LABEL"],
}

DESCRIPTIONS = {
    "uz": uz_texts["DESCRIPTIONS"],
    "ru": ru_texts["DESCRIPTIONS"],
    "en": en_texts["DESCRIPTIONS"],
    "tr": tr_texts["DESCRIPTIONS"],
    "qz": qz_texts["DESCRIPTIONS"],
}



MAFIA_ROLES = {"don", "mafia", "adv", "spy"}
MAFIA_ROLES_LAB = {"don", "mafia", "adv", "spy", "lab"}
SOLO_ROLES = {"killer", "trap", "snyper", "arrow", "traitor", "pirate", "professor","drunk"}
PEACE_ROLES = {"peace", "doc", "daydi", "com", "kam", "lover", "serg", "kaldun",  "snowball","santa","nogiron","ghost"}
NIGHT_ACTION_ROLES = {
    "doc", "daydi", "com", "killer", "kaldun",
    "don", "mafia", "adv", "spy", "lab", "trap",
    "snyper", "arrow", "traitor", "pirate", "professor",
     "snowball", "santa","drunk"
}

LINK_RE = re.compile(
    r"("
    r"(?:(?:https?://)|(?:www\.))"                 # http(s) or www
    r"|(?:t\.me/|telegram\.me/|tg://)"             # telegram links
    r"|(?:@[\w\d_]{4,})"                           # @first_name
    r"|(?:[a-z0-9-]+\.)+(?:com|net|org|ru|uz|io|me|app|xyz|info|biz|co|tv|online)\b"  # domains
    r")",
    re.IGNORECASE
)



ROLE_TEAM = {
    "peace": "peace",
    'nogiron':"peace",
    "doc": "peace",
    "daydi": "peace",
    "com": "peace",
    "kam": "peace",
    "lover": "peace",
    "serg": "peace",
    "kaldun": "peace",
    "snowball": "peace",
    "santa": "peace",
    'suid':"peace",
    "ghost":"peace",

    "don": "mafia",
    "mafia": "mafia",
    "adv": "mafia",
    "spy": "mafia",
    "lab": "mafia",

    "killer": "solo",
    "trap": "solo",
    "snyper": "solo",
    "arrow": "solo",
    "traitor": "solo",
    "drunk":"solo",
    "pirate": "solo",
    "professor": "solo",
}




async def send_night_action( tg_id, role, game_id, game, users_after_night, day):
    game_data = games_state.get(game_id, {})
    night_action = game_data.get("night_actions", {})
    lover_block_target = night_action.get("lover_block_target")
    if lover_block_target == tg_id:
        return
    if role in ("peace","serg", "kam","nogiron","suid","ghost"):
        return
    elif role == "doc":
        await send_safe_message(
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("doc_heal"),
            reply_markup=doc_btn(players=users_after_night, doctor_id=tg_id, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return
    elif role == "daydi":
        await send_safe_message(
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("daydi_watch"),
            reply_markup=action_inline_btn(action="daydi", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return

    elif role == "com":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("com_deside"),
            reply_markup=com_inline_btn(game.id, game.chat_id,day=day)
        )
        return
    elif role == "santa":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("santa"),
            reply_markup=action_inline_btn(action="santa", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return
    elif role == "killer":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("killer_kill"),
            reply_markup=action_inline_btn(action="killer", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return
    elif role == "lover":
        await send_safe_message(
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("lover_block"),
            reply_markup=action_inline_btn(action="lover", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return
    elif role == "kaldun":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("kaldun_spell"),
            reply_markup=action_inline_btn(action="kaldun", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return

    elif role == "don":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("don_kill"),
            reply_markup=don_inline_btn(players=users_after_night, game_id=game.id, chat_id=game.chat_id, don_id=tg_id, day=day)
        )
        return

    elif role == "mafia":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("mafia_vote"),
            reply_markup=mafia_inline_btn(players=users_after_night, game_id=game.id,day=day)
        )
        return
    elif role == "adv":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("adv_mask"),
            reply_markup=adv_inline_btn(players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return
    elif role == "spy":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("spy_check"),
            reply_markup=spy_inline_btn(players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day,spy_id=tg_id)
        )
        return
    elif role == "lab":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("lab_action"),
            reply_markup=lab_inline_btn(players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day,lab_id=tg_id)
        )
        return
    elif role == "trap":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("trap_place"),
            reply_markup=action_inline_btn(action="trap", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return
    elif role == "snyper":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("snyper_kill"),
            reply_markup=action_inline_btn(action="snyper", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id,day=day)
        )
        return
    elif role == "arrow":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("arrow_kill"),
            reply_markup=action_inline_btn(action="arrow", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id, day=day)
        )
        return
    elif role == "traitor":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("traitor_choose"),
            reply_markup=action_inline_btn(action="traitor", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id, day=day)
        )
        return
    elif role == "pirate":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("pirate_rob"),
            reply_markup=action_inline_btn(action="pirate", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id, day=day)
        )
        return
    elif role == "professor":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("professor_choose"),
            reply_markup=action_inline_btn(action="professor", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id, day=day)
        )
        return
   
    elif role == "snowball":
        await send_safe_message(
        
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("snowball_kill"),
            reply_markup=action_inline_btn(action="snowball", own_id=tg_id, players=users_after_night, game_id=game.id, chat_id=game.chat_id, day=day)
        )
        return
    elif role == "drunk":
        await send_safe_message(
            chat_id=tg_id,
            text=get_actions_lang(tg_id).get("drunk_action"),
            reply_markup=action_inline_btn(action="drunk",own_id=tg_id,players=users_after_night,game_id=game.id,chat_id=game.chat_id,day=day)
        )
        return
    
async def send_night_actions_to_all( game_id, game,players,day):
    game_data = games_state.get(game_id, {})
    roles_map = game_data.get("roles", {})

    tasks = []
    for user in players:
        tg_id = user.get("tg_id")
        role = roles_map.get(tg_id)
        
        tasks.append(asyncio.create_task(
            send_night_action( tg_id, role, game_id, game,players,day)
        ))

    await asyncio.gather(*tasks, return_exceptions=True)


def init_game(game_id: int, chat_id: int | None = None):
    with lock:
        if game_id in games_state:
            return
        max_players = 30
        game_settings = GameSettings.objects.filter(group_id=int(chat_id)).first()
        if game_settings and game_settings.begin_instance:
            max_players = game_settings.number_of_players if game_settings else max_players
        game = Game.objects.filter(id=game_id).first()
        if game and game.game_type == 'turnir':
            type_game = 'turnir'
        else:
            type_game = 'classic'
       

        games_state[game_id] = {
            "meta": {
                "game_id": game_id,
                "chat_id": chat_id,
                "created_at": int(time.time()),
                "phase": "lobby",
                "game_type": type_game,
                "day": 0,
                "night": 0,
                "message_allowed":"yes",
                "team_chat_open":"no",
                "max_players": max_players,
                "is_active_game": False,
            },
            "runtime": {
                "night_event": None,
                "pending_night": set(),
                "hang_event": None,
                "pending_hang": set(),
                "confirm_event": None,
                "pending_confirm": set(),
             },
            "afk": {
                "missed_nights": {},   # {tg_id: count}
                "kicked": set(),       # kicked users log
            },

            "allowed_to_send_message":[] ,
            "players": [],
            "users_map": {},
            "alive": [],
            "dead": [],
            "left": [],
            "hanged": [],

            "roles": {},
            "team": {},

            "hero": {
                "has": set(),
                'self_protect':set(),
                "used": set(),
                "notified": set(), 
            },

            "limits": {
                "doc_self_heal_used": set(),
                "traitor_transformed": set(),
            },

            "effects": {
                "protected": {},
                "blocked": {},
                "silenced": {},
                "poisoned": {},
                "no_hang": {},
                "advokat_masked": {},
            },

            "visits": {
                "log": [],
                "invisible_visitors": set(),
            },

            "kills": {
                "shooted": {},
                "hanged": set(),
                "special": set(),
            },

            "night_actions": {
                "don_kill_target": None,
                "mafia_vote": [],

                "doc_target": None,
                "com_check_target": None,
                "com_shoot_target": None,

                "daydi_house": None,
                "daydi_seen": [],

                "lover_block_target": None,

                "kaldun_target": None,
                "killer_target": [],
                "advokat_target": None,
                "spy_target": None,
                "lab_target": None,
                "drunk_target": None,

                "trap_house": None,

                "snyper_target": None,
                "arrow_target": None,

                "traitor_target": None,

                "snowball_target": None,
                "hero_targets":{},
                "hero_used":{},
                "pirate": {
                    "pirate_id": None,
                    "target_id": None,
                    "result": None,
                },

                "professor": {
                    "target_id": None,
                    "chosen": None,
                },
            },

            "day_actions": {
                "votes": [],
                "hang_yes":[],
                "hang_no":[],
                "hang_confir_msg_id": None,
                "last_hanged": None,
                "kamikaze_trigger": None,
                "kamikaze_take": None,
            },
        }

BAD_GUYS = {"mafia","don"}


async def punish_afk_night_players(game_id):
    game = games_state.get(game_id)
    if not game:
        return

    roles = game.get("roles", {})
    alive = set(game.get("alive", []))
    chat_id = game.get("meta", {}).get("chat_id")

    runtime = game.get("runtime", {})
    pending = set(runtime.get("pending_night", set()))  # tun tugaganda kim qolgan bo'lsa - action qilmadi

    afk = game.setdefault("afk", {})
    missed = afk.setdefault("missed_nights", {})
    kicked = afk.setdefault("kicked", set())

    # pending ichida o'lganlar bo'lib qolmasin
    pending = {pid for pid in pending if pid in alive}

    # bosmaganlarga +1
    for pid in pending:
        missed[pid] = missed.get(pid, 0) + 1

    # bosganlar reset (night_action role bo'lsa)
    for pid in list(missed.keys()):
        if pid in alive and roles.get(pid) in NIGHT_ACTION_ROLES and pid not in pending:
            missed[pid] = 0

    # 2 marta bo'lsa kick
    to_kick = [pid for pid, cnt in missed.items() if cnt >= 2 and pid in alive]

    if not to_kick:
        return

    # userlarni 1 ta query bilan olish
    users_qs = game.get("users_map", {})
    night_text= []
    for pid in to_kick:
        alive.discard(pid)
        kicked.add(pid)

        # state update
        if pid in game["alive"]:
            game["alive"].remove(pid)
        if pid not in game["dead"]:
            game["dead"].append(pid)
        if pid not in game.get("left", []):
            game.setdefault("left", []).append(pid)

        # counter reset
        missed[pid] = 0

        # guruhga xabar
        if chat_id:
            chat_id = int(chat_id)
            user = users_qs.get(pid)
            name = user.get("first_name") if user else str(pid)
            role = roles.get(pid, "Noma'lum")
            tg=get_lang_text(int(chat_id))
            if role == "don":
                new_don_id = promote_new_don_if_needed(game)
                if new_don_id:
                    await notify_new_don( game,new_don_id)
                    await send_safe_message(
                        chat_id=chat_id,
                        text=tg["don_become"]
                                )
            elif role == "com":
                new_com_id = promote_new_com_if_needed(game)
                if new_com_id:
                    await notify_new_com(  new_com_id)
                    await send_safe_message(
                                chat_id=chat_id,
                                text=tg["com_become"]
                            )
            
            role_label = get_role_labels_lang(chat_id).get(role, role)
            night_text.append(tg["punish_afk"].format(name=name, role_label=role_label,pid=pid))
    try:
        await send_safe_message(
        chat_id=int(chat_id),
        text="\n\n".join(night_text),
        parse_mode="HTML"
        )
    except Exception:
        pass
    






def prepare_hang_pending(game_id:int):
    game = games_state.get(game_id)
    if not game:
        return

    alive = set(game.get("alive", []))

    game.setdefault("runtime", {})
    game["runtime"]["pending_hang"] = set(int(x) for x in alive)
    game["runtime"]["hang_event"] = asyncio.Event()

    if not alive:
        game["runtime"]["hang_event"].set()

def mark_hang_done(game_id, voter_id: int):
    
    game = games_state.get(game_id)
    if not game:
        return

    runtime = game.get("runtime", {})
    pending = runtime.get("pending_hang")
    event = runtime.get("hang_event")

    if not pending or not event:
        return

    pending.discard(int(voter_id))

    if len(pending) == 0:
        event.set()


def prepare_night_pending(game_id: int):
    game = games_state.get(game_id)
    if not game:
        return

    roles = game.get("roles", {})
    alive = set(game.get("alive", []))

    pending = set()
    for tg_id in alive:
        role = roles.get(int(tg_id))
        if role in NIGHT_ACTION_ROLES:
            pending.add(int(tg_id))

    game.setdefault("runtime", {})
    game["runtime"]["pending_night"] = pending
    game["runtime"]["night_event"] = asyncio.Event()

    if not pending:
        game["runtime"]["night_event"].set()

def mark_night_action_done(game, tg_id: int):
    if not game:
        return

    runtime = game.get("runtime", {})
    pending = runtime.get("pending_night")
    event = runtime.get("night_event")

    if pending is None or event is None:
        return

    pending.discard(int(tg_id))

    if len(pending) == 0:
        event.set()

def prepare_confirm_pending(game_id: int, voted_user_id: int):
    game = games_state.get(game_id)
    if not game:
        return

    alive = set(int(x) for x in game.get("alive", []))

    # ✅ osilayotgan odam confirm bermaydi
    alive.discard(int(voted_user_id))

    game.setdefault("runtime", {})
    game["runtime"]["pending_confirm"] = alive
    game["runtime"]["confirm_event"] = asyncio.Event()

    if not alive:
        game["runtime"]["confirm_event"].set()
        
def mark_confirm_done(game_id, voter_id: int):
    game = games_state.get(game_id)

    runtime = game.get("runtime", {})
    pending = runtime.get("pending_confirm")
    event = runtime.get("confirm_event")

    if pending is None or event is None:
        return


    pending.discard(int(voter_id))

    if len(pending) == 0:
        event.set()

def get_hero_level(tg_id):
    try:
        return User.objects.get(telegram_id=tg_id).hero_level
    except:
        return 0


def get_most_voted_id(game_id: int):
    all_votes = games_state.get(game_id, {}).get("day_actions", {}).get("votes", [])
    if not all_votes:
        return False

    counts = Counter(all_votes)
    max_votes = max(counts.values())

    top = [v for v, c in counts.items() if c == max_votes]

    # tie
    if len(top) > 1:
        return False

    result = top[0]

    # hech kim osilmasin
    if result == "no_lynch":
        return False

    return result
def can_hang(game_id: int) -> bool:
    game = games_state.get(game_id)
    if not game:
        return False

    yes = len(game["day_actions"].get("hang_yes", []))
    no = len(game["day_actions"].get("hang_no", []))
    if yes > no:
        return "yes" , yes, no
    else:
        return "no" , yes, no
    
def get_mafia_members(game_id):
    game = games_state.get(int(game_id), {})
    roles_map = game.get("roles", {})
    alive = set(game.get("alive", []))

    members = []
    for tg_id, role in roles_map.items():
        if tg_id in alive and role in MAFIA_ROLES:
            members.append(tg_id)
    return members


def remove_prefix(text):
    return text.lstrip('@')

def parse_amount(text: str) -> int | None:
    if not text:
        return None

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None

    raw = parts[1].strip()
    raw = raw.replace(" ", "").replace(",", "").replace(".", "")
    if not raw.isdigit():
        return None

    amount = int(raw)
    if amount <= 0:
        return None

    return amount

async def process_santa_reward(target_id, callback):
    user = User.objects.filter(telegram_id=target_id).first()
    if not user:
        user = User.objects.create(
            telegram_id=target_id,
            lang='uz',
            first_name=callback.from_user.first_name,
            username=callback.from_user.username
        )
    user.coin += 20
    user.save()
    t= get_lang_text(int(target_id))
    await send_safe_message(
        chat_id=target_id,
        text=t["santa_gift"]
    )


def is_alive(game, tg_id: int) -> bool:
    return int(tg_id) in set(game.get("alive", []))



def find_game(game_id, tg_id,chat_id,user):
    init_game(game_id,chat_id)
    tg_id = int(tg_id)

    with lock:
        game = games_state[game_id]

        if tg_id in game["players"]:
            return {"message": "already_in"}
        max_players = game["meta"].get("max_players", 30)
        if len(game["players"]) >= max_players:
            return {"message": "full"}

        game["players"].append(tg_id)
        if game['meta']['game_type']=='turnir':
            game["users_map"][tg_id]={"first_name":user.first_name,"protection":1 if user.protection>=1 and user.is_protected else 0,"doc": 1 if user.docs>=1 and user.is_doc else 0,"hang_protect": 1 if user.hang_protect>=1 and user.is_hang_protected else 0,"geroy_protect": 1 if user.geroy_protection>=1 and user.is_geroy_protected else 0,"tg_id":tg_id,"hero":False}
        else:
            game["users_map"][tg_id]={"first_name":user.first_name,"protection":1 if user.protection>=1 and user.is_protected else 0,"doc": 1 if user.docs>=1 and user.is_doc else 0,"hang_protect": 1 if user.hang_protect>=1 and user.is_hang_protected else 0,"geroy_protect": 1 if user.geroy_protection>=1 and user.is_geroy_protected else 0,"tg_id":tg_id,"hero":user.is_hero and user.is_geroy_use}
        game["alive"].append(tg_id)
        if len(game["players"])==max_players:
            return {"message": "full"}

    return {"message": "joined"}



def create_main_messages(game_id, tg_id_for_lang):
    tg_ids = games_state.get(game_id, {}).get("players", [])
    t = get_lang_text(int(tg_id_for_lang))

    msg = f"{t['reg_started']}\n\n{t['reg_list']}\n"

    if not tg_ids:
        return msg + f"\n\n{t['no_players']}"

    users_map = games_state.get(game_id, {}).get("users_map", {})
    
    count = 0
    for tg_id in tg_ids:
        user = users_map.get(tg_id)
        if not user:
            continue
        msg += f'<a href="tg://user?id={tg_id}">{user.get("first_name")}</a>, '
        count += 1

    msg += f"\n\n{t['total'].format(count=count)}"
    return msg






def night_reset(game_id: int):
    with lock:
        game = games_state.get(game_id)
        if not game:
            return False

        game["meta"]["phase"] = "night"
        game["meta"]["night"] += 1

        # effects reset
        game["effects"]["protected"].clear()
        game["effects"]["blocked"].clear()
        game["effects"]["silenced"].clear()
        game["effects"]["poisoned"].clear()
        game["effects"]["no_hang"].clear()
        game["effects"]["advokat_masked"].clear()

        # visits reset
        game["visits"]["log"].clear()
        game["visits"]["invisible_visitors"].clear()

        # kills reset (night)
        game["kills"]["shooted"].clear()
        game["kills"]["special"].clear()

        # night actions reset
        na = game["night_actions"]

        na["don_kill_target"] = None
        na["mafia_vote"].clear()

        na["doc_target"] = None
        na["com_check_target"] = None
        na["com_shoot_target"] = None

        na["daydi_house"] = None
        na["daydi_seen"].clear()

        na["lover_block_target"] = None

        na["kaldun_target"] = None
        na["killer_target"] = []
        na["advokat_target"] = None
        na["spy_target"] = None
        na["lab_target"] = None
        na["drunk_target"] = None

        na["trap_house"] = None

        na["snyper_target"] = None
        na["arrow_target"] = None

        na["traitor_target"] = None

        na["snowball_target"] = None

        # pirate reset
        na["pirate"]["pirate_id"] = None
        na["pirate"]["target_id"] = None
        na["pirate"]["result"] = None

        # professor reset (boxes endi yo'q)
        na["professor"]["target_id"] = None
        na["professor"]["chosen"] = None

        rt = game.get("runtime", {})
        rt["night_event"] = None
        rt["pending_night"].clear()

        # message allowed default

    return True


def day_reset(game_id: int):
    with lock:
        game = games_state.get(game_id)
        if not game:
            return False

        game["meta"]["phase"] = "day"
        game["meta"]["day"] += 1

        # day kill reset
        game["kills"]["hanged"].clear()

        # day actions reset
        da = game["day_actions"]
        da["votes"].clear()
        da["hang_yes"].clear()
        da["hang_no"].clear()

        da["hang_confir_msg_id"] = None
        da["last_hanged"] = None
        da["kamikaze_trigger"] = None
        da["kamikaze_take"] = None

        rt = game.get("runtime", {})
        rt["hang_event"] = None
        rt["pending_hang"].clear()

        rt["confirm_event"] = None
        rt["pending_confirm"].clear()


    return True

def shuffle_roles(game_id) -> bool:
    game = games_state.get(game_id)
    if not game:
        return False

    players = game.get("players", [])
    num_players = len(players)

    base_roles = ROLES_BY_COUNT.get(num_players)
    if not base_roles:
        return False

    roles = base_roles.copy()
    random.shuffle(roles)

    roles_map = {}
    fixed_players = []

    for tg_id in players:
        user = User.objects.filter(telegram_id=tg_id).first()
        if not user or not user.is_active_role_use:
            continue

        user_roles = UserRole.objects.filter(user_id=user.id, quantity__gt=0)
        if not user_roles.exists():
            continue

        chosen_ur = None
        for ur in user_roles:
            if ur.role_key in roles:
                chosen_ur = ur
                break

        if not chosen_ur:
            continue

        roles_map[tg_id] = chosen_ur.role_key
        fixed_players.append(tg_id)

        UserRole.objects.filter(id=chosen_ur.id, role_key=chosen_ur.role_key, quantity__gt=0).update(quantity=DF("quantity") - 1)
        UserRole.objects.filter(id=chosen_ur.id, role_key=chosen_ur.role_key, quantity__lte=0).delete()
        active_role_used.append(tg_id)

        try:
            roles.remove(chosen_ur.role_key)
        except ValueError:
            pass

    remaining_players = [p for p in players if p not in fixed_players]
    random.shuffle(remaining_players)

    for tg_id, role in zip(remaining_players, roles):
        roles_map[tg_id] = role

    game["roles"] = roles_map
    return True


def add_visit(game: dict, visitor_id: int, house_id: int, invisible: bool = False):
    with lock:
        if not game:
            return

        game["visits"]["log"].append((int(visitor_id), int(house_id)))

        if invisible:
            game["visits"]["invisible_visitors"].add(int(visitor_id))





def check_bot_rights(bot_member,chat_id) -> str | bool:
    t= get_lang_text(int(chat_id))
    message_text = t["bot_no_rights"] 

    # Bot admin emas bo‘lsa — hammasini so‘raymiz
    if bot_member.status not in ("administrator", "creator"):
        return (
            message_text +
            t['bot_no_rights_add']
        )

    # Owner bo‘lsa hammasiga ruxsat bor
    if isinstance(bot_member, ChatMemberOwner):
        return False

    # Administrator bo‘lsa — rights tekshiramiz
    if isinstance(bot_member, ChatMemberAdministrator):
        no_all_rights = False

        if not bot_member.can_delete_messages:
            message_text += t['bot_no_rights_delete']
            no_all_rights = True

        if not bot_member.can_restrict_members:
            message_text += t['bot_no_rights_restrict']
            no_all_rights = True

        if not bot_member.can_pin_messages:
            message_text += t['bot_no_rights_pin']
            no_all_rights = True

        if not no_all_rights:
            return False

        return message_text

    return False

def get_mafia_kill_target(night_actions):
    don_target = night_actions.get("don_kill_target")
    mafia_votes = night_actions.get("mafia_vote", [])  # list

    targets = mafia_votes.copy()

    if don_target:
        targets.append(don_target)  # 1x
        targets.append(don_target)  # 2x ✅

    if not targets:
        return None

    counts = Counter(targets)
    max_votes = max(counts.values())
    top = [t for t, c in counts.items() if c == max_votes]

    # agar durang bo'lsa None
    if len(top) != 1:
        return don_target if don_target else mafia_votes[0] if mafia_votes else None

    return top[0]

def get_first_name_from_players(tg_id):
    user = User.objects.filter(telegram_id=tg_id).only("telegram_id", "first_name").first()
    if user:
        return user.first_name
    return str(tg_id)

def has_link(text: str) -> bool:
    if not text:
        return False
    return bool(LINK_RE.search(text))



def role_label(role_key: str,chat_id:int):
    return get_role_labels_lang(chat_id).get(role_key, role_key or "")
        
        
def kill(game, tg_id: int):
    if not tg_id:
        return
    if not game:
        return
    tg_id = int(tg_id)
    if tg_id in game["alive"]:
        game["alive"].remove(tg_id)
    if tg_id not in game["dead"]:
        game["dead"].append(tg_id)
    
def compute_daydi_seen(game):
    night_actions = game["night_actions"]

    daydi_house = night_actions.get("daydi_house")
    if not daydi_house:
        night_actions["daydi_seen"] = []
        return []

    daydi_house = int(daydi_house)
    invisible = game["visits"]["invisible_visitors"]
    visits = game["visits"]["log"]

    seen = []
    for visitor_id, house_id in visits:
        visitor_id = int(visitor_id)
        house_id = int(house_id)

        # Faqat daydi tanlagan uyga kelganlar
        if house_id != daydi_house:
            continue

        # Ko‘rinmaydigan visitorlar
        if visitor_id in invisible:
            continue

        # Uy egasini o‘zi ko‘rmaydi
        if visitor_id == daydi_house:
            continue

        if visitor_id not in seen:
            seen.append(visitor_id)

    night_actions["daydi_seen"] = seen
    return seen

def get_alive_role_id(game, role_key: str):
    roles = game.get("roles", {})
    for tg_id, r in roles.items():
        if r == role_key :
            return tg_id
    return None

def get_alive_role_ids(game, role_key: str):
    roles = game.get("roles", {})
    alive = set(game.get("alive", []))
    return [tg_id for tg_id, r in roles.items() if r == role_key and tg_id in alive]


def get_visible_role_for_com(game, target_id: int, users_map=None) -> str:
    roles = game.get("roles", {})
    effects = game.get("effects", {})

    real_role = roles.get(int(target_id))

    if not real_role:
        return "peace"

    # 1) advokat mask (agar target mafiyadan bo'lsa)
    adv_masked = effects.get("advokat_masked", {})
    if int(target_id) in adv_masked:
        return "peace"

    # 2) shop protection: mafia/solo bo'lsa tinch ko'rinsin
    if users_map:
        user = users_map.get(int(target_id))
        if user and user.get("docs", 0) > 0 and real_role in (MAFIA_ROLES_LAB | SOLO_ROLES):
            user_qs = User.objects.filter(telegram_id=int(target_id)).first()
            user["docs"] -= 1
            user_qs.docs -= 1
            user_qs.save(update_fields=["docs"])
            # Assuming there's a mechanism to save the updated user data back to the database or game state
            return "peace"

    return real_role


def promote_new_don_if_needed(game: dict):
    roles = game.get("roles", {})
    alive = set(game.get("alive", []))

    alive_don = any(roles.get(tg) == "don" for tg in alive)
    if alive_don:
        return None

    mafia_candidates = [
        tg for tg in alive
        if roles.get(tg) in ("mafia",)   # faqat mafia ichidan
    ]

    if not mafia_candidates:
        return None

    new_don_id = mafia_candidates[0]  # xohlasangiz random ham qilsa bo'ladi
    roles[new_don_id] = "don"
    game["roles"] = roles
    return new_don_id


async def notify_new_don(game: dict, new_don_id: int):
    roles = game.get("roles", {})
    alive = set(game.get("alive", []))
    user_map = game.get("users_map", {})    
    t = get_lang_text(int(new_don_id))

    mafia_members = [
        tid for tid in alive
        if roles.get(tid) in MAFIA_ROLES
    ]   
    
    await send_safe_message(
        chat_id=int(new_don_id),
        text=t['don_killed'],
    )

    for member_id in mafia_members:
        if member_id == int(new_don_id):
            continue
        t = get_lang_text(int(member_id))
        try:
            user = user_map.get(int(new_don_id))
            await send_safe_message(
                chat_id=int(member_id),
                text=t['don_notify'].format(new_don_id=new_don_id, first_name=user.get("first_name","")),
                parse_mode="HTML"
            )
        except Exception:
            pass




def promote_new_com_if_needed(game: dict):
    roles = game.get("roles", {})
    alive = set(game.get("alive", []))

    alive_com = any(roles.get(tg) == "com" for tg in alive)
    if alive_com:
        return None

    # serg tirik bo'lsa o'sha komissar bo'ladi
    serg_id = next((tg for tg in alive if roles.get(tg) == "serg"), None)
    if not serg_id:
        return None

    roles[int(serg_id)] = "com"
    game["roles"] = roles
    return int(serg_id)

async def notify_new_com(new_com_id: int):
    # serjantning o'ziga
    t= get_lang_text(int(new_com_id))
    try:
        await send_safe_message(
            chat_id=int(new_com_id),
            text=t['com_killed'],
        )
        
    except Exception:
        pass



def traitor_swap_roles(game: dict):
    roles = game.get("roles", {})
    alive = set(game.get("alive", []))
    night_actions = game.get("night_actions", {})

    traitor_id = next((tid for tid, r in roles.items() if r == "traitor" and tid in alive), None)
    if not traitor_id:
        return None

    target_id = night_actions.get("traitor_target")
    if not target_id:
        return None

    target_id = int(target_id)

    if target_id not in alive:
        return None

    if target_id == int(traitor_id):
        return None

    # swap
    traitor_role = roles.get(int(traitor_id))
    target_role = roles.get(int(target_id))

    if not target_role:
        return None

    roles[int(traitor_id)] = target_role
    roles[int(target_id)] = traitor_role

    game["roles"] = roles
    return int(traitor_id), int(target_id), target_role



async def hero_day_actions(game_id: int):
    game = games_state.get(int(game_id))
    if not game:
        return

    users_map = game.get("users_map", {})
    roles = game.get("roles", {})
    meta = game.get("meta", {})
    chat_id = meta.get("chat_id")
    day = meta.get("day")
    game["hero"].setdefault("notified", set())

    for tg_id, user in users_map.items():
        tg_id = int(tg_id)
        if tg_id not in game.get("alive", []):
            continue
        if not user.get("hero", False):
            continue

        if tg_id in game["hero"]["used"]:
            continue


        role = roles.get(tg_id)
        t = get_lang_text(tg_id)
        if role in ["don", "com", "snyper"]:
            await send_safe_message(
                chat_id=tg_id,
                text=t['hero_day_action'],
                reply_markup=use_hero_inline_btn(
                    attack = True,
                    game_id=int(game_id),
                    chat_id=chat_id,
                    tg_id=tg_id,
                    day=day
                )
            )
        else:
            await send_safe_message(
                chat_id=tg_id,
                text=t['hero_protect'],
                reply_markup=use_hero_inline_btn(
                    attack = False,
                    game_id=int(game_id),
                    chat_id=chat_id,
                    tg_id=tg_id,
                    day=day
                )
            )

        # ✅ belgilab qo‘yamiz
        game["hero"]["notified"].add(tg_id)


async def apply_night_actions(game_id: int):
    game = games_state.get(game_id)
    if not game:
        return

    game.setdefault("allowed_to_send_message", [])

    night_actions = game.get("night_actions", {})
    effects = game.get("effects", {})
    roles = game.get("roles", {})

    chat_id = game.get("meta", {}).get("chat_id")
    if not chat_id:
        return

    alive_ids = game.get("alive", [])
    alive_users_map = game.get("users_map", {})
    
    def uname(tg_id):
        user = alive_users_map.get(int(tg_id))
        return user.get("first_name") if user else str(tg_id)

    protected = effects.setdefault("protected", {})

    doc_id = get_alive_role_id(game, "doc")
    if doc_id:
        doc_target = night_actions.get("doc_target")
        if doc_target and is_alive(game, doc_target):
            protected[int(doc_target)] = "doc"

  
    kill_intents = {}

    def add_intent(target_id, by_role, priority=1):
        if not target_id:
            return
        if isinstance(target_id, dict):
            return
        try:
            target_id = int(target_id)
        except (TypeError, ValueError):
            return
        if not is_alive(game, target_id):
            return
        kill_intents.setdefault(target_id, []).append((by_role, priority))

    mafia_alive = any(roles.get(tg) in {"don", "mafia"} for tg in alive_ids)
    if mafia_alive:
        mafia_target = get_mafia_kill_target(night_actions)
        if  mafia_target:
            add_intent(mafia_target, "don", priority=1)
            mafia_ids = get_mafia_members(game_id)
            mafia_target_name = uname(mafia_target)
            for mafia in mafia_ids:
                t= get_lang_text(int(mafia))
                await send_safe_message(
                chat_id=int(mafia),
                text=t['mafia_target'].format(mafia_target=mafia_target_name)
            )

    killer_id = get_alive_role_id(game, "killer")
    if killer_id:
        for target_id in night_actions.get("killer_target", []):
            add_intent(target_id, "killer", priority=1)

    com_id = get_alive_role_id(game, "com")
    if com_id:
        add_intent(night_actions.get("com_shoot_target"), "com", priority=1)
    drunk_id = get_alive_role_id(game, "drunk")
    if drunk_id:
        add_intent(night_actions.get("drunk_target"), "drunk", priority=4)
        if random.random() < 0.4:
                add_intent(drunk_id, "💊 O'zi", priority=4)

    snowball_id = get_alive_role_id(game, "snowball")
    if snowball_id:
        add_intent(night_actions.get("snowball_target"), "snowball", priority=1)

    arrow_id = get_alive_role_id(game, "arrow")
    if arrow_id:
        add_intent(night_actions.get("arrow_target"), "arrow", priority=1)

    snyper_id = get_alive_role_id(game, "snyper")
    if snyper_id:
        add_intent(night_actions.get("snyper_target"), "snyper", priority=99)
    professor_id = get_alive_role_id(game, "professor")
    if professor_id:
        professor_data = night_actions.get("professor", {})
        prof_target = professor_data.get("target_id")
        prof_chosen = professor_data.get("chosen")
        if prof_target and prof_chosen == "die":
            add_intent(prof_target, "professor", priority=1)

    pirate_id = get_alive_role_id(game, "pirate")
    pirate_data = night_actions.get("pirate", {})
    if pirate_id and pirate_data and pirate_data.get("result") in ("no", "no_money"):
        add_intent(pirate_data.get("target_id"), "pirate", priority=1)

    lab_id = get_alive_role_id(game, "lab")
    if lab_id:
        lab_target = night_actions.get("lab_target")
        if lab_target and is_alive(game, lab_target):
            if roles.get(int(lab_target)) in MAFIA_ROLES:
                protected[int(lab_target)] = "lab"
            else:
                add_intent(lab_target, "lab", priority=2)

    kaldun_id = get_alive_role_id(game, "kaldun")
    if kaldun_id:
        kaldun_target = night_actions.get("kaldun_target")
        if kaldun_target and is_alive(game, kaldun_target):
            if roles.get(int(kaldun_target)) in PEACE_ROLES:
                protected[int(kaldun_target)] = "kaldun"
            else:
                add_intent(kaldun_target, "kaldun", priority=2)

    trap_id = get_alive_role_id(game, "trap")
    if trap_id:
        trap_house = night_actions.get("trap_house")
        if trap_house:
            trap_house = int(trap_house)
            visitors = [v for (v, h) in game.get("visits", {}).get("log", []) if int(h) == trap_house]
            if visitors:
                first = int(visitors[0])
                if roles.get(first) != "trap":
                    add_intent(first, "trap", priority=10)
     

    dead_tonight = []
    saved_tonight = []
    lover_target = night_actions.get("lover_block_target")
    hero_data = game.get("hero", {})
    for target_id, intents in kill_intents.items():
        if target_id is None:
            continue
        
        intents.sort(key=lambda x: x[1], reverse=True)
        killer_by, pr = intents[0]
        role = roles.get(int(target_id))
        killer_id = get_alive_role_id(game, killer_by)
        if lover_target and int(lover_target) == int(target_id):
            continue

        target_user = alive_users_map.get(int(target_id))
        hero_used = game.setdefault("hero_used", {})
        if target_user and target_user.get("hero", False):
            if not hero_used.get(target_id) and target_id in hero_data.get("self_protect", set()):
                hero_used[target_id] = True
                t= get_lang_text(int(target_id))
                tu = get_lang_text(int(chat_id))
                await send_safe_message(
                    chat_id=int(target_id),
                    text=t['hero_half_protect'],
                    parse_mode="HTML"
                )
                
                target_name = uname(target_id)
                await send_safe_message(
                    chat_id=chat_id,
                    text=tu['hero_saved'].format(target_name=target_name,target_id=target_id),
                    parse_mode="HTML"
                )
                continue
        if role == "ghost" and not killer_by == "snyper":
            continue
        if role == "arrow" and  killer_by == "com":
            continue
            
        if killer_by == "snyper":
            kill(game, target_id)
            dead_tonight.append((target_id, killer_by))
            continue

        if target_id in protected:
            saved_tonight.append((target_id, protected[target_id], killer_by))
            continue
        
        if target_user and target_user.get("protection", 0) > 0:
            target_user_qs = User.objects.filter(telegram_id=int(target_id)).first()
            target_user["protection"] -= 1
            target_user_qs.protection -= 1
            target_user_qs.save(update_fields=["protection"])

            saved_tonight.append((target_id, "himoya", killer_by))
            continue
        


        if roles.get(int(target_id)) == "kam":
            if killer_id and is_alive(game, killer_id):
                kill(game, killer_id)
                dead_tonight.append((killer_id, "kam"))


        kill(game, target_id)
        dead_tonight.append((target_id, killer_by))
    night_texts = []
    for target_id, killer_by in dead_tonight:
        if not isinstance(target_id, int):
            continue

        target_role = roles.get(int(target_id))
        killer_role_label = role_label(killer_by, chat_id)
        victim_role_label = role_label(target_role, chat_id)
        target_name = uname(target_id)
        t = get_lang_text(int(chat_id))
        night_texts.append(
               t['night_kills'].format(
                    target_name=target_name,
                    victim_role_label=victim_role_label,
                    killer_role_label=killer_role_label,
                    target_id=target_id)
            )
            
        
        if target_role == "don":
            new_don_id = promote_new_don_if_needed(game)
            if new_don_id:
                await notify_new_don( game, new_don_id)
                await send_safe_message(
                    chat_id=chat_id,
                    text=t['don_become']
                )
                
        if target_role == "com":
            new_com_id = promote_new_com_if_needed(game)
            if new_com_id:
                await notify_new_com(new_com_id)
                await send_safe_message(
                    chat_id=chat_id,
                    text=t['com_become']
                )

        t = get_lang_text(int(target_id))
        await send_safe_message(
            chat_id=int(target_id),
            text=t['u_killed'],
            parse_mode="HTML"
        )

        if int(target_id) not in game["allowed_to_send_message"]:
            game["allowed_to_send_message"].append(int(target_id))
            last_wishes[int(target_id)] = {
                "chat_id": chat_id,
                "target_name": target_name,
                "victim_role_label": victim_role_label
            }
            
    if night_texts:
        await send_safe_message(
            chat_id=chat_id,
            text="\n\n".join(night_texts),
            parse_mode="HTML"
        )           
            
    for target_id, protector_by, killer_by in saved_tonight:
        protector_role_label = role_label(protector_by,int(target_id))
        t = get_lang_text(int(target_id))
        await send_safe_message(
                chat_id=int(target_id),
                text=t['u_saved'].format(protector_role_label=protector_role_label),
                parse_mode="HTML"
            )
            
    
    com_id = get_alive_role_id(game, "com")
    serg_id = get_alive_role_id(game, "serg")
    com_check_target = night_actions.get("com_check_target")

    if com_id and com_check_target and is_alive(game, com_id):
        target_user = alive_users_map.get(int(com_check_target))
        target_name = target_user.get("first_name") if target_user else str(com_check_target)

        visible_role_key = get_visible_role_for_com(game, int(com_check_target), alive_users_map)
        visible_role_text = get_role_labels_lang(int(com_check_target)).get(visible_role_key, "👨🏼 Tinch axoli")
        com= get_lang_text(int(com_check_target))
        try:
            await send_safe_message(
                chat_id=int(com_check_target),
                text=com["someone_interested"]
            )
            target_lang= get_lang_text(int(com_id))
            text = target_lang['com_check_result'].format(
                target_name=target_name,
                visible_role_text=visible_role_text,
                com_check_target=com_check_target
            )
            await send_safe_message(
                chat_id=int(com_id),
                text=text,
                parse_mode="HTML"
            )
            if serg_id and is_alive(game, serg_id):
                await send_safe_message(
                    chat_id=int(serg_id),
                    text=text,
                    parse_mode="HTML"
                )
        except Exception:
            pass
        
    spy_id = get_alive_role_id(game, "spy")
    spy_target = night_actions.get("spy_target")

    if spy_id and spy_target and is_alive(game, spy_id):
        target_user = alive_users_map.get(int(spy_target))
        target_name = target_user.get("first_name") if target_user else str(spy_target)

        real_role_key = roles.get(int(spy_target))
        real_role_text = get_role_labels_lang(int(spy_target)).get(real_role_key, "Unknown")

        try:
            await send_safe_message(
                chat_id=int(spy_target),
                text=t["someone_interested"]
            )
            
            mafia_members = get_mafia_members(game_id)
            for member_id in mafia_members:
                t = get_lang_text(int(member_id))
                if member_id == int(spy_id):
                    continue
                await send_safe_message(
                    chat_id=int(member_id),
                    text=t['spy_notify'].format(
                        target_name=target_name,
                        real_role_text=real_role_text,
                        spy_target=spy_target
                    ),
                    parse_mode="HTML"
                )
            t= get_lang_text(int(spy_id))
            await send_safe_message(
                chat_id=int(spy_id),
                text=t['spy_found'].format(
                        target_name=target_name,
                        real_role_text=real_role_text,
                        spy_target=spy_target
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    


    
    daydi_id = get_alive_role_id(game, "daydi")
    if daydi_id:
        daydi_seen = compute_daydi_seen(game)     
        daydi_house_id = night_actions.get("daydi_house")
        if daydi_house_id:
            daydi_house_id = int(daydi_house_id)
            house_owner = uname(daydi_house_id)

            lines = []
            for vid in daydi_seen:
                role = roles.get(int(vid))
                lines.append(f"{role_label(role, daydi_id)} <a href='tg://user?id={vid}'>{uname(vid)}</a>")
            t = get_lang_text(int(daydi_id))
            if lines:
                text =t['daydi_report'].format(
                    house_owner=house_owner,
                    daydi_house_id=daydi_house_id,
                    visitors=" ".join(lines)
                )
            else:
                text = (
                    t['daydi_report_no_visitors'].format(
                        house_owner=house_owner,
                        daydi_house_id=daydi_house_id
                    )
                )

            await send_safe_message(
                chat_id=int(daydi_id),
                text=text,
                parse_mode="HTML"
            )
    
    if lover_target and is_alive(game, lover_target):
        t = get_lang_text(int(lover_target))
        try:
            await send_safe_message(
                chat_id=int(lover_target),
                text=t['lover_blocked'],
                parse_mode="HTML"
            )
        except Exception:
            pass
    swap_result = traitor_swap_roles(game)
    if swap_result:
        traitor_id, target_id, new_role = swap_result

        try:
            new_name = get_role_labels_lang(int(traitor_id)).get(new_role, new_role)
            await send_safe_message(
                chat_id=traitor_id,
                text=t['traitor_changed'].format(new_name=new_name)
            )
        except Exception:
            pass

        try:
            t= get_lang_text(int(target_id))
            await send_safe_message(
                chat_id=target_id,
                text=t['traitor_swapped']
            )
        except Exception:
            pass

                
def get_game_by_chat_id(chat_id: int):
    chat_id = int(chat_id)
    for game in games_state.values():
        if game.get("meta", {}).get("chat_id") == chat_id:
            return game
    return False    
                
                
def get_alive_teams(game):
    roles = game.get("roles", {})
    alive = game.get("alive", [])

    mafia = []
    peace = []
    solo = []

    for tg_id in alive:
        r = roles.get(tg_id)
        if r in MAFIA_ROLES_LAB:
            mafia.append(tg_id)
        elif r in PEACE_ROLES:
            peace.append(tg_id)
        elif r in SOLO_ROLES:
            solo.append(tg_id)

    return mafia, peace, solo
def check_game_over(game_id: int) -> str | None:
    game = games_state.get(game_id)
    if not game:
        return None

    alive = game.get("alive", [])
    if not alive:
        return "draw"

    mafia_ids, peace_ids, solo_ids = get_alive_teams(game)

    mafia = len(mafia_ids)
    peace = len(peace_ids)
    solo  = len(solo_ids)
    alive_count = mafia + peace + solo

    # =========================
    # 🔥 1. SOLO MAXSUS HOLATLAR
    # =========================

    # Faqat solo qolsa
    if solo > 0 and mafia == 0 and peace == 0:
        return "solo"

    # 1 peace + 1 solo
    if alive_count == 2 and peace == 1 and solo == 1:
        return "solo"

    # 1 mafia + 1 solo
    if alive_count == 2 and mafia == 1 and solo == 1:
        return "mafia"

    # =========================
    # 🔥 2. MAFIA PARITY QOIDASI (ENG MUHIM)
    # =========================
    # Mafia soni tinchlardan kam emas bo‘lsa — mafia yutadi
    if mafia > 0 and mafia >= peace and solo == 0:
        return "mafia"

    # 3 kishidan kam va mafia bor
    if alive_count < 3 and mafia > 0:
        return "mafia"

    # =========================
    # 🔥 3. TINCHLAR YUTISHI
    # =========================
    if peace > 0 and mafia == 0 and solo == 0:
        return "peace"

    # =========================
    # 🔥 4. Aralash holat — o‘yin davom etadi
    # =========================
    return None


async def is_user_in_chat( user_id: int) -> bool:
    chat_id = "@MafiaRedDonOfficial"
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status not in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
        )
    except Exception:
        return False

async def stop_game_if_needed(game_id: int):
    game_id = int(game_id)
    game_state = games_state.get(game_id)
    if not game_state:
        return False

    winner_key = check_game_over(game_id)
    if not winner_key:
        return False

    game_state["meta"]["phase"] = "ended"
    game_state["meta"]["winner"] = winner_key
    chat_id = game_state.get("meta", {}).get("chat_id")

    final_text, winners, loosers = await build_final_game_text(game_id, winner_key)

    try:
        await send_safe_message(chat_id=chat_id, text=final_text, parse_mode="HTML")
    except:
        pass

    game = Game.objects.filter(id=game_id).first()
    if game:
        game.is_active = False
        game.is_active_game = False
        game.is_ended = True
        game.save(update_fields=["is_active", "is_active_game", "is_ended"])

    all_players = game_state.get("players", [])
    roles_map = game_state.get("roles", {})

    users_qs = User.objects.filter(telegram_id__in=all_players)
    users_map = {u.telegram_id: u for u in users_qs}
    users = [users_map[int(tg)] for tg in all_players if int(tg) in users_map]

    # 🔥 Telegram group membershipni parallel tekshirish
    followers = await asyncio.gather(
        *(is_user_in_chat( u.telegram_id) for u in users)
    )
    followers_map = {u.telegram_id: f for u, f in zip(users, followers)}

    dm_payload = []

    with transaction.atomic():
        records = []
        users_to_update = []

        for u in users:
            t = get_lang_text(int(u.telegram_id))
            is_winner = u.telegram_id in winners
            is_group_follower = followers_map.get(u.telegram_id, False)
            last_wishes.pop(u.telegram_id, None)

            reward = (
                110 if is_winner and is_group_follower else
                55 if is_winner else
                50 if is_group_follower else
                25
            )

            u.coin += reward
            users_to_update.append(u)

            records.append(
                MostActiveUser(
                    user=u,
                    group=int(chat_id),
                    games_played=1,
                    games_win=1 if is_winner else 0,
                )
            )

            role_key = roles_map.get(u.telegram_id)
            role_text = get_role_labels_lang(int(u.telegram_id)).get(role_key, "Unknown")
            user_link = f"<a href='tg://user?id={u.telegram_id}'>{u.first_name}</a>"

            if is_winner:
                text = t['win_report'].format(
                    reward=reward,
                    user_link=user_link,
                    role_text=role_text,
                    coins=u.coin,
                    stones=u.stones,
                    protection=u.protection,
                    docs=u.docs
                )
            else:
                text = t['lose_report'].format(
                    reward=reward,
                    user_link=user_link,
                    role_text=role_text,
                    coins=u.coin,
                    stones=u.stones,
                    protection=u.protection,
                    docs=u.docs
                )

            dm_payload.append((u.telegram_id, text))

        User.objects.bulk_update(users_to_update, ["coin"])
        MostActiveUser.objects.bulk_create(records)

    # DM yuborish
    for user_id, text in dm_payload:
        try:
            await send_safe_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                reply_markup=cart_inline_btn(user_id)
            )
        except:
            pass

    # Cleanup
    chat_id_game_id.pop(chat_id, None)
    games_state.pop(game_id, None)
    writing_allowed_groups.pop(chat_id, None)
    game_tasks.pop(game_id, None)

    game_settings = GameSettings.objects.first()
    if game_settings and game_settings.begin_after_end:
        from mafia_bot.handlers.command_handlers import auto_begin_game
        await auto_begin_game(chat_id)

    return True


def format_duration(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m} min. {s} sek."

async def build_final_game_text(game_id: int, winner_key: str) -> str:
    game = games_state.get(game_id)
    if not game:
        return "O'yin tugadi."

    roles = game.get("roles", {})
    alive = set(game.get("alive", []))
    all_players = game.get("players", [])
    hanged = set(game.get("hanged", []))
    chat_id = int(game.get("meta", {}).get("chat_id"))
    created_at = int(game.get("meta", {}).get("created_at", int(time.time())))
    duration = int(time.time()) - created_at

    winner_team_roles = (
        PEACE_ROLES if winner_key == "peace"
        else MAFIA_ROLES_LAB if winner_key == "mafia"
        else SOLO_ROLES if winner_key == "solo"
        else set()
    )

    winner_label = get_winner_label_lang(chat_id).get(winner_key, winner_key)

    # players order bo'yicha ismni saqlab chiqarish uchun list ishlatamiz
    ids_in_order = [tg_id for tg_id in all_players if tg_id in roles]

    # userlarni 1 query bilan olamiz
    users_map = game.get("users_map", {})

    winners = []
    others = []
    winners_list = []
    loosers_list = []
    for tg_id in ids_in_order:
        role_key = roles.get(tg_id)
        user = users_map.get(tg_id)

        name = user.get("first_name") if user else str(tg_id)
        role_txt = role_label(role_key,chat_id)

        line = f"    {name} - {role_txt}"

        # ✅ Winner bo'lish sharti: alive + winner team
        if tg_id in alive and role_key in winner_team_roles:
            winners.append(line)
            winners_list.append(tg_id)
        else:
            others.append(line)
            loosers_list.append(tg_id)
            
    suid_player = next((uid for uid, role in roles.items() if role == "suid"), None)

    if suid_player and suid_player in hanged:
        user = users_map.get(suid_player)
        name = user.get("first_name") if user else str(suid_player)
        role_txt = role_label("suid", chat_id)

        line = f"    {name} - {role_txt}"

        if line not in winners:
            winners.append(line)
            winners_list.append(suid_player)

        if suid_player in loosers_list:
            loosers_list.remove(suid_player)
            
    t = get_lang_text(chat_id)
    text = (
        f"{t['title']}\n"
        f"{t['winner'].format(winner=winner_label)}\n\n"
        f"{t['winners']}\n"
    )

    text += "\n".join(winners) if winners else t["no_one"]

    text += f"\n\n{t['others']}\n"

    text += "\n".join(others) if others else t["no_one"]

    text += f"\n\n{t['duration'].format(time=format_duration(duration))}"
    return text, winners_list, loosers_list

async def is_group_admin( chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        return False
    
    
async def mute_user(chat_id: int, user_id: int, seconds: int = 45):
    until_date = int(time.time()) + seconds

    await bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        permissions=ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        ),
        until_date=until_date
    )
    
def is_player_in_game( tg_id: int) -> bool:
    tg_id = int(tg_id)
    for game in games_state.values():
        players = game.get("players", [])
        if tg_id in players:
            return True
    return False
    
def get_game_lock(chat_id):
    if chat_id not in game_locks:
        game_locks[chat_id] = asyncio.Lock()
    return game_locks[chat_id]

    
def get_week_range(today):
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=7)
    return start, end


def get_month_range(today):
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


async def send_safe_message(chat_id: int, text: str, **kwargs) -> Message | None:
    try:
        return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except Exception:
        return None
    
    
def get_lang(tg_id: int) -> str:
    tg_id = int(tg_id)
    lang = USER_LANG_CACHE.get(tg_id)
    if lang:
        return lang
    
    if tg_id > 0:
        user_type ="user"
    else:
        user_type ="group"
    if user_type == "group":
        group = GroupTrials.objects.filter(group_id=tg_id).only("lang").first()
        if group:
            USER_LANG_CACHE[tg_id] = group.lang
            return group.lang
    else: 
        user = User.objects.filter(telegram_id=tg_id).only("lang").first()
        if user:
            USER_LANG_CACHE[tg_id] = user.lang
            return user.lang

    return "uz"


def get_lang_text(tg_id: int) -> dict:
    return LANG_TEXTS.get(get_lang(tg_id), uz_texts)


def get_role_labels_lang(tg_id: int) -> dict:
    return ROLE_LABELS.get(get_lang(tg_id), ROLE_LABELS["uz"])

def get_roles_choices_lang(tg_id: int):
    return LANG_TEXTS.get(get_lang(tg_id), uz_texts)["ROLES_CHOICES"]


def get_actions_lang(tg_id: int) -> dict:
    return ACTIONS.get(get_lang(tg_id), ACTIONS["uz"])


def get_winner_label_lang(tg_id: int) -> dict:
    return WINNER_LABELS.get(get_lang(tg_id), WINNER_LABELS["uz"])


def get_description_lang(tg_id: int) -> dict:
    return DESCRIPTIONS.get(get_lang(tg_id), DESCRIPTIONS["uz"])
