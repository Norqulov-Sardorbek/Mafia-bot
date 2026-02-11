import time
import random
import asyncio
from aiogram import F
from dispatcher import dp,bot
from datetime import timedelta
from django.db.models import Sum  
from django.utils import timezone
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from mafia_bot.state import CredentialsState
from aiogram.types import Message,LabeledPrice
from django.contrib.auth.hashers import check_password
from mafia_bot.handlers.game_handler import run_game_in_background
from mafia_bot.handlers.callback_handlers import begin_instance_callback
from mafia_bot.models import Game, GroupTrials, MostActiveUser,User,BotMessages,GameSettings, UserRole,default_end_date,BotCredentials,LoginAttempts
from mafia_bot.storage import GameStorage
from mafia_bot.utils import last_wishes,team_chat_sessions,game_tasks,group_users,stones_taken,gsend_taken,giveaways,notify_users,active_role_used,writing_allowed_groups
from mafia_bot.handlers.main_functions import (MAFIA_ROLES, find_game,create_main_messages, get_lang_text,
                                               kill, notify_new_don, promote_new_com_if_needed,get_game_lock,
                                               promote_new_don_if_needed,  shuffle_roles ,check_bot_rights,
                                               role_label,is_group_admin,mute_user,has_link,parse_amount,get_game_by_chat_id,get_description_lang,get_role_labels_lang,
                                               send_safe_message,notify_new_com)
from mafia_bot.buttons.inline import (admin_inline_btn, back_btn, claim_chanel_olmos_inline_btn, giveaway_join_btn, group_profile_inline_btn, join_game_btn, 
                                      start_inline_btn, go_to_bot_inline_btn, cart_inline_btn, take_gsend_stone_btn,
                                      take_stone_btn,stones_to_premium_inline_btn,language_keyboard)


@dp.message(Command("start"), StateFilter(None))
async def start(message: Message) -> None:
    tg_id = message.from_user.id
    t= get_lang_text(tg_id)
    user = User.objects.filter(telegram_id=tg_id).first()
    if user is None:
        await message.answer(
            text=t['greating_message'].format(first_name=message.from_user.first_name),
            parse_mode="HTML",
            reply_markup=language_keyboard()
        )
        return
    if message.from_user.first_name != user.first_name or message.from_user.username != user.username:
        user.first_name = message.from_user.first_name
        user.username = message.from_user.username
        user.save(update_fields=["first_name","username"])
    if ' ' in message.text and message.chat.type == "private": 
        args = message.text.split(' ')[1]
        if args == "true":
            return
        elif args.startswith("instance_"):
            chat_id = args.split('_')[1]
            await begin_instance_callback(message,chat_id)
            return
        elif args.startswith("paym_"):
            chat_id = args.split('_')[1]
            olmos = args.split('_')[2]
            star = args.split('_')[3]
            await olmos_star_handler(message, olmos,star, chat_id)
            return
        elif args.startswith("stone_"):
            chat_id = int(args.split('_')[1])
            await stones_to_premium(message,chat_id)
            return
        elif args.startswith("claim_"):
            username = args.split('_')[1]
            await claim_channel_olmos(message,username)
            return
            
            
        game = Game.objects.filter(uuid=args,is_active_game=True,is_started=False).first()
        if not game :
            await message.reply(text=t['game_not_active'])
            return
        # if is_player_in_game(tg_id):
        #     await message.reply(text=t['already_in_another_game'])
        #     return
        
        result = find_game(game.id,tg_id,game.chat_id,user)
        if result.get("message") == "already_in":
            await message.reply(text=t['already_in_game'])
        elif result.get("message") in ("joined","full"):
            trial = GroupTrials.objects.filter(group_id=game.chat_id).first()
            group_name = trial.group_name if trial else ""
            await message.reply(text=t['joined_game'].format(group_name=group_name))
            result_2 = create_main_messages(game.id,game.chat_id)
            bot_message=BotMessages.objects.filter(game_id=game.id,is_main=True,is_deleted=False).first()
            if bot_message:
                try:
                    await bot.edit_message_text(chat_id=game.chat_id,message_id=bot_message.message_id,text=result_2,reply_markup=join_game_btn(str(game.uuid),game.chat_id))
                except Exception as e:
                    pass
        if result.get("message") == "full":
            await stop_registration(game_id=game.id)
        return
    
            
    
    if message.chat.type == "private":
        if user.role == "admin":
            await message.answer("Salom\n\n👮 Siz Mafia botning admin panelidasiz.",reply_markup=admin_inline_btn())
            return
       
        first_name=message.from_user.first_name
        await message.answer(
    text=t['greating_message'].format(first_name=first_name),
    parse_mode="HTML",
    reply_markup=start_inline_btn(message.from_user.id)
        )
    elif message.chat.type in ("group", "supergroup"):
        t = get_lang_text(message.chat.id)
        await message.delete()
        if " " in message.text and message.text.split(' ')[1] == "true":
            game_settings = GameSettings.objects.filter(group_id = message.chat.id).first()
            if not game_settings:
                game_settings = GameSettings.objects.create(group_id=message.chat.id,user_id=user.id)
            await message.answer(t['use_game_command'])
            return
        chat_id = message.chat.id
        game = Game.objects.filter(chat_id=chat_id, is_active_game=True,is_started=False).first()
        if not game:
            await message.answer(t['use_game_command'])
            return
        is_admin = await is_group_admin(chat_id, tg_id)
        if not is_admin:
            return
        await stop_registration(chat_id=chat_id)
        return
        
        

