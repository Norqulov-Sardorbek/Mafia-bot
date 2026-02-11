from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from decouple import config
from aiogram.client.default import DefaultBotProperties
from aiogram import Bot
from aiogram.enums import ParseMode
from mafia_bot.middleware import DjangoDBMiddleware

TOKEN = config("BOT_TOKEN")


print(TOKEN)

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.update.middleware(DjangoDBMiddleware())