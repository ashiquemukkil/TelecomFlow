from connectors.cosmos import ConversationCache
from orc.run import get_answer
    
async def run(conversation_id, ask: str):
    async with ConversationCache() as db_cache:
        history = await db_cache.get_messages(conversation_id)
        await db_cache.push_message(conversation_id, "user", ask)
        response = await get_answer(ask, history, conversation_id)
        await db_cache.push_message(conversation_id, "assistant", response)
    return response