# /profile komandasi kelganda
@dp.message(Command("profile"), StateFilter(None))
async def profile_command(message: Message):
    if message.chat.type != "private":
        t = get_lang_text(message.chat.id)
        await message.delete()
        is_admin = await is_group_admin(message.chat.id, message.from_user.id)
        if not is_admin:
            return
        group_trial = GroupTrials.objects.filter(group_id=message.chat.id).first()
        if not group_trial:
            link = message.chat.username if message.chat.username else ""
            if link == "":
                invite = await bot.create_chat_invite_link(
                chat_id=message.chat.id,
                creates_join_request=False
            )   
                link = invite.invite_link
            group_trial = GroupTrials.objects.create(
                group_id=message.chat.id,
                group_name=message.chat.title if message.chat.title else "",
                group_username=link
            )
        if group_trial.end_date and group_trial.end_date < timezone.now():
            group_trial.premium_stones = 0
            group_trial.end_date = None
            group_trial.save()
        is_active = group_trial.end_date > timezone.now() if group_trial.end_date else False
        has_stone = group_trial.stones >= 20
        coins = group_trial.coins if group_trial else 0
        active_text = "✅ Aktiv" if is_active else "❌ Aktiv emas"
        next_activation = group_trial.end_date.strftime('%Y-%m-%d %H:%M:%S') if group_trial.end_date else "Noma'lum"
        stones = group_trial.stones if group_trial else 0
        premium_stones = group_trial.premium_stones if group_trial else 0
        premium_end_date = group_trial.end_date.strftime('%Y-%m-%d %H:%M:%S') if group_trial.end_date else "O'tib ketgan"

        await message.answer(text=t['group_profile'].format(
            coins=coins,
            is_active=active_text,
            next_activation=next_activation,
            stones=stones,
            premium_stones=premium_stones,
            premium_end_date=premium_end_date
        ),
        reply_markup=group_profile_inline_btn(has_stone, message.chat.id)
        )
        
        return
    t = get_lang_text(message.from_user.id)
    user = User.objects.filter(telegram_id=message.from_user.id).first()
    if not user:
        user = User.objects.create(
            telegram_id=message.from_user.id,
            lang ='uz',
            first_name=message.from_user.first_name,
            username=message.from_user.username
        )
    
    user_role = UserRole.objects.filter(user_id=user.id)
    text =""
    for user_r in user_role:
        ROLES_CHOICES = get_role_labels_lang(message.from_user.id)
        role_name = dict(ROLES_CHOICES).get(user_r.role_key, "Noma'lum rol")
        text += f"🎭 {role_name} - {user_r.quantity}\n"
    result = MostActiveUser.objects.filter(user_id=user.id).aggregate(
    total_played=Sum('games_played'),
    total_wins=Sum('games_win')
)

    total_played = result['total_played'] or 0
    total_wins = result['total_wins'] or 0

    await message.answer(
        text=t['user_profile'].format(
            first_name=message.from_user.first_name,
            coin=user.coin,
            stones=user.stones,
            protection=user.protection,
            hang_protect=user.hang_protect,
            docs=user.docs,
            geroy_protect=user.geroy_protection,
            wins=total_wins,
            all_played=total_played,
            text=text
        ),
        parse_mode="HTML",reply_markup=cart_inline_btn(message.from_user.id)
    )
    
    

@dp.message(Command("help"), StateFilter(None))
async def help_command(message: Message) -> None:
    await message.delete()
    await message.answer("Admin.\n\n@RedDon_Mafia")
    

@dp.message(Command("money"), F.chat.type.in_({"group", "supergroup"}), StateFilter(None))
async def money_command(message: Message) -> None:
    await message.delete()
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return

    amount = parse_amount(message.text)
    if amount is None:
        return
    
    sender_id = message.from_user.id
    sender_user = User.objects.filter(telegram_id=sender_id).first()
    if not sender_user:
        sender_user = User.objects.create(
            telegram_id=sender_id,
            lang ='uz',
            first_name=message.from_user.first_name,
            username=message.from_user.username
        )
    if sender_user.coin < amount:
        return
    target_id = message.reply_to_message.from_user.id
    if target_id == sender_id:
        return

    target_user = User.objects.filter(telegram_id=target_id).first()
    if not target_user:
        target_user = User.objects.create(
            telegram_id=target_id,
            lang ='uz',
            first_name=message.reply_to_message.from_user.first_name,
            username=message.reply_to_message.from_user.username
        )

    target_user.coin += amount
    sender_user.coin -= amount
    sender_user.save(update_fields=["coin"])
    target_user.save(update_fields=["coin"])
    t = get_lang_text(message.chat.id)
    send_text = t['send_money'].format(
        amount=amount,
    )
    await send_safe_message(
        chat_id=message.chat.id,
        text=(
            f"<a href='tg://user?id={sender_user.telegram_id}'>{sender_user.first_name}</a> -> <a href='tg://user?id={target_user.telegram_id}'>{target_user.first_name}</a> {send_text}"
        ),
        parse_mode="HTML"
    )

@dp.message(Command("gsend"), F.chat.type.in_({"group", "supergroup"}), StateFilter(None))
async def gsend_command(message: Message) -> None:
    await message.delete()

    if message.reply_to_message:
        return
    is_admin_group = await is_group_admin(message.chat.id, message.from_user.id)
    if not is_admin_group:
        return
    sender = User.objects.filter(telegram_id=message.from_user.id).first()
    if not sender:
        sender = User.objects.create(
            telegram_id=message.from_user.id,
            lang ='uz',
            first_name=message.from_user.first_name,
            username=message.from_user.username
        )

    amount = parse_amount(message.text)
    if amount is None or amount <= 0:
        return
    chat_id = message.chat.id
    game = Game.objects.filter(chat_id=message.chat.id, is_active_game=True).first()
    if not game:
        await message.answer("❌ O'yin boshlanmagan.")
        return
    game = await GameStorage.load(game.id)
    if not game.data or not game.get("players"):
        await message.answer("❌ O'yin boshlanmagan yoki o'yinchilar yo'q.")
        return
    if sender.stones < amount:
        await message.answer("❌ Sizda yetarli olmos yo'q.")
        return
    t = get_lang_text(message.chat.id)
    
    sender.stones -= amount
    sender.save(update_fields=["stones"])
    chat_id = message.chat.id
    t = get_lang_text(chat_id)
    group_sender = t['group_sender'].format(  
        count=amount,
    )
    text = (
        f"💎 <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a> {group_sender}"
    )

    sent = await message.answer(text, reply_markup=take_gsend_stone_btn(chat_id), parse_mode="HTML")

    gsend_taken[chat_id] = {
        "limit": amount,
        "taken": [],
        "msg_id": sent.message_id,
        "creator": message.from_user.id
}   
    
        
   
    


