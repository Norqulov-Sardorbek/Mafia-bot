import re
import json
import time
import datetime
from aiogram import F
from asyncio import sleep
from dispatcher import dp, bot
from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from aiogram.filters import StateFilter
from mafia_bot.storage import GameStorage
from aiogram.fsm.context import FSMContext 
from django.contrib.auth.hashers import make_password
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from mafia_bot.utils import stones_taken,gsend_taken,giveaways,USER_LANG_CACHE
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery,CallbackQuery
from mafia_bot.models import Game, MoneySendHistory, User,PremiumGroup,MostActiveUser,CasesOpened,GameSettings,GroupTrials,PriceStones, UserRole,BotCredentials, default_end_date
from mafia_bot.state import AddGroupState, BeginInstanceState,SendMoneyState,ChangeStoneCostState,ChangeMoneyCostState,ExtendGroupState,QuestionState,Register,CredentialsState
from mafia_bot.handlers.main_functions import (add_visit, get_mafia_members,get_first_name_from_players, kill, remove_prefix,send_safe_message,get_description_lang,get_hero_level,
                                               mark_confirm_done, mark_hang_done,mark_night_action_done,get_week_range,get_month_range,role_label,get_lang_text,get_role_labels_lang,get_actions_lang)
from mafia_bot.buttons.inline import (action_inline_btn,
    admin_inline_btn, answer_admin, back_btn, cart_inline_btn, change_money_cost, change_stones_cost, com_inline_btn, end_talk_keyboard, geroy_inline_btn,  giveaway_join_btn, group_profile_inline_btn,
    groupes_keyboard, groups_buy_stars, history_groupes_keyboard, language_keyboard, language_keyboard, money_case, pay_for_money_inline_btn, pay_using_stars_inline_btn, role_shop_inline_keyboard,
    shop_inline_btn, start_inline_btn, roles_inline_btn, com_inline_action_btn,pirate_steal_inline_btn,confirm_channel_olmos_inline_btn,
    professor_gift_inline_btn,confirm_hang_inline_btn,groups_inline_btn,group_manage_btn,back_admin_btn,case_inline_btn,claim_chanel_olmos_inline_btn,
    stone_case,begin_instance_inline_btn, take_gsend_stone_btn, take_stone_btn,trial_groupes_keyboard,trial_group_manage_btn,privacy_inline_btn, use_hero_inline_btn
)




# Callbackdan kelganda
@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    await callback.answer()
    tg_id = callback.from_user.id
    user = User.objects.filter(telegram_id=tg_id).first()
    if not user:
        user = User.objects.create(
            telegram_id=tg_id,
            lang ='uz',
            first_name=callback.from_user.first_name,
            username=callback.from_user.username
        )
    t = get_lang_text(int(tg_id))
    user_role = UserRole.objects.filter(user_id=user.id)
    text =""
    for user_r in user_role:
        role_name = dict(get_role_labels_lang(tg_id)).get(user_r.role_key, "Noma'lum rol")
        text += f"🎭 {role_name} -  {user_r.quantity}\n"
    result = MostActiveUser.objects.filter(user_id=user.id).aggregate(
    total_played=Sum('games_played'),
    total_wins=Sum('games_win')
    )

    total_played = result['total_played'] or 0
    total_wins = result['total_wins'] or 0

    await callback.message.edit_text(
        text=t['user_profile'].format(
            first_name=callback.from_user.first_name,
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
        parse_mode="HTML",reply_markup=cart_inline_btn(tg_id)
    )

@dp.callback_query(F.data == "cart")
async def cart_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=shop_inline_btn(callback.from_user.id)
    )


@dp.callback_query(F.data == ("roles_back_main"))
async def back_callback_special(callback: CallbackQuery):
    t = get_lang_text(callback.from_user.id)
    await callback.message.edit_text(
    text=t['greating_message'],
    parse_mode="HTML",
    reply_markup=start_inline_btn(callback.from_user.id)
)
    
@dp.callback_query(F.data == ("language"))
async def language_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        text = "Language / Tilni tanlang / Выберите язык / Dil seçin:",
        reply_markup=language_keyboard()
    )
    
   
# Callbackdan kelganda
@dp.callback_query(F.data.startswith("back_"))
async def back_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    place = callback.data.split("_")[1]
    t = get_lang_text(callback.from_user.id)
    if place== "profile":
        await profile_callback(callback)
    elif place == "admin":
        await callback.message.edit_text(
            text="⚙️ Admin paneli",
            reply_markup=admin_inline_btn()
        )
    elif place == "case":
        await callback.message.edit_text(
        text= t['case_menu'],
        parse_mode="HTML",
        reply_markup=case_inline_btn(callback.from_user.id)
    )
    elif place == "money":
        button = pay_for_money_inline_btn(callback.from_user.id,is_money=True)
        await callback.message.edit_text(
            text=t['payment_method_choose'],
            reply_markup=button
        )
    elif place == "stone":
        button = pay_for_money_inline_btn(callback.from_user.id,is_money=False)
        await callback.message.edit_text(
            text=t['payment_method_choose'],
            reply_markup=button
        )
    elif place == "group":
        chat_id =callback.message.chat.id
        group_trial = GroupTrials.objects.filter(group_id=chat_id).first()
        if not group_trial:
            link = callback.message.chat.username if callback.message.chat.username else ""
            if link == "":
                invite = await bot.create_chat_invite_link(
                chat_id=callback.message.chat.id,
                creates_join_request=False
            )   
                link = invite.invite_link
            group_trial = GroupTrials.objects.create(
                group_id=callback.message.chat.id,
                group_name=callback.message.chat.title if callback.message.chat.title else "",
                group_username=link
            )
        is_active = group_trial.end_date > timezone.now()
        has_stone = group_trial.stones >= 20
        coins = group_trial.coins if group_trial else 0
        active_text = "✅ Aktiv" if is_active else "❌ Aktiv emas"
        next_activation = group_trial.end_date.strftime('%Y-%m-%d %H:%M:%S') if group_trial.end_date else "Noma'lum"
        stones = group_trial.stones if group_trial else 0
        premium_stones = group_trial.premium_stones if group_trial else 0
        premium_end_date = group_trial.end_date.strftime('%Y-%m-%d %H:%M:%S') if group_trial.end_date else "O'tib ketgan"

        await callback.message.answer(text=t['group_profile'].format(
            coins=coins,
            is_active=active_text,
            next_activation=next_activation,
            stones=stones,
            premium_stones=premium_stones,
            premium_end_date=premium_end_date
        ), reply_markup=group_profile_inline_btn(has_stone, chat_id))
        
    elif place == "groups":
        page = 1
        limit = 5
        offset = (page - 1) * limit
        groupes = GroupTrials.objects.all()[offset:offset + limit]
        total = GroupTrials.objects.count()
        total_pages = (total + limit - 1) // limit
        
        
        group_list = "\n".join([
        f"{i+1}. <a href='{group.group_username}'>{group.group_name}</a>"
        if group.group_username
        else f"{i+1}. {group.group_name}"
        for i, group in enumerate(groupes)
        ])

        await callback.message.edit_text(
            text=f"Obunadagi guruhlar (sahifa {page}/{total_pages}):\n\n{group_list}",
            reply_markup=trial_groupes_keyboard(questions=groupes, page=page, total=total, per_page=limit))
        
        
        


# Callbackdan kelganda
@dp.callback_query(F.data.startswith("buy_"))
async def buy_callback(callback: CallbackQuery):
    thing_to_buy = callback.data.split("_")[1]
    price = callback.data.split("_")[2]
    tg_id = callback.from_user.id
    user = User.objects.filter(telegram_id=callback.from_user.id).first()
    result = MostActiveUser.objects.filter(user_id=user.id).aggregate(
    total_played=Sum('games_played'),
    total_wins=Sum('games_win')
)

    total_played = result['total_played'] or 0
    total_wins = result['total_wins'] or 0

    if not user:
        user = User.objects.create(
            telegram_id=callback.from_user.id,
            lang ='uz',
            first_name=callback.from_user.first_name,
            username=callback.from_user.username
        )
    t = get_lang_text(tg_id)
    if thing_to_buy == "protection":
        if user.coin >= 250:
            user.coin -= 250
            user.protection += 1
            user.save()
            await callback.message.edit_text(
                 text=t['user_profile'].format(
                first_name=callback.from_user.first_name,
                coin=user.coin,
                stones=user.stones,
                protection=user.protection,
                hang_protect=user.hang_protect,
                docs=user.docs,
                geroy_protect=user.geroy_protection,
                wins=total_wins,
                all_played=total_played,
                text=""
            ),
                parse_mode="HTML",
                reply_markup=cart_inline_btn(tg_id)
            )
        else:
            await callback.answer(text=t['not_enough_money'], show_alert=True)
    elif thing_to_buy == "docs":
        if user.coin >= 250:
            user.coin -= 250
            user.docs += 1
            user.save()
            await callback.message.edit_text(
                text=t['user_profile'].format(
                    first_name=callback.from_user.first_name,
                    coin=user.coin,
                    stones=user.stones,
                    protection=user.protection,
                    hang_protect=user.hang_protect,
                    wins=total_wins,
                    all_played=total_played,
                    docs=user.docs,
                    geroy_protect=user.geroy_protection,
                    text=""
                ),
                parse_mode="HTML",
                reply_markup=cart_inline_btn(tg_id)
            )
        else:
            await callback.answer(text=t['not_enough_money'], show_alert=True)
    elif thing_to_buy == "hangprotect":
        if price == "1" and user.coin >= 20000:
            user.coin -= 20000
            user.hang_protect += 1
            user.save()
        elif price == "2" and user.stones >= 20:
            user.stones -= 20
            user.hang_protect += 1
            user.save()
        else:
            await callback.answer(text=t['not_enough_money'], show_alert=True)
            return
        await callback.message.edit_text(
                text=t['user_profile'].format(
                    first_name=callback.from_user.first_name,
                    coin=user.coin,
                    stones=user.stones,
                    protection=user.protection,
                    hang_protect=user.hang_protect,
                    docs=user.docs,
                    geroy_protect=user.geroy_protection,
                    wins=total_wins,
                    all_played=total_played,
                    text=""
                ),
                parse_mode="HTML",
                reply_markup=cart_inline_btn(tg_id)
            )
    elif thing_to_buy == "activerole":
        await callback.message.edit_text(
            text=t['buy_role'],
            reply_markup=role_shop_inline_keyboard(tg_id)
        )
    elif thing_to_buy == "geroyprotect":
        if user.coin >= 10000:
            user.coin -= 10000
            user.geroy_protection += 1
            user.save()
            await callback.message.edit_text(
                text=t['user_profile'].format(
                    first_name=callback.from_user.first_name,
                    coin=user.coin,
                    stones=user.stones,
                    protection=user.protection,
                    hang_protect=user.hang_protect,
                    docs=user.docs,
                    geroy_protect=user.geroy_protection,
                    wins=total_wins,
                    all_played=total_played,
                    text=""
                ),
                parse_mode="HTML",
                reply_markup=cart_inline_btn(tg_id)
            )
        else:
            await callback.answer(text=t['not_enough_money'], show_alert=True)

@dp.callback_query(F.data.startswith("active_"))
async def buy_role_callback(call: CallbackQuery, state: FSMContext):
    
    role_key = call.data.split("_")[1]
    price = int(call.data.split("_")[2])
    
    if price<75:
        currency = "stones"
    else:
        currency = "money"

    user = User.objects.filter(telegram_id=call.from_user.id).first()
    if not user:
        user = User.objects.create(
            telegram_id=call.from_user.id,
            lang ='uz',
            first_name=call.from_user.first_name,
            username=call.from_user.username
        )
    t = get_lang_text(call.from_user.id)
    if currency == "stones":
        if user.stones < price:
            return await call.answer(t['not_enough_stones'], show_alert=True)
        user.stones -= price

    if currency == "money":
        if user.coin < price:
            return await call.answer(t['not_enough_money'], show_alert=True)
        user.coin -= price

    await user.asave(update_fields=["stones", "coin"])
    user_role, created = UserRole.objects.get_or_create(user=user, role_key=role_key)
    if not created:
        user_role.quantity += 1
    user_role.save()

    await call.answer(t['role_bought'], show_alert=True)

    await call.message.edit_text(
        text=t['role_bought'] + "\n\n" + t['buy_another_role'],
        reply_markup=role_shop_inline_keyboard(call.from_user.id)
    )

    

# Callbackdan kelganda
@dp.callback_query(F.data == ("role_menu"))
async def roles_callback(callback: CallbackQuery):
    await callback.answer()
    t = get_lang_text(callback.from_user.id)
    await callback.message.edit_text(t['roles_list'],reply_markup=roles_inline_btn(callback.from_user.id))


@dp.callback_query(F.data.startswith("money_"))
async def buy_money_handler(callback: CallbackQuery):
    await callback.answer()
    t = get_lang_text(callback.from_user.id)
    if callback.data == "money_stone":
        button = pay_for_money_inline_btn(callback.from_user.id, is_money=False)
    else:
        button = pay_for_money_inline_btn(callback.from_user.id, is_money=True)
    await callback.message.edit_text(
        text=t['payment_method_choose'],
        reply_markup=button
    )
    

@dp.callback_query(F.data.startswith("p2p_"))
async def p2p_callback(callback: CallbackQuery):
    await callback.answer()
    which = callback.data.split("_")[1]
    cost = PriceStones.objects.first()
    tg_id = callback.from_user.id
    t = get_lang_text(callback.from_user.id)
    if not cost:
        cost = PriceStones.objects.create()
    if which == "money":
        money = cost.money_in_money
        text = t['money_in_money'].format(money=money)
        await callback.message.edit_text(
        text=text,
        reply_markup=back_btn(tg_id, "money")
    )
    else:
        stone = cost.stone_in_money
        await callback.message.edit_text(
        text=t['stone_in_money'].format(stone=stone),
        reply_markup=back_btn(tg_id, "stone")
    )
        
