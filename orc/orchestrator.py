from connectors.cosmos import ConversationCache
from orc.run import get_answer
    
async def run(conversation_id, ask: str):
    async with ConversationCache() as db_cache:
        history = await db_cache.get_messages(conversation_id)
        await db_cache.push_message(conversation_id, "user", ask)
        user_data = await db_cache.get_user_data(conversation_id+":user_data")
        print("User data: ", user_data)
        response, is_agent_required,data, is_data_changed = await get_answer(ask, history, conversation_id, user_data)
        if is_data_changed:
            await db_cache.push_user_data(conversation_id+":user_data", data)
        await db_cache.push_message(conversation_id, "assistant", response)
    return response, is_agent_required