@dp.message(Command("send"), F.chat.type.in_({"group", "supergroup"}), StateFilter(None))
async def money_command(message: Message) -> None:
    await message.delete()
    if not message.reply_to_message or not message.reply_to_message.from_user:
        is_admin_grp = await is_group_admin(message.chat.id, message.from_user.id)
        if not is_admin_grp:
            return
        
        sender = User.objects.filter(telegram_id=message.from_user.id).first()
        if not sender:
            sender = User.objects.create(
                telegram_id=message.from_user.id,
                lang ='uz',
                first_name=message.from_user.first_name,
                username=message.from_user.username
            )
        
        parts = message.text.split(maxsplit=1)
        count = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1

        if count <= 0:
            return
        if sender.stones < count:
            await message.answer("❌ Sizda yetarli olmos yo'q.")
            return
        sender.stones -= count
        sender.save(update_fields=["stones"])
        chat_id = message.chat.id
        t = get_lang_text(chat_id)
        group_sender = t['group_sender'].format(  
            count=count,
        )
        text = (
            f"💎 <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a> {group_sender}"
        )

        sent = await message.answer(text, reply_markup=take_stone_btn(chat_id), parse_mode="HTML")

        stones_taken[chat_id] = {
            "limit": count,
            "taken": [],
            "msg_id": sent.message_id,
            "creator": message.from_user.id
    }   
        return

    amount = parse_amount(message.text)
    if amount is None:
        return
    
    sender_id = message.from_user.id
    sender_user = User.objects.filter(telegram_id=sender_id).first()
    if not sender_user:
        sender_user = User.objects.create(
            telegram_id=sender_id,
            lang ='uz',
            first_name=message.from_user.first_name,
            username=message.from_user.username
        )
    if sender_user.stones < amount:
        return
    
    target_id = message.reply_to_message.from_user.id
    if target_id == sender_id:
        return
    
    target_user = User.objects.filter(telegram_id=target_id).first()
    if not target_user:
        target_user = User.objects.create(
            telegram_id=target_id,
            lang ='uz',
            first_name=message.reply_to_message.from_user.first_name,
            username=message.reply_to_message.from_user.username
        )

    target_user.stones += amount
    sender_user.stones -= amount
    sender_user.save(update_fields=["stones"])
    target_user.save(update_fields=["stones"])

    t = get_lang_text(message.chat.id)
    send_text = t['send_stone'].format(
        amount=amount,
    )
    await send_safe_message(
        chat_id=message.chat.id,
        text=(
            f"<a href='tg://user?id={sender_user.telegram_id}'>{sender_user.first_name}</a> -> <a href='tg://user?id={target_user.telegram_id}'>{target_user.first_name}</a> {send_text}"
        ),
        parse_mode="HTML"
    )
        
        
@dp.message(Command("change"), F.chat.type.in_({"group", "supergroup"}), StateFilter(None))
async def change_command(message: Message) -> None:
    await message.delete()

    is_admin_grp = await is_group_admin(message.chat.id, message.from_user.id)
    if not is_admin_grp:
        return
    
    amount = parse_amount(message.text)
    if amount is None or amount <= 0:
        return
    sender = User.objects.filter(telegram_id=message.from_user.id).first()
    if not sender:
        sender = User.objects.create(
            telegram_id=message.from_user.id,
            lang ='uz',
            first_name=message.from_user.first_name,
            username=message.from_user.username
        )

    chat_id = message.chat.id
    if sender.stones< amount:
        await message.answer("❌ Sizda yetarli olmos yo'q.")
        return

    sender.stones -= amount
    sender.save(update_fields=["stones"])

    duration = 300  # ⏳ seconds
    minut = duration // 60
    end_at = int(time.time()) + duration
    t = get_lang_text(message.chat.id)
    group_change = t['giveaway_join'].format(
        amount=amount,
        minut=minut,
        sekund=duration % 60,
        text ="",
        quantity = 0
    )

    sent = await message.answer(group_change, reply_markup=giveaway_join_btn(chat_id), parse_mode="HTML")

    giveaways[chat_id] = {
        "amount": amount,
        "members": set(),
        "end_at": end_at,
        "msg_id": sent.message_id
    }

    asyncio.create_task(finish_giveaway(chat_id, message.bot))

@dp.message(Command(commands=["leave", "quit"]),F.chat.type.in_({"group", "supergroup"}), StateFilter(None))
async def leave(message: Message) -> None:
    await message.delete()
    tg_id = message.from_user.id
    chat_id = message.chat.id
    game_db = Game.objects.filter(chat_id=chat_id, is_active_game=True).first()
    if not game_db or not game_db.is_started:
        return
    
    game = await GameStorage.load(game_db.id)
    if not game.data:
        return
    if tg_id not in game.get("alive", []):
        return
    await kill(game,tg_id)
    user = User.objects.filter(telegram_id=tg_id).first()
    if not user:
        return
    t = get_lang_text(chat_id)
    role = game.get("roles", {}).get(tg_id)
    if role == "don":
        new_don_id = promote_new_don_if_needed(game)
        if new_don_id:
            await notify_new_don( game,new_don_id)
            await send_safe_message(
                chat_id=chat_id,
                text=t['don_become']
                    )
    elif role == "com":
        new_com_id = promote_new_com_if_needed(game)
        if new_com_id:
            await notify_new_com(  new_com_id)
            await send_safe_message(
                        chat_id=chat_id,
                        text=t['com_become']
                    )
    role_label_text = role_label(role,chat_id)
    await send_safe_message(chat_id=chat_id,text=t['left_game'].format(telegram_id=tg_id,first_name=user.first_name,role_label_text=role_label_text))
    
    


@dp.message(Command("admin"), StateFilter(None))
async def admin_command(message: Message) -> None:
    if message.chat.type != "private":
        await message.delete()
        return
    user = User.objects.filter(telegram_id=message.from_user.id).first()
    if user and user.role == 'admin':
        await message.answer("👮 Siz Mafia botning admin panelidasiz.",reply_markup=admin_inline_btn())

