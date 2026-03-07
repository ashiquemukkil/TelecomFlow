import asyncio
from cachetools import TTLCache
from datetime import datetime
from typing import List, Dict, Any

CACHE = TTLCache(maxsize=100, ttl=3 * 24 * 60 * 60)

class ConversationCache:
    def __init__(self):
        """
        :param max_users: Maximum number of users to cache
        :param ttl_seconds: Time-to-live for each user's conversation
        """
        self.cache = CACHE
        self.lock = asyncio.Lock()

    async def __aenter__(self) -> "ConversationCache":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def push_message(self, user_id: str, role: str, content: str) -> None:
        """
        Add a single message for a user.
        Keeps only the last 5 messages.
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }

        async with self.lock:
            messages = self.cache.get(user_id, [])
            messages.append(message)

            # Keep only last 5
            messages = messages[-5:]

            self.cache[user_id] = messages

    async def get_messages(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve messages for a user.
        Returns empty list if not found or expired.
        """
        async with self.lock:
            return self.cache.get(user_id, []).copy()

    async def clear(self, user_id: str) -> None:
        """
        Remove conversation for a user.
        """
        async with self.lock:
            self.cache.pop(user_id, None)


async def main() -> None:
    cache = ConversationCache()

    await cache.push_message("user1", "user", "Hello!")
    await cache.push_message("user1", "assistant", "Hi there! How can I help you?")
    await cache.push_message("user1", "user", "Can you tell me a joke?")
    await cache.push_message("user1", "assistant", "Why don't scientists trust atoms? Because they make up everything!")
    await cache.push_message("user1", "user", "That's funny! Do you have another one?")
    await cache.push_message("user1", "assistant", "Sure! Why did the scarecrow win an award? Because he was outstanding in his field!")

    print(await cache.get_messages("user1"))
    await cache.clear("user1")
    print(await cache.get_messages("user1"))  # Should be empty after clearing


if __name__ == "__main__":
    asyncio.run(main())