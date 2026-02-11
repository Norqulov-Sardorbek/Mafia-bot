from aiogram.fsm.state import StatesGroup, State


class AddGroupState(StatesGroup):
    waiting_for_group_name = State()
    waiting_for_group_link= State()
    waiting_for_olmos_amount= State()
    
class SendMoneyState(StatesGroup):
    waiting_for_money = State()
    waiting_for_olmos = State()
    waiting_olmos_to_remove = State()
    waiting_money_to_remove = State()
    waiting_for_channel_olmos = State()
    
    
class ChangeStoneCostState(StatesGroup):
    waiting_for_money_cost = State()
    waiting_for_star_cost = State()

class ChangeMoneyCostState(StatesGroup):
    waiting_for_money_cost = State()
    waiting_for_star_cost = State()
    
class BeginInstanceState(StatesGroup):
    waiting_for_instant_count = State()
    waiting_for_instant_time = State()
    
class ExtendGroupState(StatesGroup):
    waiting_for_extend_info = State()
    waiting_for_amount= State()
    
class QuestionState(StatesGroup):
    question_name = State()
    waiting_for_question = State()
    user_talk = State()
    user_id = State()
    user_answer = State()
    
class Register(StatesGroup):
    full_name = State()
    phone_number = State()
    answer = State()
    every_one = State()
    
class CredentialsState(StatesGroup):
    waiting_for_new_password = State()
    waiting_for_new_username = State()
    login = State()