@dp.message(Command("language"), StateFilter(None))
async def language(message: Message):
    if message.chat.type != "private":
        await message.delete()
        return
    await message.answer(
        "🌐 Tilni tanlang:",
        reply_markup=language_keyboard()
    )




registration_timers = {}

async def registration_timer(game_id, chat_id):
    one_minute_notified = False
    thirty_sec_notified = False
    uuid = str(Game.objects.get(id=game_id).uuid)
    t = get_lang_text(chat_id)

    try:
        while True:
            data = registration_timers.get(int(game_id))
            if not data:
                return

            remaining = data[1]
            if remaining <= 0:
                break
            if remaining > 60:
                one_minute_notified = False
                thirty_sec_notified = False
            elif remaining > 30 :
                thirty_sec_notified = False
            if remaining <= 59 and not one_minute_notified:
                one_minute_notified = True
                msg = await send_safe_message(
                    chat_id,
                    t['59_left'],
                    reply_markup=join_game_btn(uuid,chat_id)
                )
                BotMessages.objects.create(game_id=int(game_id), message_id=msg.message_id, is_main=False)

            if remaining <= 29 and not thirty_sec_notified:
                msg = BotMessages.objects.filter(game_id=int(game_id), is_main=False, is_deleted=False).last()
                if msg:
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
                        msg.is_deleted = True
                        msg.save()
                    except:
                        pass
                thirty_sec_notified = True
                msg = await send_safe_message(
                    chat_id,
                    t['29_left'],
                    reply_markup=join_game_btn(uuid,chat_id)
                )
                BotMessages.objects.create(game_id=int(game_id), message_id=msg.message_id, is_main=False)

            await asyncio.sleep(1)
            data[1] -= 1

        await stop_registration(game_id=int(game_id))

    except asyncio.CancelledError:
        return



async def stop_registration(game_id=None, chat_id=None, instant=False):
    if game_id and chat_id is None:
        game = Game.objects.get(id=game_id)
    else:
        game = Game.objects.filter(chat_id=chat_id, is_active_game=True, is_started=False).first()

    all_players = (await GameStorage.load(game.id)).get("players", [])
    players_count = len(all_players)

    timer = registration_timers.pop(game.id, None)
    if timer:
        task = timer[0]
        if task and not task.done():
            task.cancel()
    t = registration_refresh_tasks.pop(game.id, None)
    if t and not t.done():
        t.cancel()


    deleted_messages = BotMessages.objects.filter(game_id=game.id, is_deleted=False)
    for bot_message in deleted_messages:
        try:
            await bot.delete_message(chat_id=game.chat_id, message_id=bot_message.message_id)
            bot_message.is_deleted = True
            bot_message.save()
        except:
            pass
    if instant:
        return
    t = get_lang_text(game.chat_id)
    if players_count < 4 and not game.is_started:
        game.is_active_game = False
        game.save()
        await send_safe_message(
            chat_id=game.chat_id,
            text=t["not_enough_players"]
        )
    else:
        game.is_started = True
        game.save()
        await send_safe_message(
            chat_id=game.chat_id,
            text=t["game_started"],
            reply_markup=go_to_bot_inline_btn(game.chat_id)
        )
        shuffle_roles(game.id)
        await send_roles(game_id=game.id, chat_id=game.chat_id)
        return
    

registration_refresh_tasks = {}

@dp.message(Command("game"), StateFilter(None)) 
async def game_command(message: Message) -> None:
    chat_id = message.chat.id
    lock = get_game_lock(chat_id)

    if lock.locked():
        return

    async with lock:

        bot_member = await message.chat.get_member(message.bot.id)
        result = check_bot_rights(bot_member,chat_id)
        if result:
            await message.answer(text=result)
            return
        await message.delete() 
        t = get_lang_text(chat_id)
        if message.chat.type in ("group", "supergroup"): 
            chat_id = message.chat.id
            is_admin = await is_group_admin(chat_id, message.from_user.id)
            if not is_admin:
                return
            trial = GroupTrials.objects.filter(group_id=chat_id).first()
            if trial:
                if trial.end_date <= timezone.now():
                    if not trial.coins > 5:
                    
                        await message.answer(
                        t["trial_expired"]
                    )
                        return
                    else:
                        trial.coins -5
                        trial.end_date = default_end_date()
                        trial.save()
            else:
                link = message.chat.username if message.chat.username else ""
                if link == "":
                    invite = await bot.create_chat_invite_link(
                    chat_id=chat_id,
                    creates_join_request=False
                )   
                    link = invite.invite_link
                
                GroupTrials.objects.create(
                    group_id=chat_id,
                    group_name=message.chat.title if message.chat.title else "",
                    group_username=link
                )
            game , created = Game.objects.get_or_create(chat_id=chat_id,is_active_game=True) 
            if not created: 
                text_begining = create_main_messages(game.id,chat_id)
                bot_message=BotMessages.objects.filter(game_id=game.id,is_main=True,is_deleted=False)
                if bot_message:
                    message_ids = [m.message_id for m in bot_message if m]
                    if message_ids:
                        await bot.delete_messages(chat_id=chat_id,message_ids=message_ids)
                    bot_message.update(is_deleted=True)
                msg = await message.answer(text=text_begining,reply_markup=join_game_btn(str(game.uuid), chat_id))
                await bot.pin_chat_message(chat_id=chat_id,message_id=msg.message_id)
                BotMessages.objects.create(game_id=game.id,message_id=msg.message_id,is_main=True)
                return
            if game.is_started:
                return
            if " " in message.text and message.text.split(' ')[1] == "turnir":
                print("turnir mode")
                game.game_type = "turnir"
                game.save(update_fields=["game_type"])
            user = User.objects.filter(telegram_id=message.from_user.id).first()
            if not user:
                user = User.objects.create(
                    telegram_id=message.from_user.id,
                    lang ='uz',
                    first_name=message.from_user.first_name,
                    username=message.from_user.username
                )
                
                
            msg = await message.answer(text=t["registration_started"],reply_markup=join_game_btn(str(game.uuid), chat_id))
            await bot.pin_chat_message(chat_id=chat_id,message_id=msg.message_id)
            BotMessages.objects.create(game_id=game.id,message_id=msg.message_id,is_main=True)
            task = asyncio.create_task(refresh_registration_main_message(game.id, chat_id))
            registration_refresh_tasks[game.id] = task
            users_to_notify = list(notify_users.get(chat_id, set()))
            if users_to_notify:
                text = t['registration_started_notify']

                for user_id in users_to_notify:
                    try:
                        await send_safe_message(chat_id=user_id, text=text,reply_markup=join_game_btn(str(game.uuid), chat_id))
                    except Exception:
                        pass
                notify_users[chat_id].clear()
            game_settings = GameSettings.objects.filter(group_id=chat_id).first()
            if not game_settings:
                game_settings = GameSettings.objects.create(group_id=chat_id,user_id=user.id)
            if game_settings and not game_settings.begin_instance:
                wait_time = game_settings.begin_instance_time
            else:
                return
                    
            task = asyncio.create_task(registration_timer(game.id, chat_id))
            registration_timers[game.id] = [task, wait_time] 
        