@dp.callback_query(F.data.startswith("star_"))
async def star_callback(callback: CallbackQuery):
    await callback.answer()
    which = callback.data.split("_")[1]
    t = get_lang_text(callback.from_user.id)
    if which == "money":
        await callback.message.edit_text(
            text =t['money_in_stars'],
            reply_markup=pay_using_stars_inline_btn(is_money=True)
        )
    elif which == "stone":
        await callback.message.edit_text(
            text = t['stone_in_stars'],
            reply_markup=pay_using_stars_inline_btn(is_money=False)
        )
    elif which == "group":
        await callback.message.edit_text(
            text = t['choose_quantity'],
            reply_markup=groups_buy_stars(callback.message.chat.id)
        )
    
    


@dp.callback_query(F.data.startswith("roles_"))
async def roles_specific_callback(callback: CallbackQuery):
    role_name = callback.data.split("_")[1]
    DESCRIPTIONS = get_description_lang(callback.from_user.id)
    if role_name in DESCRIPTIONS:
        await callback.answer(text=DESCRIPTIONS[role_name], show_alert=True)


@dp.callback_query(F.data.startswith("doc_"))
async def doc_heal_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")    
    target_id = parts[1]  
    chat_id = int(parts[3])
    day = parts[4]
    doctor_id = callback.from_user.id

    game = await GameStorage.load(int(parts[2]))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('doc_heal')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not doctor_id in game["alive"]:
        return
    
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('doc_heal')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        try:
            await send_safe_message(
            chat_id=chat_id,
            text=tg['no_go_doc']
        )
        except:
            pass
        return
    
    target_id = int(target_id)
    # doc o'zini 1 martadan ko'p heal qila olmaydi
    if target_id == doctor_id:
        used_self = game["limits"]["doc_self_heal_used"]
        if doctor_id in used_self:
            return
        used_self.add(doctor_id)

    # ✅ night action saqlash
    game["night_actions"]["doc_target"] = target_id
    await  add_visit(game=game, visitor_id=doctor_id, house_id=target_id, invisible=False)


    # username olish (players object bo'lsa)
    target_name = get_first_name_from_players(target_id)

    text = f"{get_actions_lang(callback.from_user.id).get('doc_heal')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}"

    await callback.message.edit_text(text=text, parse_mode="HTML")
    try:
        await send_safe_message(
            chat_id=chat_id,
            text=tg['go_doc']
        )
    except:
        pass
    

@dp.callback_query(F.data.startswith("daydi_"))
async def daydi_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")
    house_id = parts[1]
    chat_id = int(parts[3])
    day = parts[4]

    daydi_id = callback.from_user.id

    game = await GameStorage.load(int(parts[2]))
    if not game.data:
        return
    
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('daydi_watch')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not daydi_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if house_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('daydi_watch')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        try:
            await send_safe_message(
                chat_id=chat_id,
                text=tg['daydi_no_go']
            )
        except:
            pass
        return
    house_id = int(house_id)

    # ✅ Daydi qayerga bordi
    game["night_actions"]["daydi_house"] = house_id
    

    # username topish (players object list bo‘lsa)
    target_name = get_first_name_from_players(house_id)
    await callback.message.edit_text(
        text=f"{get_actions_lang(callback.from_user.id).get('daydi_watch')}\n\n<a href='tg://user?id={house_id}'>{target_name}</a> {t['action_choose']}",
        parse_mode="HTML"
    )
    try:
        await send_safe_message(chat_id=chat_id, text=tg['daydi_go'])
    except:
        pass
    


@dp.callback_query(F.data.startswith("com_"))
async def com_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")
    action = parts[1]     
    chat_id = int(parts[3])
    day = parts[4]
    com_id = callback.from_user.id
    game = await GameStorage.load(int(parts[2]))
    if not game.data:
        return
    if not com_id in game["alive"]:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('com_deside')}\n\n{t['late']}", parse_mode="HTML")
        return
    mark_night_action_done(game, callback.from_user.id)
    if action == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('com_deside')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        try:
            await send_safe_message(
                chat_id=chat_id,
                text=tg['com_no_go']
            )
        except:
            pass
        return
    elif action == "back":
        await callback.message.edit_text(
            text=get_actions_lang(callback.from_user.id).get("com_deside"),
            reply_markup=com_inline_btn(game_id=int(parts[2]), chat_id=chat_id,day=day)
        )
        return
    
    if action == "shoot":
        try:
            await send_safe_message(chat_id=chat_id, text=tg['com_shoot'])
        except:
            pass
        await callback.message.edit_text(
            text=get_actions_lang(callback.from_user.id).get("com_shoot"),
            reply_markup=await com_inline_action_btn(action="shoot",chat_id=chat_id, game_id=int(parts[2]),com_id=com_id,day=day)
        )
        return

    try:
        await send_safe_message(chat_id=chat_id, text=tg['com_check'])
    except:
        pass
    await callback.message.edit_text(
        text=get_actions_lang(callback.from_user.id).get("com_check"),
        reply_markup=await com_inline_action_btn(action="search",chat_id=chat_id, game_id=int(parts[2]),com_id=com_id,day=day)
    )


@dp.callback_query(F.data.startswith("shoot_"))
async def com_shoot_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")
    target_id = int(parts[1])

    com_id = callback.from_user.id

    game = await GameStorage.load(int(parts[2]))
    day = parts[3]
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{t.get('com_shoot')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not com_id in game["alive"]:
        return
    

    game["night_actions"]["com_shoot_target"] = target_id
    await add_visit(game, com_id, target_id, False)


    target_name = get_first_name_from_players( target_id)

    await callback.message.edit_text(
        text=f"{get_actions_lang(callback.from_user.id).get('com_shoot')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}.",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("search_"))
async def com_protect_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")
    target_id = int(parts[1])
    day = parts[3]
    com_id = callback.from_user.id

    game = await GameStorage.load(int(parts[2]))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('com_check')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not com_id in game["alive"]:
        return
   

    # ✅ Action saqlaymiz
    game["night_actions"]["com_check_target"] = target_id
    await add_visit(game, com_id, target_id, False)


    target_name = get_first_name_from_players( target_id)

    await callback.message.edit_text(
        text=f"{get_actions_lang(callback.from_user.id).get('com_check')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}.",
        parse_mode="HTML"
    )

    
@dp.callback_query(F.data.startswith("lover_"))
async def lover_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")
    target_id = parts[1]
    chat_id = int(parts[3])
    day = parts[4]
    lover_id = callback.from_user.id

    game = await GameStorage.load(int(parts[2]))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('lover_block')}\n\n {t['late']}", parse_mode="HTML")
        return
    if not lover_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('lover_block')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        try:
            await send_safe_message(
                chat_id=chat_id,
                text=tg['lover_no_go']
            )
        except:
            pass
        return
    target_id = int(target_id)
    # ✅ lover action saqlash
    game["night_actions"]["lover_block_target"] = target_id
    await add_visit(game=game, visitor_id=lover_id, house_id=target_id, invisible=False)

    target_name = get_first_name_from_players(target_id)

    text = f"{get_actions_lang(callback.from_user.id).get('lover_block')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}."

    await callback.message.edit_text(text=text, parse_mode="HTML")

    await send_safe_message(
        chat_id=chat_id,
        text=tg['lover_go']
    )
    return

@dp.callback_query(F.data.startswith("killer_"))
async def killer_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")
    target_id = parts[1]
    chat_id = int(parts[3])
    day = parts[4]
    killer_id = callback.from_user.id

    game = await GameStorage.load(int(parts[2]))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('killer_kill')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not killer_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('killer_kill')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=chat_id,
            text=tg['killer_no_go']
        )
        return
    target_id = int(target_id)
    # ✅ killer action saqlash
    game["night_actions"]["killer_target"].append(target_id)

    target_name = get_first_name_from_players(target_id)
    await add_visit(game=game, visitor_id=killer_id, house_id=target_id, invisible=False)

    text = f"{get_actions_lang(callback.from_user.id).get('killer_kill')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}."

    await callback.message.edit_text(text=text, parse_mode="HTML")

    await send_safe_message(
        chat_id=chat_id,
        text=tg['killer_go']
    )
    return

@dp.callback_query(F.data.startswith("santa_"))
async def santa_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")
    target_id = parts[1]
    chat_id = int(parts[3])
    day = parts[4]
    santa_id = callback.from_user.id

    game = await GameStorage.load(int(parts[2]))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('santa')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not santa_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('santa')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=chat_id,
            text=tg['santa_no_go']
        )
        return
    target_id = int(target_id)
    # ✅ killer action saqlash
    user = User.objects.filter(telegram_id=target_id).first()
    if not user:
        user = User.objects.create(
            telegram_id=target_id,
            lang ='uz',
            first_name=callback.from_user.first_name,
            username=callback.from_user.username
        )
    user.coin += 20
    user.save()
    target_name = get_first_name_from_players(target_id)
    await add_visit(game=game, visitor_id=santa_id, house_id=target_id, invisible=False)

    text = f"{get_actions_lang(callback.from_user.id).get('santa')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}."

    await callback.message.edit_text(text=text, parse_mode="HTML")
    await send_safe_message(
        chat_id=target_id,
        text=t['santa_gift']
    )
    await send_safe_message(
        chat_id=chat_id,
        text=tg['santa_go']
    )
    return

@dp.callback_query(F.data.startswith("kaldun_"))
async def kaldun_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)

    parts = callback.data.split("_")
    target_id = parts[1]
    chat_id = int(parts[3])
    day = parts[4]
    kaldun_id = callback.from_user.id

    game = await GameStorage.load(int(parts[2]))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('kaldun_spell')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not kaldun_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('kaldun_spell')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=chat_id,
            text=tg['kaldun_no_go']
        )
        return

    target_id = int(target_id)

    # ✅ kaldun action saqlash
    game["night_actions"]["kaldun_target"] = target_id
    
    await add_visit(game=game, visitor_id=kaldun_id, house_id=target_id, invisible=False)
    target_name = get_first_name_from_players(target_id)

    text = f"{get_actions_lang(callback.from_user.id).get('kaldun_spell')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}."

    await callback.message.edit_text(text=text, parse_mode="HTML")

    await send_safe_message(
        chat_id=chat_id,
        text=tg["kaldun_go"]
    )
    return


@dp.callback_query(F.data.startswith("drunk_"))
async def drunk_callback(callback: CallbackQuery):
    await callback.answer()

    parts = callback.data.split("_")
    target_raw = parts[1]
    game_id = int(parts[2])
    chat_id = int(parts[3])
    day = parts[4]
    drunk_id = callback.from_user.id

    game = await GameStorage.load(game_id)
    if not game.data:
        return
    t = get_lang_text(drunk_id)
    tu = get_lang_text(chat_id)
    if day != str(game['meta']['day']):
        await callback.message.edit_text(
            f"{get_actions_lang(drunk_id).get('drunk_action')}\n\n{t['late']}",
            parse_mode="HTML"
        )
        return

    if drunk_id not in game["alive"]:
        return

    mark_night_action_done(game, drunk_id)
    await callback.message.edit_reply_markup(None)

    if target_raw == "no":
        await callback.message.edit_text(
            f"{get_actions_lang(drunk_id).get('drunk_action')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=chat_id,
            text=tu['drunk_no_go']
        )
        return

    target_id = int(target_raw)

    # 🔒 GAME LOGIC — O‘ZGARMAGAN
    game["night_actions"]["drunk_target"] = target_id
    await add_visit(game=game, visitor_id=drunk_id, house_id=target_id, invisible=False)

    target_name = get_first_name_from_players(target_id)

    await send_safe_message(
        chat_id=chat_id,
        text=tu['drunk_go']
    )

    await callback.message.edit_text(
        f"{get_actions_lang(drunk_id).get('drunk_action')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("don_"))
async def don_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    day = callback.data.split("_")[4]
    
    don_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('don_kill')}\n\n{t['late']}", parse_mode="HTML")
        return
    
    if not don_id in game["alive"]:
        return
    
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('don_kill')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        
        return
    
    # ✅ night action saqlash
    game["night_actions"]["don_kill_target"] = int(target_id)
    await add_visit(game=game, visitor_id=don_id, house_id=target_id, invisible=False)
    
    
    target_name = get_first_name_from_players(int(target_id))
    mafia_name = get_first_name_from_players(don_id)
    mafia_members = get_mafia_members(int(game_id))
    

    text_for_mafia = (
        f"🤵🏻 Don <a href='tg://user?id={don_id}'>{mafia_name}</a> - <a href='tg://user?id={target_id}'>{target_name}</a> uchun ovoz berdi"
    )

    for member_id in mafia_members:
        if member_id == don_id:
            continue
        try:
            await send_safe_message(
                chat_id=member_id,
                text=text_for_mafia,
                parse_mode="HTML"
            )
        except Exception as e:
            pass
    
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('don_kill')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")
    

@dp.callback_query(F.data.startswith("mafia_"))
async def mafia_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    day = callback.data.split("_")[3]
    
    mafia_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('mafia_vote')}\n\n{t['late']}", parse_mode="HTML")
        return
    
    if not mafia_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('mafia_vote')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        return
    # ✅ night action saqlash
    game["night_actions"]["mafia_vote"].append(int(target_id))
    
    
    target_name = get_first_name_from_players(int(target_id))
    mafia_name = get_first_name_from_players(mafia_id)
    mafia_members = get_mafia_members(int(game_id))
    

    text_for_mafia = (
        f"🤵🏼 Mafiya a'zosi <a href='tg://user?id={mafia_id}'>{mafia_name}</a> - <a href='tg://user?id={target_id}'>{target_name}</a> uchun ovoz berdi"
    )

    for member_id in mafia_members:
        if member_id == mafia_id:
            continue

        try:
            await send_safe_message(
                chat_id=member_id,
                text=text_for_mafia,
                parse_mode="HTML"
            )
        except Exception as e:
            pass
    
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('mafia_vote')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")


