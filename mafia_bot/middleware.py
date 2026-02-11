from aiogram import BaseMiddleware
from django.db import connections

class DjangoDBMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        finally:
            for conn in connections.all():
                conn.close()