async def auto_begin_game(chat_id: int):
    game , created = Game.objects.get_or_create(chat_id=chat_id,is_active_game=True) 
    if not created: 
        return
    game_settings = GameSettings.objects.filter(group_id=chat_id).first()
    if not game_settings:
        return
    messages = BotMessages.objects.filter(game_id=game.id,is_main=True,is_deleted=False)
    if messages:
        message_ids = [m.message_id for m in messages if m]
        if message_ids:
            try:
                await bot.delete_messages(chat_id=chat_id,message_ids=message_ids)
            except:
                pass
            
            
    messages.update(is_deleted=True)
    t = get_lang_text(chat_id)
    msg = await send_safe_message(chat_id=chat_id,text=t["registration_started"],reply_markup=join_game_btn(str(game.uuid), chat_id))
    await bot.pin_chat_message(chat_id=chat_id,message_id=msg.message_id)
    BotMessages.objects.create(game_id=game.id,message_id=msg.message_id,is_main=True)
    task = asyncio.create_task(refresh_registration_main_message(game.id, chat_id))
    registration_refresh_tasks[game.id] = task
    if game_settings and not game_settings.begin_instance:
        wait_time = game_settings.begin_instance_time
    else:
        return
            
    task = asyncio.create_task(registration_timer(game.id, chat_id))
    registration_timers[game.id] = [task, wait_time] 

# /extend handler
@dp.message(Command("extend"), StateFilter(None))
async def extend_command(message: Message):
    await message.delete()
    if message.chat.type in ("group", "supergroup"):
        is_admin = await is_group_admin(message.chat.id, message.from_user.id)
        if not is_admin:
            return
        chat_id = message.chat.id
        game = Game.objects.filter(chat_id=chat_id, is_active_game=True).first()
        if game and game.id in registration_timers:
            registration_timers[game.id][1] += 30
            remaining = registration_timers[game.id][1]
            minutes = remaining // 60
            seconds = remaining % 60
            t = get_lang_text(chat_id)
            msg = await message.answer(
                f"{t['registration_extended']}\n\n"
                f"{t['time_left'].format(minutes=minutes, seconds=seconds)}"
            )
            await asyncio.sleep(5)
            await msg.delete()
        else:
            return


@dp.message(Command("stop"), StateFilter(None))
async def stop_command(message: Message) -> None:
    await message.delete()

    if message.chat.type not in ("group", "supergroup"):
        return

    chat_id = message.chat.id
    tg_id = message.from_user.id
    is_admin = await is_group_admin(chat_id, tg_id)
    if not is_admin:
        return
    

    # 1) REGISTRATION ketayotgan bo'lsa
    game_reg = Game.objects.filter(chat_id=chat_id, is_active_game=True).first()
    tu = get_lang_text(chat_id)
    if game_reg and not game_reg.is_started:
        game_reg.is_active_game = False
        game_reg.save()
        writing_allowed_groups.pop(game_reg.chat_id, None)
        # task bo'lsa cancel (agar siz game_tasks ishlatayotgan bo'ls
        await stop_registration(game_id=game_reg.id,instant=True)
        await send_safe_message(chat_id=chat_id, text=tu["registration_stopped"])
        return

    # 2) START bo'lgan o'yinni to'xtatis
    
    if not game_reg or not game_reg.is_started:
        await send_safe_message(chat_id=chat_id, text=tu["no_active_game"])
        return

    # task bo'lsa cancel (agar siz game_tasks ishlatayotgan bo'lsangiz)
    timer = registration_timers.pop(game_reg.id, None)
    if timer:
        task = timer[0]
        if task and not task.done():
            task.cancel()
    t = registration_refresh_tasks.pop(game_reg.id, None)
    if t and not t.done():
        t.cancel()

    # DB update (active game)
    if game_reg:
        game_reg.is_active_game = False
        game_reg.is_started = False
        game_reg.save()

    # RAM dan o'chiramiz
    game = await GameStorage.load(game_reg.id)
    if game.data:
        game.delete()
    writing_allowed_groups.pop(game_reg.chat_id, None)
    task = game_tasks.get(game_reg.id)
    if task and not task.done():
        task.cancel()

    await send_safe_message(chat_id=chat_id, text=tu["game_stopped"])

            
@dp.message(Command("mute"), Command("kick"), Command("ban"), StateFilter(None))
async def admin_moderation_commands(message: Message) -> None:
    await message.delete()
    if message.chat.type not in ("group", "supergroup"):
        return

    chat_id = message.chat.id
    tg_id = message.from_user.id
    is_admin = await is_group_admin(chat_id, tg_id)
    if not is_admin:
        return
    if  message.reply_to_message or  message.reply_to_message.from_user:
        game_db = Game.objects.filter(chat_id=chat_id, is_active_game=True).first()
        if not game_db:
            return
        game = await GameStorage.load(game_db.id)
        if game.data:
            await kill(game,message.reply_to_message.from_user.id)
            await send_safe_message(chat_id=message.reply_to_message.from_user.id,text="🔇 Siz o'yindan chetlatildingiz!")
        return
    tg_id = message.text.split(' ')[1]
    game_db = Game.objects.filter(chat_id=chat_id, is_active_game=True).first()
    if not game_db:
        return
    game = await GameStorage.load(game_db.id)
    if game.data:
        await kill(game,int(tg_id))
        await send_safe_message(chat_id=message.reply_to_message.from_user.id,text="🔇 Siz o'yindan chetlatildingiz!")
    return

    


