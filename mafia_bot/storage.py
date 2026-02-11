import json
from core.redis_client import redis_client


class GameStorage:

    def __init__(self, game_id: int, data: dict | None = None):
        self.game_id = game_id
        self.data = data or {}

    # 🔹 Redisdan yuklash
    @classmethod
    async def load(cls, game_id: int):
        raw = await redis_client.get(f"game:{game_id}")
        data = json.loads(raw) if raw else None
        return cls(game_id, data or {})

    # 🔹 Redisga saqlash
    async def save(self):
        await redis_client.set(
            f"game:{self.game_id}",
            json.dumps(self.data)
        )

    # 🔹 O‘chirish
    async def delete(self):
        await redis_client.delete(f"game:{self.game_id}")

    # 🔹 dict kabi ishlashi uchun
    def __getitem__(self, key):
        return self.data.get(key)

    def __setitem__(self, key, value):
        self.data[key] = value

    def __contains__(self, key):
        return key in self.data

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, value: dict):
        self.data.update(value)
