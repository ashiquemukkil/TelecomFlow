# sample fastapi application with post endpoint to receive data and return a response

from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import logging

from admin import router as admin_router
from orc.orchestrator import run
logging.basicConfig(level=logging.INFO)

app = FastAPI()
app.include_router(admin_router)

class ChatRequest(BaseModel):
    phone: str
    ask: str
    history: Optional[List[str]] = None

class UserData(BaseModel):
    traveler_type: Optional[str] = None # family/couple/friends/bachelor_group/solo
    trip_type: Optional[str] = None # group/private/customized
    number_of_travelers: Optional[str] = None
    travel_dates: Optional[str] = None

class ChatResponse(BaseModel):
    id: str
    answer: str
    is_allowed: Optional[bool] = True
    is_data_changed: Optional[int] = 0
    user_data: Optional[UserData] = None

@app.post("/chat", response_model=ChatResponse, include_in_schema=False)
async def create_item(chat: ChatRequest):
    response, is_agent_required, data, is_data_changed = await run(chat.phone, chat.ask)
    logging.info(f"Response for phone {chat.phone}: {response}, Agent required: {is_agent_required}")
    user_data = UserData(**data) if data else None
    return ChatResponse(id=chat.phone, answer=response, is_allowed=not is_agent_required, is_data_changed=is_data_changed, user_data=user_data)
    # return ChatResponse(id=chat.phone, answer=response, is_allowed=False)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # https://telecomflow.onrender.com