@dp.message(Command("next"), StateFilter(None))
async def next_command(message: Message) -> None:
    await message.delete()

    if message.chat.type not in ("group", "supergroup"):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in notify_users:
        notify_users[chat_id] = set()

    notify_users[chat_id].add(user_id)

    await send_safe_message(
        chat_id=user_id,
        text="✅ Siz keyingi o'yin haqida eslatma olasiz."
    )


async def send_top(message: Message, days: int, title: str):
    await message.delete()

    if days== 30 and message.chat.type in ("group", "supergroup"):
        return
    if message.chat.type in ("group", "supergroup"):
        is_admin = await is_group_admin(message.chat.id, message.from_user.id)
        if not is_admin:
            return
    if days == 30:
        user = User.objects.filter(telegram_id=message.from_user.id).first()
        if not user or user.role != 'admin':
            return
    group_id = message.chat.id
    since = timezone.now() - timedelta(days=days)
    all_get=10
    if days == 30:
        all_get= 30
    elif days ==7:
        all_get=7
    else:
        all_get=10
    if days == 30:
        top = (
        MostActiveUser.objects
        .filter( created_datetime__gte=since)
        .values("user")
        .annotate(wins=Sum("games_win"))
        .order_by("-wins")[:all_get]
    )
    else:
        top = (
        MostActiveUser.objects
        .filter(group=group_id, created_datetime__gte=since)
        .values("user")
        .annotate(wins=Sum("games_win"))
        .order_by("-wins")[:all_get]
    )

    if not top:
        await message.answer("Bu guruhda hali o'yin o'ynagan foydalanuvchilar yo'q.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []

    user_ids = [x["user"] for x in top]
    users_map = {u.id: u for u in User.objects.filter(id__in=user_ids)}

    for idx, row in enumerate(top, start=1):
        user = users_map.get(row["user"])
        if not user:
            continue

        mention = f"<a href='tg://user?id={user.telegram_id}'>{user.first_name}</a>"
        win = row["wins"] or 0

        if idx <= 3:
            lines.append(f"{medals[idx-1]} {mention} — {win*5} ball")
        else:
            lines.append(f"{idx}. {mention} — {win*5} ball")

    text = f"{title}\n\n" + "\n".join(lines)
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("top"), StateFilter(None))
async def top_command(message: Message):
    t = get_lang_text(message.chat.id)
    await send_top(message, days=1, title=t["top_daily"])


@dp.message(Command("top7"), StateFilter(None))
async def top7_command(message: Message):
    t = get_lang_text(message.chat.id)
    await send_top(message, days=7, title=t["top_weekly"])


@dp.message(Command("top30"), StateFilter(None))
async def top30_command(message: Message):
    t = get_lang_text(message.chat.id)
    await send_top(message, days=30, title=t["top_monthly"])


@dp.message(Command("share"), StateFilter(None))
async def share_command(message: Message) -> None:
    await message.delete()
    await message.answer("Do'stlarni chaqirish uchun /share buyrug'idan foydalaning.")
    
async def send_mafia_companions(game_id, chat_id):
    game = await GameStorage.load(game_id)
    players = game.get("players", [])
    roles_map = game.get("roles", {})
    users_map = game.get("users_map", {})

    mafia_members = [
        u for u in players
        if roles_map.get(u) in ["mafia", "don", "adv", "spy"]
    ]
    if len(mafia_members) < 2:
        return
    user_qs = [users_map[tg_id] for tg_id in mafia_members if tg_id in users_map]
    for user in user_qs:
        my_id = user.get("tg_id")
        team_chat_sessions[my_id] = chat_id
        t = get_lang_text(my_id)


        lines = []
        for mate in user_qs:
            mate_role = roles_map.get(mate.get("tg_id"))
            lines.append(f"{mate.get('first_name')} - {role_label(mate_role,chat_id)}")

        text = t["mafia_companions"] + "\n" + ("\n".join(lines) if lines else t["no"])

        try:
            await send_safe_message(chat_id=my_id, text=text, parse_mode="HTML")
        except Exception:
            pass


async def sergant_send_companions(game_id, chat_id):
    game = await GameStorage.load(game_id)
    players = game.get("players", [])
    roles_map = game.get("roles", {})
    users_map = game.get("users_map", {})

    sergant_members = [
        u for u in players
        if roles_map.get(u) in ["serg","com"]
    ]
    if len(sergant_members) < 2:
        return
    user_qs = [users_map[tg_id] for tg_id in sergant_members if tg_id in users_map]
    for user in user_qs:
        my_id = user.get("tg_id")
        team_chat_sessions[my_id] = chat_id
        t = get_lang_text(my_id)

        lines = []
        for mate in user_qs:
            mate_role = roles_map.get(mate.get("tg_id"))
            lines.append(f"{mate.get('first_name')} - {role_label(mate_role,chat_id)}")

        text = t["mafia_companions"] + "\n" + ("\n".join(lines) if lines else t["no"])

        try:
            asyncio.create_task(send_safe_message(chat_id=my_id, text=text))
        except Exception:
            pass


