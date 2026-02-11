import time
import random
import asyncio
import traceback
from dispatcher import bot
from collections import Counter
from mafia_bot.models import Game, User
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramRetryAfter
from mafia_bot.utils import game_tasks,writing_allowed_groups
from mafia_bot.buttons.inline import confirm_hang_inline_btn, go_to_bot_inline_btn,action_inline_btn
from mafia_bot.handlers.main_functions import (can_hang, games_state, get_most_voted_id,night_reset,day_reset, notify_new_com, notify_new_don, prepare_confirm_pending,
                                               prepare_hang_pending, prepare_night_pending, promote_new_com_if_needed, promote_new_don_if_needed, punish_afk_night_players,send_night_actions_to_all,send_safe_message,
                                               apply_night_actions, stop_game_if_needed,PEACE_ROLES,MAFIA_ROLES_LAB,SOLO_ROLES,hero_day_actions,get_lang_text,get_role_labels_lang)



def run_game_in_background(game_id: int):
    if game_id in game_tasks and not game_tasks[int(game_id)].done():
        return False

    task = asyncio.create_task(start_game(int(game_id)))
    game_tasks[int(game_id)] = task
    return True



async def start_game(game_id):
    game_id = int(game_id)
    try:
        game = Game.objects.filter(id=game_id).first()
        if not game:
            return

        game.is_started = True
        game.save()
        game_data_bg = games_state.get(game_id)
        if not game_data_bg:
            return
        games_state[game_id]['meta']["chat_id"] = game.chat_id
        games_state[game_id]['meta']["uuid"] = str(game.uuid)
        games_state[game_id]['meta']['is_active_game'] = True
        games_state[game_id]['meta']['created_at'] = int(time.time())
        day = 1
        sunset = FSInputFile("mafia_bot/gifs/sunset.mp4")
        sunrise = FSInputFile("mafia_bot/gifs/sunrise.mp4")
        users_map = games_state[game_id].get("users_map", {})
        t= get_lang_text(game.chat_id)
        while True:
            # ================= NIGHT START =================
            night_reset(game_id)
            

            game_data = games_state.get(game_id, {})
            all_players = game_data.get("players", [])   # tg_id list
            alive_players = game_data.get("alive", [])   # tg_id list
            game_data['meta']['message_allowed'] = "no"
            writing_allowed_groups[game.chat_id] = "no"
            alive_before_night = alive_players.copy()

            # alive ids join-order bilan

            alive_users_qs = [users_map[tg_id] for tg_id in alive_players if tg_id in users_map]


            # object list keyboardlar uchun

            # night action buttonlar

            games_state[game_id]['meta']['day'] +=1
            games_state[game_id]["meta"]["team_chat_open"] = "yes"
            game_day = games_state[game_id].get("meta", {}).get("day", 0) 
            
            asyncio.create_task(send_night_actions_to_all( game_id, game, alive_users_qs,game_day))

            
            caption = t['night_caption']
            try:
                await bot.send_video(
                    chat_id=game.chat_id,
                    video=sunset,
                    caption=caption,
                    parse_mode="HTML"
                )

            except TelegramRetryAfter as e:
                # video limit — textga tushamiz
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=caption,
                    parse_mode="HTML"
                )

            except Exception:
                # boshqa xato bo‘lsa ham text yuboramiz
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=caption,
                    parse_mode="HTML"
                )


            await asyncio.sleep(1)

            msgb = t['alive_players'] + "\n\n"

            for idx, tg_id in enumerate(all_players, 1):
                if tg_id not in alive_players:
                    continue
                user = users_map.get(tg_id)
                if not user:
                    continue
                first_name = user.get("first_name")
                msgb += f'<b>{idx}. <a href="tg://user?id={tg_id}">{first_name}</a></b>\n'

            msgb += t['1_min_day_start']

            await send_safe_message(
                chat_id=game.chat_id,
                text=msgb,
                reply_markup=go_to_bot_inline_btn(game.chat_id,2),
                parse_mode="HTML"
            )

            prepare_night_pending(game_id)
    
            event = games_state[game_id]["runtime"]["night_event"]

            try:
                await asyncio.wait_for(event.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass
            
            await asyncio.sleep(1)
            is_don_alive = False
            roles_map = games_state.get(game_id, {}).get("roles", {})
            for tg_id in games_state[game_id]['alive']:
                if roles_map.get(tg_id) == "don":
                    is_don_alive = True
                    break
            
            if games_state[game_id]['night_actions']['don_kill_target'] is not None and games_state[game_id]['night_actions']['mafia_vote'] is not [] and is_don_alive:
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=t['don_choose']
                )
            else:
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=t['don_not_choose']
                )
            ended = await stop_game_if_needed(game_id)
            if ended:
                return
            games_state[game_id]["meta"]["team_chat_open"] = "no"
            writing_allowed_groups[game.chat_id] = "no"


            # ================= MORNING =================
            caption = t['day_start'].format(day=day)
            try:
                await bot.send_video(
                    chat_id=game.chat_id,
                    video=sunrise,
                    caption=caption,
                    parse_mode="HTML"
                )

            except TelegramRetryAfter as e:
                # video limit — textga tushamiz
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=caption,
                    parse_mode="HTML"
                )

            except Exception:
                # boshqa xato bo‘lsa ham text yuboramiz
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=caption,
                    parse_mode="HTML"
                )

            day += 1
            await asyncio.sleep(1)
            
            games_state[game_id]['meta']['day'] +=1
            await apply_night_actions(game_id)
            await punish_afk_night_players(game_id)
            ended = await stop_game_if_needed(game_id)
            if ended:
                return
            await asyncio.sleep(1)
            # ================= DAY RESET =================
            day_reset(game_id)

        

            alive_after_night = games_state.get(game_id, {}).get("alive", [])
            if len(alive_before_night) == len(alive_after_night):
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=t['no_night_deaths']
                )

            await asyncio.sleep(1)

            # ================= ALIVE LIST AFTER NIGHT =================
            
            
            users_after_night_qs = [users_map[tg_id] for tg_id in alive_after_night if tg_id in users_map]


            

            msg = t['alive_players'] + "\n\n"
            roles_map = games_state.get(game_id, {}).get("roles", {})

            peace_labels = []
            mafia_labels = []
            solo_labels = []

            for idx, tg_id in enumerate(all_players, 1):
                if tg_id not in alive_after_night:
                    continue
                
                user = users_map.get(tg_id)
                if not user:
                    continue
                
                first_name = user.get("first_name")
                msg += f'<b>{idx}. <a href="tg://user?id={tg_id}">{first_name}</a></b>\n'
                role_key = roles_map.get(tg_id)
                if tg_id not in games_state[game_id]['alive']:
                    continue
                
                label = get_role_labels_lang(game.chat_id).get(role_key, "Unknown")

                if role_key in PEACE_ROLES:
                    peace_labels.append(label)
                elif role_key in MAFIA_ROLES_LAB:
                    mafia_labels.append(label)
                elif role_key in SOLO_ROLES:
                    solo_labels.append(label)
                else:
                    peace_labels.append(label)

            def format_role_list(labels: list):
                c = Counter(labels)
                result = []
                for role_label, count in c.items():
                    if count > 1:
                        result.append(f"{role_label} - {count}")
                    else:
                        result.append(role_label)
                random.shuffle(result)
                return ", ".join(result) if result else "—"

            msg += t['from_them']
            peace_roles = format_role_list(peace_labels)
            mafia_roles = format_role_list(mafia_labels)
            solo_roles = format_role_list(solo_labels)
            msg += t['peace_roles'].format(count=len(peace_labels), roles=peace_roles) + "\n"
            msg += t['mafia_roles'].format(count=len(mafia_labels), roles=mafia_roles) + "\n"
            msg += t['solo_roles'].format(count=len(solo_labels), roles=solo_roles)

            msg += t['debate_time']
            await hero_day_actions(game_id)

            await send_safe_message(
                chat_id=game.chat_id,
                text=msg,
                parse_mode="HTML"
            )
            games_state[game_id]['meta']['message_allowed'] = "yes"
            writing_allowed_groups[game.chat_id] = "yes"
            # ================= DISCUSSION =================
            await asyncio.sleep(45)
            ended = await stop_game_if_needed(game_id)
            if ended:
                return
            # ================= START VOTING =================
            await send_safe_message(
                chat_id=game.chat_id,
                text=t['start_voting'],
                reply_markup=go_to_bot_inline_btn(game.chat_id, 3),
                parse_mode="HTML"
            )
            game_day = games_state.get(game_id, {}).get("meta", {}).get("day", 0)
            # har bir tirikka osish keyboard yuboramiz
            for tg_id in alive_after_night:
                game_data = games_state.get(game_id, {})
                night_action = game_data.get("night_actions", {})
                lover_block_target = night_action.get("lover_block_target")
                if lover_block_target == tg_id:
                    continue
                tu = get_lang_text(tg_id)
                try:
                    await send_safe_message(
                        chat_id=tg_id,
                        text=tu['hang_prompt'],
                        reply_markup=action_inline_btn(
                            action="hang",
                            own_id=tg_id,
                            players=users_after_night_qs,
                            game_id=game.id,
                            chat_id=game.chat_id,
                            day=game_day,
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

            prepare_hang_pending(game_id)

            event = games_state[game_id]["runtime"]["hang_event"]
            try:
                await asyncio.wait_for(event.wait(), timeout=45)
            except asyncio.TimeoutError:
                pass
            await asyncio.sleep(1)
            games_state[game_id]["meta"]["day"] +=1

            ended = await stop_game_if_needed(game_id)
            if ended:
                return

            # ================= MOST VOTED =================
            top_voted = get_most_voted_id(game_id)  # siz yozgan function: tie bo'lsa False
            if not top_voted:
                games_state[game_id]['meta']['message_allowed'] = "no"
                writing_allowed_groups[game.chat_id] = "no"
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=t['vote_end'],
                    parse_mode="HTML"
                )
                continue

            voted_user = users_map.get(top_voted)
            if not voted_user:
                await send_safe_message(chat_id=game.chat_id, text="❗ Ovoz berilgan o'yinchi topilmadi.")
                continue

            voted_user_tg_id = voted_user.get('tg_id')
            voted_user_first_name = voted_user.get('first_name')
            # ================= CONFIRM HANG =================
            msg_obj = await send_safe_message(
                chat_id=game.chat_id,
                text=t['voted_user'].format(first_name=voted_user_first_name,tg_id = voted_user_tg_id
                ),
                reply_markup=confirm_hang_inline_btn(
                    voted_user_id=voted_user.get('tg_id'),
                    game_id=game.id,
                    chat_id=game.chat_id,
                    yes=0,
                    no=0
                ),
                parse_mode="HTML"
            )

            games_state[game_id]["day_actions"]["hang_confirm_msg_id"] = msg_obj.message_id
            games_state[game_id]["day_actions"]["hang_target_id"] = voted_user.get('tg_id')

            prepare_confirm_pending(game_id,voted_user.get('tg_id'))

            event = games_state[game_id]["runtime"]["confirm_event"]
            try:
                await asyncio.wait_for(event.wait(), timeout=45)
            except asyncio.TimeoutError:
                pass
            await asyncio.sleep(1)

            games_state[game_id]['meta']['message_allowed'] = "no"
            writing_allowed_groups[game.chat_id] = "no"
            ended = await stop_game_if_needed(game_id)
            if ended:
                return

            try:
                await msg_obj.edit_text(
                    text=t['confirm_hanged'].format(first_name=voted_user_first_name,tg_id = voted_user_tg_id
                    ),
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except Exception:
                pass

            await asyncio.sleep(3)

            # ================= FINAL CONFIRM RESULT =================
            final_vote, yes, no = can_hang(game_id)

            if final_vote == "no":
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=t['no_consenus'].format(yes=yes, no=no),
                    parse_mode="HTML"
                )
                continue
            if voted_user.get('hang_protect',0) >0:
                voted_user['hang_protect'] -=1
                user = User.objects.filter(telegram_id=voted_user.get('tg_id')).first()
                if user:
                    user.hang_protect -=1
                    user.save()
                await send_safe_message(
                    chat_id=game.chat_id,
                    text=t['hang_protect'].format(yes=yes, no=no,
                        first_name=voted_user_first_name,
                        tg_id=voted_user_tg_id
                    ),
                    parse_mode="HTML"
                )
                continue
            

            await send_safe_message(
                chat_id=game.chat_id,
                text=t['hang_no_protect'].format(yes=yes, no=no,
                    first_name=voted_user_first_name,
                    tg_id=voted_user_tg_id
                ),
                parse_mode="HTML"
            )

            # ================= HANG PLAYER =================
            target_id = voted_user.get('tg_id')

            if target_id in games_state[game_id]["alive"]:
                games_state[game_id]["alive"].remove(target_id)

            if target_id not in games_state[game_id]["dead"]:
                games_state[game_id]["dead"].append(target_id)
            games_state[game_id]["day_actions"]["last_hanged"] = target_id
            games_state[game_id]["hanged"].append(target_id)
            

            await asyncio.sleep(2)
            await send_safe_message(
                chat_id=game.chat_id,
                text = t['hanged'].format(first_name=voted_user_first_name,tg_id = voted_user_tg_id,role_label=get_role_labels_lang(game.chat_id).get(roles_map.get(voted_user.get('tg_id')), roles_map.get(voted_user.get('tg_id'))))
            )
            if roles_map.get(voted_user.get('tg_id')) == "don":
                new_don_id = promote_new_don_if_needed(games_state[game_id])
                if new_don_id:
                    await notify_new_don( games_state[game_id], new_don_id )
                    await send_safe_message(
                        chat_id=game.chat_id,
                        text=t['don_killed']
                    )
            if roles_map.get(voted_user.get('tg_id')) == "com":
                new_com_id = promote_new_com_if_needed(games_state[game_id])
                if new_com_id:
                    await notify_new_com( new_com_id)
                    await send_safe_message(
                        chat_id=game.chat_id,
                        text=t['com_killed']
                    )
                ended = await stop_game_if_needed(game_id)
                if ended:
                    return
            
            await asyncio.sleep(2)
            ended = await stop_game_if_needed(game_id)
            if ended:
                return

            # loop davom etadi
            continue

            
    except asyncio.CancelledError:
        print(f"Game {game_id} cancelled.")
        game = Game.objects.filter(id=game_id).first()
        game.is_active_game = False
        game.is_ended = True
        game.is_started = False
        game.save()
        return
    except Exception as e:
        traceback.print_exc()
        return