@dp.callback_query(F.data.startswith("adv_"))
async def adv_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = int(callback.data.split("_")[2])
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    adv_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('adv_mask')}\n {t['late']}", parse_mode="HTML")
        return
    
    if not adv_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('adv_mask')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['adv_no_go']
        )
        return
    # ✅ night action saqlash
    game["night_actions"]["advokat_target"] = int(target_id)
    await add_visit(game=game, visitor_id=adv_id, house_id=target_id, invisible=False)
    
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['adv_go'],
    )
    
    target_name = get_first_name_from_players(int(target_id))
    adv_name = get_first_name_from_players(adv_id)
    mafia_members = get_mafia_members(int(game_id))
    

    text_for_mafia = (
        f"👨🏼‍💼 Advokat {adv_name} tanlovi: <a href='tg://user?id={target_id}'>{target_name}</a>"
    )

    for member_id in mafia_members:
        if member_id == adv_id:
            continue

        try:
            await send_safe_message(
                chat_id=member_id,
                text=text_for_mafia,
                parse_mode="HTML"
            )
        except Exception as e:
            pass
    

    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('adv_mask')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")


@dp.callback_query(F.data.startswith("spy_"))
async def spy_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    spy_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('spy_check')}\n\n{t['late']}", parse_mode="HTML")
        return
    
    if not spy_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('spy_check')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['spy_no_go']
        )
        return
    
    # ✅ night action saqlash
    game["night_actions"]["spy_target"] = int(target_id)
    await add_visit(game=game, visitor_id=spy_id, house_id=target_id, invisible=False)
    
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['spy_go'],
    )
    
    target_name = get_first_name_from_players(int(target_id))
    spy_name = get_first_name_from_players(spy_id)
    mafia_members = get_mafia_members(int(game_id))
    text_for_mafia = (
        f"🦇 Ayg'oqchi {spy_name} tanlovi: <a href='tg://user?id={target_id}'>{target_name}</a>"
    )
    for member_id in mafia_members:
        if member_id == spy_id:
            continue

        try:
            await send_safe_message(
                chat_id=member_id,
                text=text_for_mafia,
                parse_mode="HTML"
            )
        except Exception as e:
            pass
    
    
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('spy_check')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")


@dp.callback_query(F.data.startswith("lab_"))
async def lab_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = int(callback.data.split("_")[2])
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    
    lab_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('lab_action')}\n\n{t['late']}", parse_mode="HTML")
        return
    
    if not lab_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('lab_action')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['lab_no_go']
        )
        return
    
    # ✅ night action saqlash
    game["night_actions"]["lab_target"] = int(target_id)
    await add_visit(game=game, visitor_id=lab_id, house_id=target_id, invisible=False)
    
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['lab_go'],
    )
    
    target_name = get_first_name_from_players(int(target_id))
    
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('lab_action')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")


@dp.callback_query(F.data.startswith("arrow_"))
async def arrow_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    
    arrow_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('arrow_kill')}\n\n{t['late']}", parse_mode="HTML")
        return
    
    if not arrow_id in game["alive"]:
        return
    
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('arrow_kill')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['arrow_no_go']
        )   
        return
    # ✅ night action saqlash
    game["night_actions"]["arrow_target"] = int(target_id)
    await add_visit(game=game, visitor_id=arrow_id, house_id=target_id, invisible=True)
    
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['arrow_go'],
    )
    
    target_name = get_first_name_from_players(int(target_id))
    
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('arrow_kill')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")


@dp.callback_query(F.data.startswith("trap_"))
async def trap_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    
    trap_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('trap_action')}\n\n{t['late']}", parse_mode="HTML")
        return
    
    if not trap_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('trap_action')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['trap_no_go']
        )
        return
    
    # ✅ night action saqlash
    game["night_actions"]["trap_house"] = int(target_id)
    
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['trap_go'],
    )
    
    target_name = get_first_name_from_players(int(target_id))
    
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('trap_action')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")


@dp.callback_query(F.data.startswith("snyper_"))
async def snyper_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    
    snyper_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('snyper_kill')}\n\n{t['late']}", parse_mode="HTML")
        return
    
    if not snyper_id in game["alive"]:
        return
    
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('snyper_kill')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['snyper_no_go']
        )   
        return
    
    # ✅ night action saqlash
    game["night_actions"]["snyper_target"] = int(target_id)
    await add_visit(game=game, visitor_id=snyper_id, house_id=target_id, invisible=True)
    
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['snyper_go']
    )
    
    target_name = get_first_name_from_players(int(target_id))
    
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('snyper_kill')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")



@dp.callback_query(F.data.startswith("traitor_"))
async def spy_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    
    traitor_id = callback.from_user.id
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('traitor_choose')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not traitor_id in game["alive"]:
        return
    
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('traitor_choose')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['traitor_no_go']
        )
        return
    
    # ✅ night action saqlash
    game["night_actions"]["traitor_target"] = int(target_id)
    await add_visit(game=game, visitor_id=traitor_id, house_id=target_id, invisible=False)
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['traitor_go']
    )
    target_name = get_first_name_from_players(int(target_id))
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('traitor_choose')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")
    


@dp.callback_query(F.data.startswith("snowball_"))
async def snowball_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    
    snowball_id = callback.from_user.id
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('snowball_kill')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not snowball_id in game["alive"]:
        return
    
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('snowball_kill')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['snowball_no_go']
        )
        return
    
    # ✅ night action saqlash
    game["night_actions"]["snowball_target"] = int(target_id)
    await add_visit(game=game, visitor_id=snowball_id, house_id=target_id, invisible=False)
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['snowball_go']
    )
    target_name = get_first_name_from_players(int(target_id))
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('snowball_kill')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")



@dp.callback_query(F.data.startswith("pirate_"))
async def pirate_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    chat_id = int(callback.data.split("_")[3])
    pirate_id = callback.from_user.id
    day = callback.data.split("_")[4]
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('pirate_steal')}\n\n{t['late']}", parse_mode="HTML")
        return
    if not pirate_id in game["alive"]:
        return
    
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('pirate_steal')}\n\n{t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['pirate_no_go']
        )
        return
    
    # ✅ night action saqlash
    game["night_actions"]["pirate"]['target_id'] = int(target_id)
    game["night_actions"]["pirate"]['pirate_id'] = int(pirate_id)
    game["night_actions"]["pirate"]['result'] = "no"
    await add_visit(game=game, visitor_id=pirate_id, house_id=target_id, invisible=False)

    await send_safe_message(
        chat_id=int(target_id),
        text=t['pay_pirate'],
        reply_markup=pirate_steal_inline_btn(pirate_id=pirate_id,game_id=int(game_id),day=day)
    )
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['pirate_go'],
    )
    target_name = get_first_name_from_players(int(target_id))
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('pirate_steal')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")


@dp.callback_query(F.data.startswith("pirpay_"))
async def pirpay_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    parts = callback.data.split("_")
    confirmation = str(parts[1])
    pirate_id = int(parts[2])
    game_id = int(parts[3])
    day = parts[4]
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    if not day == str(game_day):
        await callback.message.edit_text(text=t['late'], parse_mode="HTML")
        return
    if not pirate_id in game["alive"]:
        return
    target_id = callback.from_user.id
    if not target_id in game["alive"]:
        return
    target_name = get_first_name_from_players(int(target_id))
    if confirmation == "no":
        await callback.message.edit_text(text=f"👺 {t['pirate_pay_no']}")
        await send_safe_message(
            chat_id=pirate_id,
            text=t['pirate_answer'].format(target_name=target_name,target_id=target_id)
        )
        game['night_actions']['pirate']['result'] = "no"
        return
    target_player = User.objects.filter(telegram_id=int(target_id)).first()
    if not target_player:
        target_player = User.objects.create(
            telegram_id=target_id,
            lang ='uz',
            first_name=callback.from_user.first_name,
            username=callback.from_user.username
        )
    if target_player.coin < 10:
        await callback.message.edit_text(text=t['pirate_pay_no'])
        await send_safe_message(
            chat_id=pirate_id,
            text=t['pirate_no_money'].format(target_name=target_name,target_id=target_id)
        )
        game['night_actions']['pirate']['result'] = "no_money"
        return
    target_player.coin -= 10
    target_player.save()
    pirate_player = User.objects.filter(telegram_id=int(pirate_id)).first()
    pirate_player.coin += 10
    pirate_player.save()
    game['night_actions']['pirate']['result'] = "success"
    await callback.message.edit_text(text=t['pirate_pay_yes'])
    

@dp.callback_query(F.data.startswith("professor_"))
async def professor_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = int(callback.data.split("_")[2])
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    
    professor_id = callback.from_user.id
    
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('professor_choose')}\n\n{t['late']}", parse_mode="HTML")
        return
    
    if not professor_id in game["alive"]:
        return
    mark_night_action_done(game, callback.from_user.id)
    if target_id == "no":
        # hech narsa qilmaslik
        await callback.message.edit_text(
            text=f"{get_actions_lang(callback.from_user.id).get('professor_choose')}\n\n {t['action_no_choose']}",
            parse_mode="HTML"
        )
        await send_safe_message(
            chat_id=int(chat_id),
            text=tg['professor_no_go']
        )
        return
    
    # ✅ night action saqlash
    game["night_actions"]["professor"]['target_id'] = int(target_id)
    game["night_actions"]["professor"]['chosen'] = "die"
    await add_visit(game=game, visitor_id=professor_id, house_id=target_id, invisible=False)
    
    await send_safe_message(
        chat_id=int(chat_id),
        text=tg['professor_go']
    )
    
    target_name = get_first_name_from_players(int(target_id))
    await send_safe_message(
        chat_id=int(target_id),
        text=t['professor_gift'],
        reply_markup=professor_gift_inline_btn(game_id=int(game_id),day=day,professor_id=professor_id,chat_id=chat_id)
    )
    
    await callback.message.edit_text(text=f"{get_actions_lang(callback.from_user.id).get('professor_choose')}\n\n<a href='tg://user?id={target_id}'>{target_name}</a> {t['action_choose']}")


@dp.callback_query(F.data.startswith("prof_"))
async def prof_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    parts = callback.data.split("_")
    choose = str(parts[1])
    game_id = int(parts[2])
    day = parts[3]
    professor_id = int(parts[4])
    chat_id = int(parts[5])
    prof_id = callback.from_user.id
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"🎩 {t['late']}", parse_mode="HTML")
        return
    if not prof_id in game["alive"]:
        return
    if choose == "die":
        reward = t['die']
        game["night_actions"]["professor"]['chosen'] = "die"
    elif choose == "empty":
        reward = t['empty']
        game["night_actions"]["professor"]['chosen'] = "empty"
        
    else:
        reward = t['hero']
        user = User.objects.filter(telegram_id=int(prof_id)).first()
        if user and user.is_hero:
             await send_safe_message(
                chat_id=prof_id,
                text=t['hero_day_action'],
                reply_markup=use_hero_inline_btn(
                    game_id=game_id,
                    chat_id=chat_id,
                    tg_id = prof_id,
                    day=day
                )
            )
            
        game["night_actions"]["professor"]['chosen'] = "hero"
    
    mark_night_action_done(game, callback.from_user.id)
    
    await callback.message.edit_text(text=t['prof_chosen'].format(reward=reward))
    await send_safe_message(
        chat_id=professor_id,
        text=f"<a href='tg://user?id={prof_id}'>{get_first_name_from_players(prof_id)}</a> : {reward} ",
    )

@dp.callback_query(F.data.startswith("hang_"))
async def hang_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(None)
    target_id = callback.data.split("_")[1]
    game_id = callback.data.split("_")[2]
    chat_id = int(callback.data.split("_")[3])
    day = callback.data.split("_")[4]
    shooter_id = callback.from_user.id
    shooter_name = callback.from_user.first_name
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    game_day = game['meta']['day']
    t = get_lang_text(callback.from_user.id)
    tg= get_lang_text(chat_id)
    if not day == str(game_day):
        await callback.message.edit_text(text=f"{t['hang_action']}\n\n{t['late']}", parse_mode="HTML")
        return
    if target_id == "no":
        await callback.message.edit_text(text=f"{t['hang_action']}\n\n{t['action_no_choose']}", parse_mode="HTML")
        await send_safe_message(
            chat_id=chat_id,
            text=f"🚷 <a href='tg://user?id={shooter_id}'>{shooter_name}</a> {tg['no_hang_choose']}"
        )
        game["day_actions"]['votes'].append("no_lynch")
        return
    
    game["day_actions"]['votes'].append(int(target_id))
    mark_hang_done(int(game_id), callback.from_user.id)
    
    user_map = game.get("users_map",{})
    user = user_map.get(int(target_id))
    await callback.message.edit_text(text=f"{t['hang_action']}\n\n<a href='tg://user?id={target_id}'>{user.get('first_name')}</a> {t['action_choose']}", parse_mode="HTML")
    await send_safe_message(
        chat_id=chat_id,
        text=f"<a href='tg://user?id={shooter_id}'>{shooter_name}</a> -> <a href='tg://user?id={target_id}'>{user.get('first_name')}</a> {tg['hang_choose']}"
    )

        
@dp.callback_query(F.data.startswith("con_"))
async def confirm_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    confirmation = str(parts[1])
    target_id = int(parts[2])
    game_id = int(parts[3])
    chat_id = int(parts[4])
    voter_id = callback.from_user.id
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    t = get_lang_text(callback.from_user.id)
    if not voter_id in game["alive"]:
        if voter_id in game["dead"]:
            await callback.answer(text=t['dead_cant_vote'])
            return
        if voter_id not in game["players"]:
            await callback.answer(text=t['no_player'])
        return
    if target_id == voter_id:
        await callback.answer(text=t['cant_vote_self'])
        return
    if voter_id == game["night_actions"]["lover_block_target"]:
        await callback.answer(text=t['lover_waiting'])
        return
    
    if not target_id in game["alive"]:
        return
    if confirmation == "yes":
        if voter_id not in game["day_actions"]["hang_yes"]:
            game["day_actions"]["hang_yes"].append(voter_id)
        else:
            game["day_actions"]["hang_yes"].remove(voter_id)
        if voter_id in game["day_actions"]["hang_no"]:
            game["day_actions"]["hang_no"].remove(voter_id)
        
    else:
        if voter_id not in game["day_actions"]["hang_no"]:
            game["day_actions"]["hang_no"].append(voter_id)
        else:
            game["day_actions"]["hang_no"].remove(voter_id)
        if voter_id in game["day_actions"]["hang_yes"]:
            game["day_actions"]["hang_yes"].remove(voter_id)
    
    mark_confirm_done(int(game_id), voter_id)
    
    
    await callback.answer(text=t['vote_accepted'])
    yes = len(game["day_actions"]["hang_yes"])
    no = len(game["day_actions"]["hang_no"])
    
    await update_hang_votes(voter_id=target_id,game_id=int(game_id),chat_id=chat_id,yes=yes,no=no)
    
    