async def send_roles(game_id, chat_id):
    game = await GameStorage.load(game_id)
    game_players = game.get("players", [])
    roles_map = game.get("roles", {})  

    for tg_id in game_players:
        role_key = roles_map.get(tg_id)
        if tg_id in active_role_used:
            t = get_lang_text(tg_id)
            await send_safe_message(
                chat_id=tg_id,
                text=t["active_role_used"])
            active_role_used.remove(tg_id)

        role_text = get_description_lang(tg_id).get(role_key, "Rol topilmadi.")

        try:
            await send_safe_message(
                chat_id=tg_id,
                text=f"{role_text}",
                parse_mode="HTML"
            )
        except Exception as e:
            pass
            
    await send_mafia_companions(int(game_id), chat_id)
    await sergant_send_companions(int(game_id), chat_id)
    run_game_in_background(int(game_id))
    
    

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def delete_not_alive_messages(message: Message):
    chat_id = int(message.chat.id)
    tg_id = int(message.from_user.id)
    if chat_id not in group_users:
        group_users[chat_id] = set()

    group_users[chat_id].add(tg_id)
    if message and message.text and message.text.startswith('!'):
        is_group_admin_bool = await is_group_admin(chat_id, tg_id)
        if is_group_admin_bool:
            return

    if writing_allowed_groups.get(int(chat_id)) == "no":
        try:
            await message.delete()
            await mute_user(int(chat_id), int(tg_id))
        except Exception:
            pass
        return
    
    game = await get_game_by_chat_id(int(chat_id))
    if not game or game.get("meta", {}).get("is_active_game") is not True:
        print("No active game in this chat")
        return 

    
    alive = set(game.get("alive", []))
    night_action = game.get("night_actions", {})
    lover_block_target = night_action.get("lover_block_target")
    t = get_lang_text(int(tg_id))
    if lover_block_target == tg_id:
        try:
            await message.delete()
            await mute_user(chat_id,tg_id)
            await send_safe_message(
                chat_id=tg_id,
                text=t['dance_party']
            )
        except Exception:
            pass
        return
    
    if tg_id not in alive:
        try:
            await message.delete()
            await mute_user(chat_id, tg_id)
            await send_safe_message(
                chat_id=tg_id,
                text=t["no_write_game_time"]
            )
        except Exception:
            pass
        return


@dp.message(F.chat.type.in_({"private"}),StateFilter(None))
async def private_router(message: Message,state: FSMContext) -> None:
    tg_id = int(message.from_user.id)
    if message.text == "admin_parol":
        await message.answer("Iltimos, login va parolni bitta qatorda yuboring:\n\nlogin password",reply_markup=back_btn(message.from_user.id))
        await state.set_state(CredentialsState.login)
        return
    elif message.text == "logout_admin":
       
        await admin_logout(message)
        return
        
    if not message.text:
        return

    text = message.text.strip()
    if not text:
        return

    # =========================================
    # 1) LAST WISH (o'lganlar xabari)
    # =========================================
    data = last_wishes.get(tg_id)
    if data:
        chat_id = int(data.get("chat_id"))
        target_name = data.get("target_name")
        role = data.get("victim_role_label")
        if has_link(text):
            print("Link detected in last wish", text)
            return
        try:
            t = get_lang_text(chat_id)
            await send_safe_message(
                chat_id=int(chat_id),
                text=t['last_wish_message'].format(
                    tg_id=int(tg_id),
                    first_name=target_name,
                    role_label_text=role,
                    text=text
                ),
                parse_mode="HTML"
            )
            
            await message.answer(text=t['last_wish_send'])
            last_wishes.pop(tg_id, None)
        except Exception:
            pass

                      
            


    # =========================================
    # 2) TEAM CHAT (mafia chat relay)
    # =========================================
    team_chat_id = team_chat_sessions.get(tg_id)
    if not team_chat_id:
        return

    game = await get_game_by_chat_id(int(team_chat_id))
    if not game:
        return

    if game.get("meta", {}).get("team_chat_open") != "yes":
        return

    # sender alive bo'lishi kerak
    if tg_id not in set(game.get("alive", [])):
        return

    roles_map = game.get("roles", {})
    sender_role = roles_map.get(tg_id)

    if sender_role not in MAFIA_ROLES:
        return

    if has_link(text):
        return

    mafia_ids = [
        pid for pid, r in roles_map.items()
        if r in MAFIA_ROLES and pid in set(game.get("alive", []))
    ]

    sender_user = game.get("users_map", {}).get(int(tg_id))
    sender_name = sender_user.get("first_name") if sender_user else str(tg_id)

    relay_text = (
        f"🕶 <b>Mafiya chat</b>\n"
        f"👤 <a href='tg://user?id={tg_id}'>{sender_name}</a>:\n\n"
        f"{text}"
    )

    for mid in mafia_ids:
        if mid == tg_id:
            continue
        try:
            await send_safe_message(
                chat_id=int(mid),
                text=relay_text,
                parse_mode="HTML"
            )
        except Exception:
            pass


