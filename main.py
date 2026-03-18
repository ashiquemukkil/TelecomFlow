# sample fastapi application with post endpoint to receive data and return a response

from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import logging

from orc.orchestrator import run
logging.basicConfig(level=logging.INFO)

app = FastAPI()

class ChatRequest(BaseModel):
    phone: str
    ask: str
    history: Optional[List[str]] = None

class ChatResponse(BaseModel):
    id: str
    answer: str
    is_allowed: Optional[bool] = True

@app.post("/chat", response_model=ChatResponse, include_in_schema=False)
async def create_item(chat: ChatRequest):
    response, is_agent_required = await run(chat.phone, chat.ask)
    logging.info(f"Response for phone {chat.phone}: {response}, Agent required: {is_agent_required}")
    # if "8714446494" in chat.phone or "69999" in chat.phone:
    return ChatResponse(id=chat.phone, answer=response, is_allowed=not is_agent_required)
    # return ChatResponse(id=chat.phone, answer=response, is_allowed=False)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # https://telecomflow.onrender.com