async def update_hang_votes(voter_id,game_id: int, chat_id: int, yes: int, no: int):
    game = await GameStorage.load(int(game_id))
    if not game.data:
        return
    msg_id = game['day_actions']['hang_confirm_msg_id']
    try:
        await bot.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=msg_id,
        reply_markup=confirm_hang_inline_btn(voted_user_id=voter_id,game_id=int(game_id),chat_id=chat_id,yes=yes,no=no)
    )
    except Exception as e:
        pass
    
@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.callback_query(F.data.startswith("pul_"))
async def pul_star_callback(callback: CallbackQuery):
    await callback.answer()

    parts = callback.data.split("_")
    money_amount = int(parts[1])
    star_amount = int(parts[2])
    user_id = callback.from_user.id

    prices = [
        LabeledPrice(label=f"💶 {money_amount} sotib olish", amount=star_amount)
    ]
    t = get_lang_text(callback.from_user.id)

    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=t['buy_money_group'],
        description=t['buy_stone_group_desc'],
        payload=f"pul_{money_amount}_{star_amount}_{user_id}",
        currency="XTR",
        prices=prices
    )

@dp.callback_query(F.data.startswith("olmos_"))
async def olmos_star_callback(callback: CallbackQuery):
    await callback.answer()

    parts = callback.data.split("_")
    olmos_amount = int(parts[1])
    star_amount = int(parts[2])
    user_id = callback.from_user.id

    prices = [
        LabeledPrice(label=f"💎 {olmos_amount} sotib olish", amount=star_amount)
    ]
    t = get_lang_text(callback.from_user.id)
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=t['buy_stone_group'],
        description=t['buy_stone_group_desc'],
        payload=f"olmos_{olmos_amount}_{star_amount}_{user_id}",
        currency="XTR",
        prices=prices
    )
    


    
    
@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    sp = message.successful_payment

    payload = sp.invoice_payload
    total_amount = sp.total_amount
    currency = sp.currency

    try:
        parts = payload.split("_")
        if len(parts) != 4:
            await message.answer("❌ Noto‘g‘ri invoice payload.")
            return

        prefix = parts[0]  # pul yoki olmos
        item_amount = int(parts[1])   # pul/olmos amount
        star_amount = int(parts[2])
        user_id = int(parts[3])
    except:
        await message.answer("❌ Payload parse error.")
        return
    
    if int(user_id)<0:
        group_trials = GroupTrials.objects.filter(group_id=int(user_id)).first()
        if group_trials:
            group_trials.stones += item_amount
            group_trials.save()
        await message.answer(
            f"✅ Olmos xarid qilindi!\n\n"
            f"💎 Olmos: {item_amount}\n"
        )
        return

    # ✅ xavfsizlik
    if message.from_user.id != user_id:
        await message.answer("❌ To‘lov user mos kelmadi.")
        return

    # ✅ real to'lov va kutilgan star amount mos kelishi kerak
    if total_amount != star_amount:
        await message.answer("❌ To‘lov summasi mos kelmadi.")
        return
    
    

    user = User.objects.filter(telegram_id=user_id).first()
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return
    if prefix == "pul":
        
        await message.answer(
            f"✅ Pul xarid qilindi!\n\n"
            f"💶 Pul: {item_amount}\n"
            f"⭐ Stars: {total_amount} {currency}"
        )
        user.coin += item_amount
        user.save()

    elif prefix == "olmos":
        # add_olmos_user(user_id, item_amount)
        await message.answer(
            f"✅ Olmos xarid qilindi!\n\n"
            f"💎 Olmos: {item_amount}\n"
            f"⭐ Stars: {total_amount} {currency}"
        )
        user.stones += item_amount
        user.save()

    else:
        await message.answer("❌ Noma’lum invoice turi.")
        return
    
    
@dp.callback_query(F.data.startswith("groups"))
async def groups_callback(callback: CallbackQuery):
    await callback.answer()
    t = get_lang_text(callback.from_user.id)
    await callback.message.edit_text(
        text=t['groups_section'],
        parse_mode="HTML",
        reply_markup=groups_inline_btn()
    )
    
    
@dp.callback_query(F.data == "premium_group")
async def premium_group_callback(callback: CallbackQuery):
    await callback.answer()
    page = 1
    limit = 5
    offset = (page - 1) * limit
    total = PremiumGroup.objects.count()
    premium_groups = PremiumGroup.objects.all()[offset:offset + limit]

    total_pages = (total + limit - 1) // limit

    quiz_list = "\n\n".join([
        f"{i + 1}. <a href='{group.link}'>{group.name}</a>\n"
        for i, group in enumerate(premium_groups)
    ])

    await callback.message.edit_text(
        text=f"Premium group (sahifa {page}/{total_pages}):\n\n{quiz_list}",
        reply_markup=groupes_keyboard(questions=premium_groups, page=page, total=total, per_page=limit)
    )

@dp.callback_query(F.data.startswith("quiz_page:"))
async def quizzes_page_callback(callback_query):
    await callback_query.answer()
    page = int(callback_query.data.split(":")[1])
    limit = 5
    offset = (page - 1) * limit

    total = PremiumGroup.objects.count()
    total_pages = (total + limit - 1) // limit

    groups = PremiumGroup.objects.all()[offset:offset + limit]

    quiz_list = "\n\n".join([
        f"{i + 1}. <a href='{group.link}'>{group.name}</a>\n"
        for i, group in enumerate(groups)
    ])

    await callback_query.message.edit_text(
        text=f"Premium group (sahifa {page}/{total_pages}):\n\n{quiz_list}",
        reply_markup=groupes_keyboard(questions=groups, page=page, total=total, per_page=limit)
    )

@dp.callback_query(F.data.startswith("quiz_select:"))
async def quiz_select(callback):
    await callback.answer()
    group_id = callback.data.split(":")[1]
    group = PremiumGroup.objects.get(id=group_id)

    await callback.message.edit_text(
        text=f"🌟 Premium guruhni boshqarish\n\n"
             f"Nomi: {group.name}\n"
             f"Link: {group.link}",
        reply_markup=group_manage_btn(group.id)
    )

@dp.callback_query(F.data == "add_group")
async def add_group(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        text="⭐ Premium guruh nomini kiriting:",
        reply_markup=back_admin_btn()
    )
    await state.set_state(AddGroupState.waiting_for_group_name)
    
    

@dp.message(AddGroupState.waiting_for_group_name)
async def process_group_name(message: Message, state: FSMContext) -> None:
    group_name = message.text.strip()
    await state.update_data(group_name=group_name)
    await message.answer(
        text="🔗 Premium guruh linkini kiriting:",
        reply_markup=back_admin_btn()
    )
    await state.set_state(AddGroupState.waiting_for_group_link)

@dp.message(AddGroupState.waiting_for_group_link)
async def process_group_link(message: Message, state: FSMContext) -> None:
    group_link = message.text.strip()
    if not group_link.startswith("https://t.me/") and not group_link.startswith("http://t.me/"):
        await message.answer(
            text="❌ Iltimos, to'g'ri guruh linkini kiriting (https://t.me/...)",
            reply_markup=back_admin_btn()
        )
        return
    
    await state.update_data(group_link=group_link)
    
    await message.answer(
        text="💎 Nechta olmos evaziga",
        reply_markup=back_admin_btn()
    )
    await state.set_state(AddGroupState.waiting_for_olmos_amount)
    
    
@dp.message(AddGroupState.waiting_for_olmos_amount)
async def process_olmos_amount(message: Message, state: FSMContext) -> None:
    olmos_amount_text = message.text.strip()
    if not olmos_amount_text.isdigit():
        await message.answer(
            text="❌ Iltimos, to'g'ri olmos miqdorini kiriting (faqat raqamlar)",
            reply_markup=back_admin_btn()
        )
        return
    data = await state.get_data()
    group_name = data.get("group_name")
    group_link = data.get("group_link")
    olmos_amount = int(olmos_amount_text)
    group_id = data.get("group_id")
    
    if group_id:
        group = PremiumGroup.objects.filter(id=group_id).first()
        if group:
            group.name = group_name
            group.link = group_link
            group.stones_for = olmos_amount
            group.ends_date = default_end_date()
            group.save()
            await message.answer(
                text=f"✅ Premium guruh muvaffaqiyatli yangilandi!\n\n"
                     f"Nomi: {group_name}\n"
                     f"Link: {group_link}",
                reply_markup=admin_inline_btn()
            )
            await state.clear()
            return

    PremiumGroup.objects.create(
        name=group_name,
        link=group_link,
        stones_for=olmos_amount,
        ends_date=default_end_date()
    )

    await message.answer(
        text=f"✅ Premium guruh muvaffaqiyatli qo'shildi!\n\n"
             f"Nomi: {group_name}\n"
             f"Link: {group_link}\n"
             f"Olmos evaziga: {olmos_amount}",
        reply_markup=admin_inline_btn()
    )
    await state.clear()
    

@dp.callback_query(F.data.startswith("manage_"))
async def manage_group(callback: CallbackQuery,state : FSMContext) -> None:
    await callback.answer()
    splited_text = callback.data.split("_")[1]
    group_id = int(splited_text.split(":")[1])
    action = splited_text.split(":")[0]
    
    if action == "edit":
        await state.update_data(group_id=group_id)
        await callback.message.edit_text(
            text="⭐ Yangi premium guruh nomini kiriting:",
            reply_markup=back_admin_btn()
        )
        await state.set_state(AddGroupState.waiting_for_group_name)
        return
    elif action == "delete":
        group = PremiumGroup.objects.filter(id=group_id).first()
        if group:
            group.delete()
            await callback.message.edit_text(
                text="✅ Premium guruh muvaffaqiyatli o'chirildi.",
                reply_markup=admin_inline_btn()
            )
        else:
            await callback.message.edit_text(
                text="❌ Premium guruh topilmadi.",
                reply_markup=admin_inline_btn()
            )
    