@dp.message(StateFilter(CredentialsState.login))
async def process_admin_password(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()

    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Login va parolni bitta qatorda yuboring:\n\nlogin password",reply_markup=back_btn(message.from_user.id))
        return

    login, password = parts[0], parts[1]

    user = User.objects.filter(telegram_id=message.from_user.id).first()
    if not user:
        await message.answer("Siz botda ro‘yxatdan o‘tmagansiz ❌")
        await state.clear()
        return

    attempts_obj, _ = LoginAttempts.objects.get_or_create(admin=user)

    if attempts_obj.permanent_ban:
        await message.answer("Siz adminkaga kirishdan bloklangansiz 🚫")
        await state.clear()
        return

    if attempts_obj.ban_until and attempts_obj.ban_until > timezone.now():
        left = attempts_obj.ban_until - timezone.now()
        hours = int(left.total_seconds() // 3600)
        await message.answer(f"Siz adminkaga kirishdan vaqtincha bloklangansiz 🚫\nQolgan vaqt: {hours} soat")
        await state.clear()
        return

    admin = BotCredentials.objects.filter(login=login).first()
    if not admin:
        await message.answer("Login noto‘g‘ri ❌")
        await state.clear()
        return

    if not check_password(password, admin.password):
        # Agar oldin 1 kun ban olgan bo‘lsa (demak ikkinchi xato) => umrbod ban
        if attempts_obj.ban_until is not None:
            attempts_obj.ban_forever()
            await message.answer("Parol noto‘g‘ri ❌\nSiz umrbod bloklandingiz 🚫")
            await state.clear()
            return

        # Birinchi xato => 1 kun ban
        attempts_obj.ban_for_1_day()
        await message.answer("Parol noto‘g‘ri ❌\nSiz 1 kunga bloklandingiz 🚫")
        await state.clear()
        return

    # login success => banlar va attempts reset
    attempts_obj.attempts = 0
    attempts_obj.last_attempt = timezone.now()
    attempts_obj.ban_until = None
    attempts_obj.permanent_ban = False
    attempts_obj.save()

    if user.role != 'admin':
        user.role = 'admin'
        user.save(update_fields=["role"])

    await message.answer("Muvaffaqiyatli kirdingiz ✅", reply_markup=admin_inline_btn())
    await state.clear()
    

    

async def admin_logout(message: Message) -> None:
    user = User.objects.filter(telegram_id=message.from_user.id).first()
    if user and user.role != 'admin':
        await message.answer(text="Siz admin emassiz!",reply_markup=start_inline_btn(message.from_user.id))
        return
    if user:
        user.role = 'user'
        user.save()
    await message.answer(text="Siz endi admin emassiz!",reply_markup=start_inline_btn(message.from_user.id))
    



async def finish_giveaway(chat_id: int, bot):
    gw = giveaways.get(chat_id)
    if not gw:
        return

    wait_seconds = gw["end_at"] - int(time.time())
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    gw = giveaways.get(chat_id)
    if not gw:
        return

    members = list(gw["members"])
    amount = gw["amount"]
    msg_id = gw["msg_id"]
    t = get_lang_text(chat_id)
    if not members:
        text = t['giveaway_ended'].format(amount=amount)
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
        except:
            pass
        giveaways.pop(chat_id, None)
        return

    winner_id = random.choice(members)

    user = User.objects.filter(telegram_id=winner_id).first()
    winner_name = user.first_name if user else "Foydalanuvchi"
    text = t['giveaway_ended_succes'].format(
        amount=amount,
        winner_name=winner_name,
        winner_id=winner_id,
        members_count=len(members)
    )
    user.stones += amount
    user.save(update_fields=["stones"])

    try:
        await send_safe_message(winner_id, text=t['giveaway_winner'].format(amount=amount), parse_mode="HTML")
        await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=None)
        await send_safe_message(text,chat_id=chat_id,parse_mode="HTML")
    except:
        await send_safe_message(chat_id, text, parse_mode="HTML")

    giveaways.pop(chat_id, None)

async def refresh_registration_main_message(game_id: int, chat_id: int):
    try:
        while True:
            await asyncio.sleep(40)
            game = Game.objects.filter(id=game_id, is_active_game=True, is_started=False).first()
            if not game:
                return

            uuid = str(game.uuid)

            old_main = BotMessages.objects.filter(
                game_id=game_id, is_main=True, is_deleted=False
            ).last()

            if old_main:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=old_main.message_id)
                except Exception:
                    pass
                old_main.is_deleted = True
                old_main.save()

            result_2 = create_main_messages(int(game_id),chat_id)
           
            msg = await send_safe_message(
                chat_id=chat_id,
                text=result_2,
                reply_markup=join_game_btn(uuid, chat_id)
            )

            await bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id)

            BotMessages.objects.create(
                game_id=int(game_id), message_id=msg.message_id, is_main=True
            )


    except asyncio.CancelledError:
        return


async def olmos_star_handler(message,olmos_amount: int, star_amount: int,chat_id: int):

    prices = [
        LabeledPrice(label=f"💎 {olmos_amount} sotib olish", amount=star_amount)
    ]
    t = get_lang_text(chat_id)
    await bot.send_invoice(
        chat_id=message.chat.id,
        title=t['buy_stone_group'],
        description=t['buy_stone_group_desc'],
        payload=f"olmos_{olmos_amount}_{star_amount}_{chat_id}",
        currency="XTR",
        prices=prices
    )
    
async def stones_to_premium(message:Message, chat_id: int):
    game_trials = GroupTrials.objects.filter(group_id=chat_id).first()
    if not game_trials:
        await message.answer("❌ Guruhda obuna muddati yo'q.")
        return 
    t = get_lang_text(chat_id)
    text = f"{t['become_premium_group']} {game_trials.stones} "
    await message.answer(text,reply_markup=stones_to_premium_inline_btn(game_trials.stones,chat_id))



async def claim_channel_olmos(message: Message, username: str):
    username = f"@{username}" if not username.startswith("@") else username
    data = stones_taken.get(username)
    user_id = message.from_user.id
    tu = get_lang_text(user_id)
    if not data:
        await message.answer(tu['no_sharing'], show_alert=True)
        return

    limit = data["limit"]
    taken = data["taken"]
    msg_id = data["msg_id"]
    sender = data["creator"]

    if user_id in taken:
        await message.answer(tu['stone_already_taken'], show_alert=True)
        return

    if len(taken) >= limit:
        await message.answer(tu['stone_ended'], show_alert=True)
        return

    taken.append(user_id)
    user_taker = User.objects.filter(telegram_id=user_id).first()
    sender = User.objects.filter(telegram_id=int(sender)).first()
    if not user_taker:
        user_taker = User.objects.create(
            telegram_id=user_id, 
            first_name=message.from_user.first_name,
            username=message.from_user.username
        )
    users_qs = User.objects.filter(telegram_id__in=taken)
    
    
    taken_text = ""
    for i, user in enumerate(users_qs, start=1):
        taken_text += f"\n{i}. 💎 <a href='tg://user?id={user.telegram_id}'>{user.first_name}</a>"

    text = (
         f"Kanalga {limit} ta 💎 olmos yuborildi."
        f"{taken_text}"
    )
    
    if len(taken) >= limit:
        await bot.edit_message_text(chat_id=username, message_id=msg_id, text=text, reply_markup=None, parse_mode="HTML")
        stones_taken.pop(username, None)
    else:
        await bot.edit_message_text(chat_id=username, message_id=msg_id, text=text, reply_markup=claim_chanel_olmos_inline_btn(username.lstrip("@")), parse_mode="HTML")
    user_taker.stones += 1
    user_taker.save()
    await message.answer(tu['stone_taken'])