@dp.callback_query(F.data.startswith("remove_"))
async def remove_callback(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    action = callback.data.split("_")[1]
    if action == "pul":
        await callback.message.edit_text(
            text="💶 Foydalanuvchidan pul yechib olish uchun telegram id va pulni yonma-yon kiriting:",
            reply_markup=back_admin_btn()
        )
        await state.set_state(SendMoneyState.waiting_money_to_remove)
    elif action == "olmos":
        await callback.message.edit_text(
            text="💎 Foydalanuvchidan olmos yechib olish uchun telegram id va olmosni yonma-yon kiriting:",
            reply_markup=back_admin_btn()
        )
        await state.set_state(SendMoneyState.waiting_olmos_to_remove)
        
@dp.message(SendMoneyState.waiting_money_to_remove)
async def process_send_money(message: Message, state: FSMContext) -> None:
    try:
        telegram_id, amount_str = message.text.strip().split()
        amount = int(amount_str)
    except ValueError:
        await message.answer(
            text="❌ Iltimos, to'g'ri formatda kiriting: telegram_id pul_miqdori",
            reply_markup=back_admin_btn()
        )
        return
    
        

    user = User.objects.filter(telegram_id=int(telegram_id)).first()
    if not user:
        await message.answer(
            text="❌ Foydalanuvchi topilmadi.",
            reply_markup=back_admin_btn()
        )
        return

    sender = User.objects.filter(telegram_id=message.from_user.id).first()
    if not sender:
        sender = User.objects.create(
            telegram_id=message.from_user.id,
            first_name=message.from_user.first_name or "NoName",
            username=message.from_user.username or "",
            role="admin"
        )
    user.coin -= amount
    user.save()
    MoneySendHistory.objects.create(
        sender_id = sender.id,
        receiver_id = user.id,
        amount = f"- {amount} 💶"
    )
        

    await message.answer(
        text=f"✅ <a href='tg://user?id={user.telegram_id}'>{user.first_name}</a> foydalanuvchisidan {amount}💶 muvaffaqiyatli yechib olindi.",
        reply_markup=admin_inline_btn(),
        parse_mode="HTML"
    )
    await send_safe_message(
        chat_id=user.telegram_id,
        text=f"Sizdan admin  💶 {amount} pullar yechib oldi."
    )   
    await state.clear()
    

@dp.message(SendMoneyState.waiting_olmos_to_remove)
async def process_send_olmos(message: Message, state: FSMContext) -> None:
    try:
        telegram_id, amount_str = message.text.strip().split()
        amount = int(amount_str)
    except ValueError:
        await message.answer(
            text="❌ Iltimos, to'g'ri formatda kiriting: telegram_id pul_miqdori",
            reply_markup=back_admin_btn()
        )
        return
    
    
    user = User.objects.filter(telegram_id=int(telegram_id)).first()
    if not user:
        await message.answer(
            text="❌ Foydalanuvchi topilmadi.",
            reply_markup=back_admin_btn()
        )
        return

    user.stones -= amount
    user.save()
    sender = User.objects.filter(telegram_id=message.from_user.id).first()
    if not sender:
        sender = User.objects.create(
            telegram_id=message.from_user.id,
            first_name=message.from_user.first_name or "NoName",
            username=message.from_user.username or "",
            role="admin"
        )
    MoneySendHistory.objects.create(
        sender_id = sender.id,
        receiver_id = user.id,
        amount = f"- {amount} 💎"
    )

    await message.answer(
        text=f"✅ <a href='tg://user?id={user.telegram_id}'>{user.first_name}</a> foydalanuvchisidan {amount}💎 muvaffaqiyatli yechib olindi.",
        reply_markup=admin_inline_btn(),
        parse_mode="HTML"
    )
    await send_safe_message(
        chat_id=user.telegram_id,
        text= f"Sizdan admin tomonidan 💎 {amount} olmoslar yechib olindi."
    )
    await state.clear()
    
    
        
@dp.callback_query(F.data.startswith("send_"))
async def send_callback(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    action = callback.data.split("_")[1]
    if action == "pul":
        await callback.message.edit_text(
            text="💶 Foydalanuvchiga pul yuborish uchun telegram id va pulni yonma-yon kiriting:",
            reply_markup=back_admin_btn()
        )
        await state.set_state(SendMoneyState.waiting_for_money)
        return
        
        
    elif action == "olmos":
        await callback.message.edit_text(
            text="💎 Foydalanuvchiga olmos yuborish uchun telegram id va olmosni yonma-yon kiriting:",
            reply_markup=back_admin_btn()
        )
        await state.set_state(SendMoneyState.waiting_for_olmos)
        return
    elif action == "channel":
        await callback.message.edit_text(
            text="💎 Kanalga jo'natmoqchi bo'lgan kanal usernamesini va olmos miqdorini yonma-yon kiriting:\n(@my_chanel 10)",
            reply_markup=back_admin_btn()
        )
        await state.set_state(SendMoneyState.waiting_for_channel_olmos)
        return
    elif action == "confirm":
        username, amount_str = callback.data.split("_")[2], callback.data.split("_")[3]
        await callback.message.edit_text(
            text="💎 Kanalga olmos jo'natildi",
            reply_markup=admin_inline_btn()
        )
        sent = await bot.send_message(
            chat_id=username,
            text=f"Kanalimiz obunachilari uchun 💎 {amount_str} ta olmos hadya qilinmoqda:",
            reply_markup=claim_chanel_olmos_inline_btn(username=remove_prefix(username))        
        )
        stones_taken[username] = {
            "limit": int(amount_str),
            "taken": [],
            "msg_id": sent.message_id,
            "creator": callback.message.from_user.id
    }   
        return
    elif action == "no":
        await bot.send_message(
            chat_id=username,
            text=f"Kanalga jo'natilishi kerak bo'lgan 💎 olmoslar bekor qilindi.",
            reply_markup=admin_inline_btn()
        )
        return
@dp.message(SendMoneyState.waiting_for_channel_olmos)
async def process_send_channel_olmos(message: Message, state: FSMContext) -> None:
    try:
        channel_username, amount_str = message.text.strip().split()
        amount = int(amount_str)
    except ValueError:
        await message.answer(
            text="❌ Iltimos, to'g'ri formatda kiriting: @channel_username olmos_miqdori",
            reply_markup=back_admin_btn()
        )
        return
    
    if not channel_username.startswith("@"):
        await message.answer(
            text="❌ Iltimos, kanal username'ini @ bilan boshlang.",
            reply_markup=back_admin_btn()
        )
        return
    if stones_taken.get(channel_username):
            await message.answer(
                text="❌ Bu kanalda tugamagan olmoslar allaqachon mavjud.",
                reply_markup=admin_inline_btn()
            )
            await state.clear()
            return
    await message.answer(
        text=f"✅ {channel_username} kanaliga {amount} olmos yuborililsinmi?",
        reply_markup=confirm_channel_olmos_inline_btn(channel_username=channel_username, amount=amount)
    )
    await state.clear()


@dp.message(SendMoneyState.waiting_for_money)
async def process_send_money(message: Message, state: FSMContext) -> None:
    try:
        telegram_id, amount_str = message.text.strip().split()
        amount = int(amount_str)
    except ValueError:
        await message.answer(
            text="❌ Iltimos, to'g'ri formatda kiriting: telegram_id pul_miqdori",
            reply_markup=back_admin_btn()
        )
        return
    
        

    user = User.objects.filter(telegram_id=int(telegram_id)).first()
    if not user:
        await message.answer(
            text="❌ Foydalanuvchi topilmadi.",
            reply_markup=back_admin_btn()
        )
        return

    sender = User.objects.filter(telegram_id=message.from_user.id).first()
    if not sender:
        sender = User.objects.create(
            telegram_id=message.from_user.id,
            first_name=message.from_user.first_name or "NoName",
            username=message.from_user.username or "",
            role="admin"
        )
    user.coin += amount
    user.save()
    MoneySendHistory.objects.create(
        sender_id = sender.id,
        receiver_id = user.id,
        amount = f"{amount} 💶"
    )
        

    await message.answer(
        text=f"✅ <a href='tg://user?id={user.telegram_id}'>{user.first_name}</a> foydalanuvchisiga {amount}💶 muvaffaqiyatli yuborildi.",
        reply_markup=admin_inline_btn(),
        parse_mode="HTML"
    )
    await send_safe_message(
        chat_id=user.telegram_id,
        text=f"Sizga admin tomonidan 💶 {amount} pullar yuborildi."
    )   
    await state.clear()
    
@dp.message(SendMoneyState.waiting_for_olmos)
async def process_send_olmos(message: Message, state: FSMContext) -> None:
    try:
        telegram_id, amount_str = message.text.strip().split()
        amount = int(amount_str)
    except ValueError:
        await message.answer(
            text="❌ Iltimos, to'g'ri formatda kiriting: telegram_id pul_miqdori",
            reply_markup=back_admin_btn()
        )
        return
    
    
    user = User.objects.filter(telegram_id=int(telegram_id)).first()
    if not user:
        await message.answer(
            text="❌ Foydalanuvchi topilmadi.",
            reply_markup=back_admin_btn()
        )
        return

    user.stones += amount
    user.save()
    sender = User.objects.filter(telegram_id=message.from_user.id).first()
    MoneySendHistory.objects.create(
        sender_id = sender.id,
        receiver_id = user.id,
        amount = f"{amount} 💎"
    )

    await message.answer(
        text=f"✅ <a href='tg://user?id={user.telegram_id}'>{user.first_name}</a> foydalanuvchisiga {amount}💎 muvaffaqiyatli yuborildi.",
        reply_markup=admin_inline_btn(),
        parse_mode="HTML"
    )
    await send_safe_message(
        chat_id=user.telegram_id,
        text= f"Sizga admin tomonidan 💎 {amount} olmoslar yuborildi."
    )
    await state.clear()
    
    
@dp.callback_query(F.data == "statistics")
async def statistics_callback(callback: CallbackQuery):
    await callback.answer()

    total_users = User.objects.count()
    total_admins = User.objects.filter(role='admin').count()
    total_premium_groups = PremiumGroup.objects.count()
    total_games = Game.objects.count()
    bot_working_in_groups = GroupTrials.objects.count()

    today = timezone.localdate()
    week_start, week_end = get_week_range(today)
    month_start, month_end = get_month_range(today)

    active_player_row = (
        MostActiveUser.objects
        .values("user")
        .annotate(total_played=Sum("games_played"))
        .order_by("-total_played")
        .first()
    )

    most_wins_all_time_row = (
        MostActiveUser.objects
        .values("user")
        .annotate(total_win=Sum("games_win"))
        .order_by("-total_win")
        .first()
    )

    daily_top_row = (
        MostActiveUser.objects
        .filter(created_datetime__date=today)
        .values("user")
        .annotate(total_win=Sum("games_win"))
        .order_by("-total_win")
        .first()
    )

    weekly_top_row = (
        MostActiveUser.objects
        .filter(created_datetime__date__gte=week_start, created_datetime__date__lt=week_end)
        .values("user")
        .annotate(total_win=Sum("games_win"))
        .order_by("-total_win")
        .first()
    )

    monthly_top_row = (
        MostActiveUser.objects
        .filter(created_datetime__date__gte=month_start, created_datetime__date__lt=month_end)
        .values("user")
        .annotate(total_win=Sum("games_win"))
        .order_by("-total_win")
        .first()
    )

    user_ids = set()
    for row in [active_player_row, most_wins_all_time_row, daily_top_row, weekly_top_row, monthly_top_row]:
        if row:
            user_ids.add(row["user"])

    users_map = {u.id: u for u in User.objects.filter(id__in=user_ids)}

    active = ""
    if active_player_row and active_player_row.get("total_played"):
        u = users_map.get(active_player_row["user"])
        if u:
            active = (
                f"\n🏅 Eng faol o'yinchi: "
                f"<a href='tg://user?id={u.telegram_id}'>{u.first_name}</a>"
                f" ({active_player_row['total_played']} o'yin)"
            )

    most_wins_text = ""
    if most_wins_all_time_row and most_wins_all_time_row.get("total_win"):
        u = users_map.get(most_wins_all_time_row["user"])
        if u:
            most_wins_text = (
                f"🏆 Eng ko'p g'alaba (umumiy): "
                f"<a href='tg://user?id={u.telegram_id}'>{u.first_name}</a>"
                f" ({most_wins_all_time_row['total_win']} g'alaba)\n"
            )

    daily_text = ""
    if daily_top_row and daily_top_row.get("total_win"):
        u = users_map.get(daily_top_row["user"])
        if u:
            daily_text = (
                f"📅 Kunlik top: "
                f"<a href='tg://user?id={u.telegram_id}'>{u.first_name}</a>"
                f" ({daily_top_row['total_win']} g'alaba)\n"
            )

    weekly_text = ""
    if weekly_top_row and weekly_top_row.get("total_win"):
        u = users_map.get(weekly_top_row["user"])
        if u:
            weekly_text = (
                f"🗓 Haftalik top: "
                f"<a href='tg://user?id={u.telegram_id}'>{u.first_name}</a>"
                f" ({weekly_top_row['total_win']} g'alaba)\n"
            )

    monthly_text = ""
    if monthly_top_row and monthly_top_row.get("total_win"):
        u = users_map.get(monthly_top_row["user"])
        if u:
            monthly_text = (
                f"🗓 Oylik top: "
                f"<a href='tg://user?id={u.telegram_id}'>{u.first_name}</a>"
                f" ({monthly_top_row['total_win']} g'alaba)\n"
            )

    await callback.message.edit_text(
        text=(
            f"📊 Bot Statistikasi\n\n"
            f"👥 Foydalanuvchilar soni: {total_users}\n"
            f"🛡️ Adminlar soni: {total_admins}\n"
            f"🌟 Premium guruhlar soni: {total_premium_groups}\n"
            f"🤖 Bot ishlayotgan guruhlar soni: {bot_working_in_groups}\n"
            f"🎲 O'yinlar soni: {total_games}\n\n"
            f"{most_wins_text}"
            f"{daily_text}"
            f"{weekly_text}"
            f"{monthly_text}"
            f"{active}"
        ),
        parse_mode="HTML",
        reply_markup=admin_inline_btn(),
    )    
@dp.callback_query(F.data.startswith("change_"))
async def change_money_cost_handler(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    action = callback.data.split("_")[1]
    if action == "money":
        await callback.message.edit_text(
            text="💶 Yangi pul sotib olish narxini kiriting:",
            reply_markup=change_money_cost()
        )
        
    elif action == "stone":
        await callback.message.edit_text(
            text="💎 Yangi olmos sotib olish narxini kiriting:",
            reply_markup=change_stones_cost()
        )
        

def format_money_prices(json_text: str) -> str:
    data = json.loads(json_text)
    items = sorted(((int(k), int(v)) for k, v in data.items()), key=lambda x: x[0])

    text = "💶 Pul → ⭐ Stars narxlari\n\n"
    for money, stars in items:
        text += f"• {money:,} so'm  →  ⭐ {stars}\n"
    return text


def format_stone_prices(json_text: str) -> str:
    data = json.loads(json_text)
    items = sorted(((int(k), int(v)) for k, v in data.items()), key=lambda x: x[0])

    text = "💎 Olmos → ⭐ Stars narxlari\n\n"
    for stone, stars in items:
        text += f"• {stone:,} 💎  →  ⭐ {stars}\n"
    return text


@dp.callback_query(F.data.startswith("aziz_"))
async def ozgar_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    action = callback.data.split("_")[1]
    cost = PriceStones.objects.first()
    if not cost:
        cost = PriceStones.objects.create()

    if action == "money":
        await callback.message.edit_text(
            text=(
                "💶 Yangi pul sotib olish narxini kiriting:\n\n"
                f"📌 Oldingi narxlar:\n\n{cost.money_in_money}"
            ),
            reply_markup=back_admin_btn()
        )
        await state.set_state(ChangeMoneyCostState.waiting_for_money_cost)

    elif action == "star":
        try:
            formatted = format_money_prices(cost.money_in_star)
        except Exception:
            formatted = cost.money_in_star or "—"

        await callback.message.edit_text(
            text=(
                "💶 Yangi pul sotib olish narxini ⭐ starsda kiriting:\n\n"
                f"📌 Oldingi narxlar:\n{formatted}\n\n"
                "✍️ Namuna (JSON format):\n"
                '{"1000":7,"10000":77,"50000":340,"100000":680}'
            ),
            reply_markup=back_admin_btn(),
            parse_mode="Markdown"
        )
        await state.set_state(ChangeMoneyCostState.waiting_for_star_cost)


@dp.callback_query(F.data.startswith("ozgar_"))
async def aziz_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    action = callback.data.split("_")[1]
    cost = PriceStones.objects.first()
    if not cost:
        cost = PriceStones.objects.create()

    if action == "money":
        await callback.message.edit_text(
            text=(
                "💎 Yangi olmos sotib olish narxini kiriting\n\n"
                f"📌 Eski narxlar:\n\n{cost.stone_in_money}"
            ),
            reply_markup=back_admin_btn()
        )
        await state.set_state(ChangeStoneCostState.waiting_for_money_cost)

    elif action == "star":
        try:
            formatted = format_stone_prices(cost.stone_in_star)
        except Exception:
            formatted = cost.stone_in_star or "—"

        await callback.message.edit_text(
            text=(
                "💎 Yangi olmos sotib olish narxini ⭐ starsda kiriting\n\n"
                f"📌 Oldingi narxlar:\n{formatted}\n\n"
                "✍️ Namuna (JSON format):\n"
                '{"1":7,"10":68,"30":185,"50":237,"70":382,"100":513}'
            ),
            reply_markup=back_admin_btn(),
            parse_mode="Markdown"
        )
        await state.set_state(ChangeStoneCostState.waiting_for_star_cost)


@dp.message(ChangeMoneyCostState.waiting_for_money_cost)
async def process_change_money_cost(message: Message, state: FSMContext) -> None:
    cost = PriceStones.objects.first()
    if not cost:
        cost = PriceStones.objects.create()

    cost.money_in_money = message.text.strip()
    cost.save()

    await message.answer(
        text=(
            "✅ Pul sotib olish narxi muvaffaqiyatli o'zgartirildi.\n\n"
            f"Yangi narxlar:\n\n{cost.money_in_money}"
        ),
        reply_markup=admin_inline_btn()
    )
    await state.clear()


@dp.message(ChangeMoneyCostState.waiting_for_star_cost)
async def process_change_money_star_cost(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()

    try:
        formatted = format_money_prices(raw)
    except Exception:
        await message.answer(
            "❌ Format xato!\n\nJSON ko‘rinishda yuboring.\nMasalan:\n"
            '{"1000":7,"10000":77,"50000":340,"100000":680}'
        )
        return

    cost = PriceStones.objects.first()
    if not cost:
        cost = PriceStones.objects.create()

    cost.money_in_star = raw
    cost.save()

    await message.answer(
        text=f"✅ Pul sotib olish narxi muvaffaqiyatli o'zgartirildi.\n\n{formatted}",
        reply_markup=admin_inline_btn(),
        parse_mode="Markdown"
    )
    await state.clear()


@dp.message(ChangeStoneCostState.waiting_for_money_cost)
async def process_change_stone_money_cost(message: Message, state: FSMContext) -> None:
    cost = PriceStones.objects.first()
    if not cost:
        cost = PriceStones.objects.create()

    cost.stone_in_money = message.text.strip()
    cost.save()

    await message.answer(
        text=(
            "✅ Olmos sotib olish narxi muvaffaqiyatli o'zgartirildi.\n\n"
            f"Yangi narxlar:\n\n{cost.stone_in_money}"
        ),
        reply_markup=admin_inline_btn()
    )
    await state.clear()


@dp.message(ChangeStoneCostState.waiting_for_star_cost)
async def process_change_stone_star_cost(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()

    try:
        data = json.loads(raw)

        if not isinstance(data, dict):
            await message.answer(
                "❌ Noto'g'ri format!\n\nJSON object yuborishingiz kerak.\nNamuna:\n"
                '{"1":7,"10":68,"30":185,"50":237,"70":382,"100":513}'
            )
            return

        for k, v in data.items():
            int(k)
            int(v)

        formatted = format_stone_prices(raw)

    except Exception:
        await message.answer(
            "❌ JSON format xato!\n\nNamuna:\n"
            '{"1":7,"10":68,"30":185,"50":237,"70":382,"100":513}'
        )
        return

    cost = PriceStones.objects.first()
    if not cost:
        cost = PriceStones.objects.create()

    cost.stone_in_star = raw
    cost.save()

    await message.answer(
        text=(
            "✅ Olmos sotib olish narxi muvaffaqiyatli (⭐ starslarda) o'zgartirildi.\n\n"
            f"{formatted}"
        ),
        reply_markup=admin_inline_btn(),
        parse_mode="Markdown"
    )
    await state.clear()


@dp.callback_query(F.data == "cases")
async def case_callback(callback: CallbackQuery):
    await callback.answer()
    t = get_lang_text(callback.from_user.id)
    await callback.message.edit_text(
        text=t['case_menu'],
        parse_mode="HTML",
        reply_markup=case_inline_btn(callback.from_user.id)
    )
    
    
@dp.callback_query(F.data.startswith("case_"))
async def case_buy_callback(callback: CallbackQuery):
    case_type = callback.data.split("_")[1]
    user = User.objects.filter(telegram_id=callback.from_user.id).first()
    if not user:
        user = User.objects.create(
            telegram_id=callback.from_user.id,
            first_name=callback.from_user.first_name or "NoName",
            username=callback.from_user.username or "",
            role="user"
        )
    t = get_lang_text(callback.from_user.id)
    case_opened = CasesOpened.objects.filter(user_id=user.id).first()
    if case_type == "money":
        await callback.message.edit_text(
            text=t['money_case_text'],
            reply_markup=money_case()
        )
    elif case_type == "stone":
        if not user.is_vip:
            if case_opened:
                last_opened = case_opened.modified_datetime

                # timezone muammosiz bo'lishi uchun UTC ishlatamiz
                now = datetime.datetime.utcnow()

                # ✅ month check
                if last_opened.year == now.year and last_opened.month == now.month:
                    await callback.answer(
                        t['already_opened']
                    )
                    return
        await callback.message.edit_text(
            text=t['stone_case_text'],
            reply_markup=stone_case()
        )
    elif case_type == "vip":
        if user.is_vip:
            await callback.answer(t['already_vip'])
            return
        if not user:
            await callback.answer(t['user_not_found'])
            return
        if user.stones < 20:
            await callback.answer(t['not_enough_stones'])
            return
        user.stones -= 20
        user.is_vip = True
        user.save()
        await callback.message.edit_text(t['vip_success'],reply_markup=back_btn(callback.from_user.id))
        
        
@dp.callback_query(F.data.startswith("open_"))
async def open_case_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    case_type = parts[1]
    reward = int(parts[2])
    user_id = callback.from_user.id
    user = User.objects.filter(telegram_id=user_id).first()
    if not user:
        user = User.objects.create(
            telegram_id=user_id,
            first_name=callback.from_user.first_name or "NoName",
            username=callback.from_user.username or "",
            role="user"
        )
    t = get_lang_text(callback.from_user.id)
    if case_type == "money":
        if user.stones < 1:
            await callback.answer(t['not_enough_stones'])
            return
        user.stones -= 1
        user.coin += reward
        user.save()
        await callback.message.edit_text(t['money_reward'].format(reward=reward),reply_markup=back_btn(callback.from_user.id))
    elif case_type == "stone":
        if user.coin < 10000:
            await callback.answer(t['not_enough_money'])
            return
        user.coin -= 10000
        user.stones += reward
        user.save()
        await callback.message.edit_text(t['stone_reward'].format(reward=reward),reply_markup=back_btn(callback.from_user.id))
        case_opened = CasesOpened.objects.filter(user_id=user.id).first()
        if not case_opened:
            case_opened = CasesOpened.objects.create(user_id=user.id)
            return
        case_opened.modified_datetime = datetime.datetime.utcnow()
        case_opened.save()
        

async def begin_instance_callback(message: Message,chat_id):
    await message.answer(
        text="🛠️ Yangi o'yinni sozlash uchun quyidagi tugmalardan foydalaning.\n\n🔢 O'yinchilar to'lganda boshlash - qachonki ro'yxatdan o'tganlar siz kiritgan songa yetsagina o'yin boshlanadi\nMasalan 20,25,30 guruh activiga qarab\n\n⏱ Belgilangan vaqtdan so'ng boshlash - O'yin belgilangan vaqtdan so'ng avtomatik boshlanadi\nVaqtni sekundlarda yozing\n\n🔁 O'yin tugagach auto boshlash - Eski o'yin tugagandan so'ng avtomatik boshlanadi",
        reply_markup=begin_instance_inline_btn(chat_id=chat_id)
    )
    
@dp.callback_query(F.data.startswith("begin_"))
async def begin_new_instance_callback(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split("_")
    action = parts[1]
    chat_id = int(parts[2])
    if action == "instance":
        await state.update_data(action = "instance")
        await state.update_data(chat_id=chat_id)
        await callback.message.edit_text(
            text="🚀 Yangi o'yinni ishtirokchilar to'lganda boshlash uchun sonini kiriting:",
            reply_markup=back_btn(callback.from_user.id)
        )
    elif action == "time":
        await state.update_data(action = "time")
        await state.update_data(chat_id=chat_id)
        await callback.message.edit_text(
            text="🚀 Yangi o'yinni boshlash vaqtini kiriting (soniyalarda):",
            reply_markup=back_btn(callback.from_user.id)
        )
    elif action == "auto":
        game_settings = GameSettings.objects.filter(group_id=chat_id).first()
        if game_settings and not game_settings.begin_after_end:
            await callback.message.edit_text(
                text="✅ O'yin avtomatik ravishda oldingi o'yin tugagandan so'ng boshlanishi yoqildi.",   
                reply_markup=start_inline_btn(callback.from_user.id)
            )
            game_settings.begin_after_end = True
        else:
            game_settings.begin_after_end = False
            await callback.message.edit_text(
                text="❌ O'yin avtomatik ravishda oldingi o'yin tugagandan so'ng boshlanishi o'chirildi.",   
                reply_markup=start_inline_btn(callback.from_user.id)
            )
            
        game_settings.save()
        return
    await state.set_state(BeginInstanceState.waiting_for_instant_time)
        
        
@dp.message(BeginInstanceState.waiting_for_instant_time)
async def process_begin_instant_count(message: Message, state: FSMContext) -> None:
    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer(
            text="❌ Iltimos, to'g'ri son kiriting:",
            reply_markup=back_btn(message.from_user.id)
        )
        return
    
    data = await state.get_data()
    action = data.get("action")
    chat_id = data.get("chat_id")
    game_settings = GameSettings.objects.filter(group_id=chat_id).first()
    if not game_settings:
        return
    if action == "instance":
        if count < 4 or count > 30:
            await message.answer(
                text="❌ Iltimos, 4 dan 30 gacha bo'lgan son kiriting:",
                reply_markup=back_btn(message.from_user.id)
            )
            return
        game_settings.begin_instance = True
        game_settings.number_of_players = count
        await message.answer(f"✅ Yangi o'yin ishtirokchilar soni {count} ga o'rnatildi.",reply_markup=start_inline_btn(message.from_user.id))
    elif action == "time":
        game_settings.begin_instance = False
        game_settings.begin_instance_time = count
        await message.answer(f"✅ Yangi o'yin boshlanish vaqti {count} soniyaga o'rnatildi.",reply_markup=start_inline_btn(message.from_user.id))
    game_settings.save()
    await state.clear()
    

@dp.callback_query(F.data == "trial")
async def trial_callback(callback: CallbackQuery):
    await callback.answer()

    page = 1
    limit = 5
    offset = (page - 1) * limit

    groups = GroupTrials.objects.all()[offset:offset + limit]
    total = GroupTrials.objects.count()
    total_pages = (total + limit - 1) // limit

    group_list = "\n".join([
    (
        f"{offset + i + 1}. <a href='{g.group_username}'>{g.group_name}</a>"
        if g.group_username.startswith("http")
        else f"{offset + i + 1}. <a href='https://t.me/{g.group_username.lstrip('@')}'>{g.group_name}</a>"
    )
    if g.group_username else f"{offset + i + 1}. {g.group_name}"
    for i, g in enumerate(groups)
])



    await callback.message.edit_text(
        text=f"Obunadagi guruhlar (sahifa {page}/{total_pages}):\n\n{group_list}",
        reply_markup=trial_groupes_keyboard(groups, page, total, limit),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("olga_page:"))
async def quizzes_page_callback(callback_query: CallbackQuery):
    await callback_query.answer()

    page = int(callback_query.data.split(":")[1])
    limit = 5
    offset = (page - 1) * limit

    groups = GroupTrials.objects.all()[offset:offset + limit]
    total = GroupTrials.objects.count()
    total_pages = (total + limit - 1) // limit

    group_list = "\n".join([
    (
        f"{offset + i + 1}. <a href='{g.group_username}'>{g.group_name}</a>"
        if g.group_username.startswith("http")
        else f"{offset + i + 1}. <a href='https://t.me/{g.group_username.lstrip('@')}'>{g.group_name}</a>"
    )
     if g.group_username else f"{offset + i + 1}. {g.group_name}"
    for i, g in enumerate(groups)
])


    await callback_query.message.edit_text(
        text=f"Obunadagi guruhlar (sahifa {page}/{total_pages}):\n\n{group_list}",
        reply_markup=trial_groupes_keyboard(groups, page, total, limit),
        parse_mode="HTML"
    )



@dp.callback_query(F.data.startswith("olga_select:"))
async def quiz_select(callback):
    await callback.answer()
    group_id = callback.data.split(":")[1]
    group = GroupTrials.objects.get(id=group_id)

    if group.group_username:
        if "http" in group.group_username:
            link_display = group.group_username
        else:
            link_display = f"@{group.group_username}"
    else:
        link_display = "Link mavjud emas"


    await callback.message.edit_text(
    text=(
        f"🌟 Obunadagi guruhni boshqarish\n\n"
        f"Nomi: {group.group_name}\n"
        f"Link: {link_display}\n"
        f"Obuna tugash sanasi: {group.end_date.strftime('%Y-%m-%d')}\n"
    ),
    reply_markup=trial_group_manage_btn(group.id)
)

@dp.callback_query(F.data.startswith("add_"))
async def group_money_callback(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    currency = callback.data.split("_")[1]
    group_id = int(callback.data.split("_")[2])
    if currency == "pul":
        await state.update_data(action = "pul", group_id=group_id)
        await callback.message.edit_text(
        text="Guruhga jo'natmoqchi bo'lgan pulingiz miqdorini kiriting:",
        reply_markup=back_btn(callback.from_user.id,"groups")
        )
    elif currency == "stone":
        await state.update_data(action = "stone", group_id=group_id)
        await callback.message.edit_text(
        text="Guruhga jo'natmoqchi bo'lgan olmosingiz miqdorini kiriting:",
        reply_markup=back_btn(callback.from_user.id,"groups")
        )
    
    await state.set_state(ExtendGroupState.waiting_for_amount)
    
@dp.message(ExtendGroupState.waiting_for_amount)
async def process_group_money(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    action = data.get("action")
    group_id = int(data.get("group_id"))
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer(
            text="❌ Iltimos, to'g'ri son kiriting:",
            reply_markup=back_btn(message.from_user.id,"groups")
        )
        return
    group = GroupTrials.objects.filter(id=group_id).first()
    if not group:
        await message.answer(
            text="❌ Guruh topilmadi.",
            reply_markup=admin_inline_btn()
        )
        await state.clear()
        return
    if action == "pul":
        group.coins += amount
        group.save()
        await message.answer(
            text=f"✅ Guruhga hisobiga 💶 {amount} qo'shildi.",
            reply_markup=admin_inline_btn()
        )
    elif action == "stone":
        group.stones += amount
        group.save()
        await message.answer(
            text=f"✅ Guruhga hisobiga 💎 {amount} qo'shildi.",
            reply_markup=admin_inline_btn()
        )
    await state.clear()
            
@dp.callback_query(F.data.startswith("extend:"))
async def extend_callback(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    group_id = callback.data.split(":")[1]
    await callback.message.edit_text(
        text="⏳ Obuna muddatini uzaytirish uchun obuna tugash sanasini (YYYY-MM-DD) kiriting:",
        reply_markup=back_btn(callback.from_user.id,callback.from_user.id,callback.from_user.id,"groups")
    )
    await state.update_data(group_id=group_id)
    await state.set_state(ExtendGroupState.waiting_for_extend_info)
    

@dp.message(ExtendGroupState.waiting_for_extend_info)
async def process_extend_info(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    group_id = data.get("group_id")
    text = message.text.strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', text):
        await message.answer(
            text="❌ Iltimos, sanani to'g'ri formatda kiriting (YYYY-MM-DD):",
            reply_markup=back_btn(message.from_user.id,"groups")
        )
        return
    extend_date = datetime.datetime.strptime(text, '%Y-%m-%d').date()
    group = GroupTrials.objects.filter(id=group_id).first()
    if not group:
        await message.answer(
            text="❌ Guruh topilmadi.",
            reply_markup=back_btn(message.from_user.id,"groups")
        )
        await state.clear()
        return
    group.trial_end_date = extend_date
    group.save()
    await message.answer(
        text=f"✅ Obuna muddati muvaffaqiyatli uzaytirildi. Yangi tugash sanasi: {extend_date}",
        reply_markup=admin_inline_btn()
    )
    
@dp.callback_query(F.data == "transfer_history")
async def transfer_history_callback(callback: CallbackQuery):
    await callback.answer()
    page = 1
    limit = 10
    offset = (page - 1) * limit
    transfers = MoneySendHistory.objects.all().order_by('-created_datetime')[offset:offset + limit]
    total = MoneySendHistory.objects.count()
    total_pages = (total + limit - 1) // limit

    if transfers:
        history_text = f"💼 Pul o'tkazmalari (sahifa {page}/{total_pages}):\n\n"
        for transfer in transfers:
            history_text += (
                f"👮 Jonatuvchi Admin: <a href='tg://user?id={transfer.sender.telegram_id}'>{transfer.sender.first_name}</a>\n"
                f"👤 Foydalanuvchi: <a href='tg://user?id={transfer.receiver.telegram_id}'>{transfer.receiver.first_name}</a>\n"
                f"💶 Miqdor: {transfer.amount} \n"
                f"🕒 Sana: {transfer.created_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

        await callback.message.edit_text(
            text=history_text,
            reply_markup=history_groupes_keyboard(page=page, total=total, per_page=limit)
        )
    else:
        await callback.message.edit_text("❌ Hech qanday o'tkazmalar topilmadi.", reply_markup=admin_inline_btn())
        return
    
    
@dp.callback_query(F.data.startswith("history_page:"))
async def quizzes_page_callback(callback_query: CallbackQuery):
    await callback_query.answer()
    page = int(callback_query.data.split(":")[1])
    limit = 10
    offset = (page - 1) * limit
    transfers = MoneySendHistory.objects.all().order_by('-created_datetime')[offset:offset + limit]
    total = MoneySendHistory.objects.count()
    total_pages = (total + limit - 1) // limit

    if transfers:
        history_text = f"💼 Pul o'tkazmalari (sahifa {page}/{total_pages}):\n\n"
        for transfer in transfers:
            history_text += (
                f"👮 Jonatuvchi Admin: <a href='tg://user?id={transfer.sender.telegram_id}'>{transfer.sender.first_name}</a>\n"
                f"👤 Foydalanuvchi: <a href='tg://user?id={transfer.receiver.telegram_id}'>{transfer.receiver.first_name}</a>\n"
                f"💶 Miqdor: {transfer.amount} \n"
                f"🕒 Sana: {transfer.created_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

        await callback_query.message.edit_text(
            text=history_text,
            reply_markup=history_groupes_keyboard(page=page, total=total, per_page=limit)
        )
    else:
        await callback_query.message.edit_text("❌ Hech qanday o'tkazmalar topilmadi.", reply_markup=admin_inline_btn())
        return
    
@dp.callback_query(F.data == "take_stone")
async def take_stone(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    t = get_lang_text(chat_id)
    tu = get_lang_text(user_id)

    data = stones_taken.get(chat_id)
    if not data:
        await callback.message.edit_reply_markup(None)
        await callback.answer(tu['no_sharing'], show_alert=True)
        return

    limit = data["limit"]
    taken = data["taken"]
    sender = data["creator"]

    if user_id in taken:
        await callback.answer(tu['stone_already_taken'], show_alert=True)
        return

    if len(taken) >= limit:
        await callback.answer(tu['stone_ended'], show_alert=True)
        return

    taken.append(user_id)
    user_taker = User.objects.filter(telegram_id=user_id).first()
    sender = User.objects.filter(telegram_id=int(sender)).first()
    if not user_taker:
        user_taker = User.objects.create(
            telegram_id=user_id, 
            first_name=callback.from_user.first_name,
            username=callback.from_user.username
        )
    users_qs = User.objects.filter(telegram_id__in=taken)
    
    
    taken_text = ""
    for i, user in enumerate(users_qs, start=1):
        taken_text += f"\n{i}. 💎 <a href='tg://user?id={user.telegram_id}'>{user.first_name}</a>"

    text = (
         f"💎 <a href='tg://user?id={sender.telegram_id}'>{sender.first_name}</a>  {t['group_sender'].format(count=limit)}\n"
        f"{taken_text}"
    )

    if len(taken) >= limit:
        await callback.message.edit_text(text, reply_markup=None, parse_mode="HTML")
        stones_taken.pop(chat_id, None)
    else:
        await callback.message.edit_text(text, reply_markup=take_stone_btn(chat_id), parse_mode="HTML")
    user_taker.stones += 1
    user_taker.save()
    await callback.answer(tu['stone_taken'])


@dp.callback_query(F.data == "take_gsend_stone")
async def take_gsend_stone(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    t = get_lang_text(chat_id)
    tu = get_lang_text(user_id)
    data = gsend_taken.get(chat_id)
    if not data:
        await callback.message.edit_reply_markup(None)
        await callback.answer(tu['no_sharing'], show_alert=True)
        return
    
    game_db = Game.objects.filter(chat_id=chat_id, is_active_game=True).first()
    if not game_db:
        return
    
    game = await GameStorage.load(game_db.id)
    players = game.get("players",[]) if game else None
    if not  players :
        await callback.answer("❌ O‘yin topilmadi.", show_alert=True)
        return

    if user_id not in players :
        await callback.answer(tu['stone_not_in_game'], show_alert=True)
        return

    limit = data["limit"]
    taken = data["taken"]
    sender = data["creator"]
    sender = User.objects.filter(telegram_id=int(sender)).first()
    
    if user_id in taken:
        await callback.answer(tu['stone_already_taken'], show_alert=True)
        return

    if len(taken) >= limit:
        await callback.answer(tu['stone_ended'], show_alert=True)
        return

    taken.append(user_id)
    user_taker = User.objects.filter(telegram_id=user_id).first()
    if not user_taker:
        user_taker = User.objects.create(
            telegram_id=user_id, 
            first_name=callback.from_user.first_name,
            username=callback.from_user.username
        )

    users_qs = User.objects.filter(telegram_id__in=taken)
    taken_text = ""
    for i, user in enumerate(users_qs, start=1):
        taken_text += f"\n {i}. 💎 <a href='tg://user?id={user.telegram_id}'>{user.first_name}</a>"

    text = (
        f"💎 <a href='tg://user?id={sender.telegram_id}'>{sender.first_name}</a> {t['group_sender'].format(count=limit)}\n"
        f"{taken_text}"
    )

    if len(taken) >= limit:
        await callback.message.edit_text(text, reply_markup=None, parse_mode="HTML")
        gsend_taken.pop(chat_id, None)
    else:
        await callback.message.edit_text(text, reply_markup=take_gsend_stone_btn(chat_id), parse_mode="HTML")
    user_taker.stones += 1
    user_taker.save()
    await callback.answer(tu['stone_taken'])
    

@dp.callback_query(F.data == "giveaway_join")
async def giveaway_join(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    t = get_lang_text(chat_id)
    tu = get_lang_text(user_id)
    gw = giveaways.get(chat_id)
    if not gw:
        await callback.message.edit_reply_markup(None)
        await callback.answer(tu['giveway_not_active'], show_alert=True)
        return

    if time.time() >= gw["end_at"]:
        await callback.message.edit_reply_markup(None)
        await callback.answer(tu['giveway_ended'], show_alert=True)
        return

    if user_id in gw["members"]:
        await callback.answer(tu['giveway_already_joined'], show_alert=True)
        return
    user_taker = User.objects.filter(telegram_id=user_id).first()
    if not user_taker:
        user_taker = User.objects.create(
            telegram_id=user_id, 
            first_name=callback.from_user.first_name,
            username=callback.from_user.username
        )

    gw["members"].add(user_id)
    users_qs = User.objects.filter(telegram_id__in=gw["members"])
    end_at = gw["end_at"] - time.time()
    minut = int(end_at // 60)
    second = int(end_at % 60)
    line = [
            f"{i + 1}. <a href='tg://user?id={user.telegram_id}'>{user.first_name}</a>"
            for i, user in enumerate(users_qs)
        ]
    amount =gw['amount']
    quantity = len(gw["members"])
    text = t['giveway_continue'].format(amount=amount, minut=minut, second=second, text="\n".join(line), quantity=quantity)
    await callback.message.edit_text(text, reply_markup=giveaway_join_btn(chat_id), parse_mode="HTML")
    await callback.answer(tu['giveway_joined'])




@dp.callback_query(F.data == "user_talk")
async def user_talk(callback_query: CallbackQuery,state: FSMContext) -> None:
    await callback_query.answer()
    await callback_query.message.answer(text="💬 Suhbat uchun foydalanuvchi ID sini yuboring:",reply_markup=back_admin_btn())
    await state.set_state(QuestionState.user_id)
    
    

@dp.message(StateFilter(QuestionState.user_id))
async def process_user_id(message: Message, state: FSMContext) -> None:
    tg_id_text = message.text.strip() if message.text else None
    if not tg_id_text or not tg_id_text.isdigit():
        await message.answer("❗️ Iltimos, foydalanuvchi ID sini to'g'ri formatda yuboring.",reply_markup=back_admin_btn())
        return

    tg_id = int(tg_id_text)
    await state.update_data(user_talk_id=tg_id)
    if not User.objects.filter(telegram_id=tg_id).exists():
        await message.answer("❗️ Bunday ID li foydalanuvchi topilmadi. Iltimos, to'g'ri ID ni kiriting.",reply_markup=back_admin_btn())
        return
    await message.answer(
        text=f"💬 Foydalanuvchi (ID: {tg_id}) bilan suhbatni boshlang. Sizning xabaringiz ushbu foydalanuvchiga yuboriladi.",reply_markup=back_admin_btn()
    )
    await state.set_state(QuestionState.user_talk)

@dp.message(StateFilter(QuestionState.user_talk))
async def process_user_talk(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    tg_id = data.get("user_talk_id")
    msg_id = message.message_id

    try:
        await send_safe_message(
            chat_id=tg_id,
            text=f"💬 Admindan xabar:\n\n{message.text}",
            reply_markup=answer_admin(message.from_user.id, msg_id)
        )
        await message.answer("✅ Xabaringiz foydalanuvchiga yuborildi.\nYana gapingiz bolsa yozing",reply_markup=end_talk_keyboard())
    except Exception as e:
        await message.answer(f"❗️ Xatolik yuz berdi: {str(e)}")



@dp.callback_query(F.data.startswith("answer_admin_"))
async def answer_from_admin(callback_query: CallbackQuery,state: FSMContext) -> None:
    await callback_query.answer()
    await callback_query.message.edit_reply_markup(None)
    tg_id = int(callback_query.data.split("_")[-2])
    msg_id = int(callback_query.data.split("_")[-1])
    await callback_query.message.answer(
        text=f"💬 Javobingizni yozing. Sizning habaringiz adminga yetkaziladi"
    )
    await state.update_data(answer_to_admin_id=tg_id, answer_to_admin_msg_id=msg_id)
    
    await state.set_state(QuestionState.user_answer)
    
    
@dp.message(StateFilter(QuestionState.user_answer))
async def process_answer_to_admin(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    tg_id = data.get("answer_to_admin_id")
    msg_id = data.get("answer_to_admin_msg_id")

    try:
        await send_safe_message(
            chat_id=tg_id,
            text=f"💬 Foydalanuvchidan javob:\n\n{message.text}",
            reply_to_message_id=msg_id
        )
        await message.answer("✅ Javobingiz adminga yuborildi.")
    except Exception as e:
        await message.answer(f"❗️ Xatolik yuz berdi: {str(e)}")
    await state.clear()
    
    
@dp.callback_query(F.data == "end_talk")
async def end_talk(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    await state.clear()
    await callback_query.message.answer("💬 Suhbat yakunlandi.",reply_markup=admin_inline_btn())
    
    
    
@dp.callback_query(F.data == "broadcast_message")
async def broadcast_message(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    await callback_query.message.answer("📢 Iltimos, bot foydalanuvchilariga jo'natiladigan xabar matnini kiriting:",reply_markup=back_admin_btn())
    await state.set_state(Register.every_one)
    
BATCH_SIZE = 25
DELAY = 0.03

@dp.message(StateFilter(Register.every_one))
async def process_broadcast_message(message: Message, state: FSMContext):
    text = message.text.strip() if message.text else None
    if not text:
        await message.answer("❗️ Iltimos, xabar matnini kiriting.")
        return

    await message.answer("⏳ Xabar yuborilmoqda...")

    await state.clear()
    success = 0
    fail = 0

    users = User.objects.all().values_list("telegram_id", flat=True)

    batch = []
    for tg_id in users.iterator():
        batch.append(tg_id)

        if len(batch) >= BATCH_SIZE:
            for uid in batch:
                try:
                    await send_safe_message(uid, f"📢 Botdan umumiy xabar:\n\n{text}")
                    success += 1
                    await sleep(DELAY)
                except TelegramForbiddenError:
                    fail += 1
                except TelegramRetryAfter as e:
                    await sleep(e.retry_after)
                except:
                    fail += 1
            batch.clear()

    for uid in batch:
        try:
            await send_safe_message(uid, f"📢 Botdan umumiy xabar:\n\n{text}")
            success += 1
            await sleep(DELAY)
        except:
            fail += 1

    await message.answer(
        f"📢 Xabar yuborildi.\n\n✅ Muvaffaqiyatli: {success}\n❌ Muvaffaqiyatsiz: {fail}",
        reply_markup=admin_inline_btn()
    )


@dp.callback_query(F.data == "close")
async def close_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    
    
@dp.callback_query(F.data.startswith("prem_"))
async def premium_manage_callback(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    chat_id = int(callback.data.split("_")[2])
    game_trial = GroupTrials.objects.filter(group_id=chat_id).first()
    if not game_trial:
        await callback.answer("❌ Guruh topilmadi.")
        return
    game_trial.premium_stones = amount
    game_trial.stones -= amount
    game_trial.prem_ends_date = timezone.now() + timedelta(days=14)
    game_trial.save()
    await callback.answer(text=f"✅ Guruhga {amount} olmosli premium berildi.", show_alert=True)
    PremiumGroup.objects.update_or_create(
        name = game_trial.group_name,
        group_id = chat_id,
        defaults={
            "link": game_trial.group_username,
            "ends_date": timezone.now() + timedelta(days=14),
            "stones_for": amount
        }
    )
        
        
    

@dp.callback_query(F.data == "privacy")
async def privacy_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        text="Kirish so'zlarni o'zgartirish uchun quyidagi tugmalardan foydalaning:",
        reply_markup=privacy_inline_btn()
    )
    
@dp.callback_query(F.data.startswith("credentials_"))
async def credentials_callback(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    action = callback.data.split("_")[1]
    await state.update_data(action=action)
    if action == "password":
        await callback.message.edit_text(
            text="🔐 Iltimos, yangi parolini so'zlarni yuboring:",
            reply_markup=back_admin_btn()
        )
        await state.set_state(CredentialsState.waiting_for_new_password)
    elif action == "username":
        await callback.message.edit_text(
            text="🔐 Iltimos, yangi foydalanuvchi nomini yuboring:",
            reply_markup=back_btn(callback.from_user.id)
        )
        await state.set_state(CredentialsState.waiting_for_new_username)
        
        
@dp.message(CredentialsState.waiting_for_new_password)
async def process_new_password(message: Message, state: FSMContext) -> None:
    new_password = message.text.strip() if message.text else None
    if not new_password:
        await message.answer(
            text="❌ Iltimos, yangi parolini so'zlarni yuboring:",
            reply_markup=back_admin_btn()
        )
        return

    cred = BotCredentials.objects.first()
    if not cred:
        cred = BotCredentials.objects.create()

    new_pass = make_password(new_password)
    cred.password = new_pass
    cred.save()

    await message.answer(
        text="✅ Bot paroli muvaffaqiyatli o'zgartirildi.",
        reply_markup=admin_inline_btn()
    )
    await state.clear()
    
@dp.message(CredentialsState.waiting_for_new_username)
async def process_new_username(message: Message, state: FSMContext) -> None:
    new_username = message.text.strip() if message.text else None
    if not new_username:
        await message.answer(
            text="❌ Iltimos, yangi foydalanuvchi nomini yuboring:",
            reply_markup=back_btn(message.from_user.id)
        )
        return

    cred = BotCredentials.objects.first()
    if not cred:
        cred = BotCredentials.objects.create()

    cred.username = new_username
    cred.save()

    await message.answer(
        text="✅ Bot foydalanuvchi nomi muvaffaqiyatli o'zgartirildi.",
        reply_markup=admin_inline_btn()
    )
    await state.clear()
    
@dp.callback_query(F.data.startswith("hero_"))
async def hero_callback(callback: CallbackQuery):
    _, hero_type, game_id, chat_id, day = callback.data.split("_")
    game_id = int(game_id)
    hero_id = callback.from_user.id
    day = int(day)

    game = await GameStorage.load(game_id)
    if not game.data:
        return

    current_day = game['meta']['day']
    t = get_lang_text(hero_id)
    if current_day != day:
        await callback.message.edit_text(
            f"{get_actions_lang(hero_id)['hero']}\n\n{t['late']}",
            parse_mode="HTML"
        )
        return

    if hero_id not in game["alive"]:
        return

    users_map = game["users_map"]
    alive_users_qs = [users_map[tg_id] for tg_id in game["alive"] if tg_id in users_map]


    if hero_type == "attack":
        await callback.message.edit_text(
            f"{get_actions_lang(hero_id)['hero']}",
            reply_markup=action_inline_btn(action="day_attack", own_id=hero_id, players=alive_users_qs, game_id=game_id, chat_id=chat_id, day=current_day),
            parse_mode="HTML"
        )
        return
        
    elif hero_type == "protect":

        await callback.message.edit_text(
            f"{get_actions_lang(hero_id)['hero']}\n\n{t['hero_protect_self']}",
            parse_mode="HTML"
        )
        hero_data = game.setdefault("hero", {"has": set(), "used": set(), "notified": set(), "self_protect": set()}) # 🔥 AGAR TARGET YO‘Q BO‘LSA O‘ZINI
        if hero_id in hero_data["self_protect"]:
            return
        
        hero_data["used"].add(hero_id)
        hero_data["self_protect"].add(hero_id)

@dp.callback_query(F.data.startswith("day_attack_"))
async def day_attack_callback(callback: CallbackQuery):
    _, _, target_id, game_id, chat_id, day = callback.data.split("_")
    target_id = target_id
    game_id = int(game_id)
    chat_id = int(chat_id)
    day = int(day)
    hero_id = callback.from_user.id
    if target_id == "no":
        return
    target_id = int(target_id)
    game = await GameStorage.load(game_id)
    if not game.data:
        return

    if game["meta"]["day"] != day:
        return

    if hero_id not in game["alive"] or target_id not in game["alive"]:
        return


    
    target_user = game["users_map"].get(target_id)
    if target_user and target_user.get("geroy_protect") > 0:
        target = User.objects.filter(telegram_id=target_id).first()
        target_user["geroy_protect"] -= 1
        if target:
            target.geroy_protection -= 1
            target.save()
        await callback.answer("Bu foydalanuvchi geroy tomonidan himoyalangan", show_alert=True)
        return

    game["hero"]["used"].add(hero_id)

    # HP tracking
    game.setdefault("hero_damage", {})
    game["hero_damage"].setdefault(target_id, {"hp_percent": 100})

    data = game["hero_damage"][target_id]
    target_name = game["users_map"].get(target_id, {}).get("first_name", "Noma'lum")

    hero_level = get_hero_level(hero_id)
    damage = hero_level * 3 + 50

    data["hp_percent"] -= damage
    hp_left = max(data["hp_percent"], 0)

    t = get_lang_text(hero_id)
    tu = get_lang_text(chat_id)

    # ☠ kill condition
    if hp_left <= 0:
        kill(game, target_id)
        role_target = role_label(game['roles'].get(target_id), chat_id)

        await send_safe_message(
            chat_id=chat_id,
            text=tu['hero_killed'].format(target_name=target_name, role_target=role_target),
            parse_mode="HTML"
        )
    else:
        await send_safe_message(
            chat_id=chat_id,
            text=tu['hero_attack'].format(target_name=target_name, damage=damage, hp_data=hp_left),
            parse_mode="HTML"
        )



@dp.callback_query(F.data.startswith("geroy_"))
async def geroy_callback(callback: CallbackQuery):
    action = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user = User.objects.filter(telegram_id=user_id).first()
    if not user:
        user = User.objects.create(
            first_name = callback.from_user.first_name,
            username = callback.from_user.username,
            telegram_id = user_id
        )
    t = get_lang_text(user_id)
    if action == "no":
        await callback.message.edit_text(t['hero_info'],reply_markup=geroy_inline_btn(user_id))
    elif action == "buy":
        if user.stones < 100:
            await callback.answer(t['not_enough_stones'])
            return
        user.stones -= 100
        user.is_hero = True
        user.hero_level = 1
        user.save()
        await callback.message.edit_text(t['hero_bought'],reply_markup=start_inline_btn(callback.from_user.id))
    elif action == "upgrade":
        price = user.hero_level * 10 + 100
        if user.stones < price:
            await callback.answer(t['not_enough_stones'])
            return
        user.hero_level += 1
        user.stones -= price
        user.save()
        await callback.message.edit_text(t['hero_upgraded'].format(level=user.hero_level),reply_markup=start_inline_btn(callback.from_user.id))
    elif action == "sold":
        user.is_hero=False
        user.hero_level=1
        user.save()
        await callback.message.edit_text(t['hero_remove'],reply_markup=start_inline_btn(callback.from_user.id))
        
import openpyxl
from aiogram.types import FSInputFile

        
@dp.callback_query(F.data == "export_users_excel")
async def export_users_excel(callback: CallbackQuery):
    await callback.answer()
    file_path = "/tmp/users.xlsx"

    users = User.objects.all().values(
        "telegram_id",
        "first_name",
        "username",
        "lang",
        "coin",
        "stones",
        "protection",
        "hang_protect",
        "docs",
        "active_role",
        "role",
        "is_vip",
        "is_hero",
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Users"

    headers = [
        "Telegram ID","First Name","Username","Lang","Coin","Stones",
        "Protection","Hang Protect","Docs","Active Role",
        "Role","VIP","Hero"
    ]
    ws.append(headers)

    for u in users:
        ws.append([
            u["telegram_id"],
            u["first_name"],
            u["username"],
            u["lang"],
            u["coin"],
            u["stones"],
            u["protection"],
            u["hang_protect"],
            u["docs"],
            u["active_role"],
            u["role"],
            u["is_vip"],
            u["is_hero"]
        ])

    wb.save(file_path)

    await callback.message.answer_document(FSInputFile(file_path))




def set_user_lang(callback, lang: str):
    tg_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    if callback.message.chat.type != "private":
        tg_id = callback.message.chat.id
        group = GroupTrials.objects.filter(group_id=tg_id).first()
        if group:
            group.lang = lang
            group.save()
            USER_LANG_CACHE[tg_id] = lang
        return
    
    User.objects.update_or_create(
        telegram_id=tg_id,
        defaults={"lang": lang,
                  "username": username,
                  "first_name": first_name}
    )
    USER_LANG_CACHE[tg_id] = lang




@dp.callback_query(F.data.startswith("lang_"))
async def set_language_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[1]

    set_user_lang(callback, lang)

    texts = {
        "uz": "✅ Til o'zbek tiliga o'zgartirildi",
        "ru": "✅ Язык изменён на русский",
        "en": "✅ Language changed to English",
        "tr": "✅ Dil Türkçe olarak değiştirildi",
        "qz": "✅ Тіл қазақ тіліне өзгертілді"
    }
    if callback.message.chat.type == "private":
        await callback.message.edit_text(texts.get(lang, texts["uz"]),reply_markup=start_inline_btn(callback.from_user.id))
        return
    await callback.message.edit_text(texts.get(lang, texts["uz"]),reply_markup=group_profile_inline_btn(True,callback.message.chat.id))
    await callback.answer()


@dp.callback_query(F.data == "lange_group")
async def lange_group_callback(callback: CallbackQuery,state: FSMContext) -> None:
    await callback.answer()
    await callback.message.edit_text(
        text="Language / Tilni tanlang / Выберите язык / Dil seçin / Тілді таңдаңыз:",
        reply_markup=language_keyboard()
    )
    
    
@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_profile_callback(callback: CallbackQuery):
    await callback.answer()
    setting = callback.data.split("_")[1]
    chat_id = callback.from_user.id
    user = User.objects.filter(telegram_id=chat_id).first()
    if setting == "protection":
        user.is_protected = not user.is_protected
    elif setting == "hang":
        user.is_hang_protected = not user.is_hang_protected
    elif setting == "doc":
        user.is_doc = not user.is_doc
    elif setting == "geroy":
        user.is_geroy_protected = not user.is_geroy_protected
    elif setting == "geroyuse":
        user.is_geroy_use = not user.is_geroy_use
    elif setting == "activerole":
        user.is_active_role_use = not user.is_active_role_use
    user.save()
    text =""
    user_role = UserRole.objects.filter(user_id=user.id)
    for user_r in user_role:
        role_name = dict(get_role_labels_lang(chat_id)).get(user_r.role_key, "Noma'lum rol")
        text += f"🎭 {role_name} -  {user_r.quantity}\n"
    t = get_lang_text(chat_id)
    result = MostActiveUser.objects.filter(user_id=user.id).aggregate(
    total_played=Sum('games_played'),
    total_wins=Sum('games_win')
)

    total_played = result['total_played'] or 0
    total_wins = result['total_wins'] or 0

    await callback.message.edit_text(
        text=t['user_profile'].format(
            first_name=callback.from_user.first_name,
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
        parse_mode="HTML",reply_markup=cart_inline_btn(chat_id)
    )