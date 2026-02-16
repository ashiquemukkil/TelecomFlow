# sample fastapi application with post endpoint to receive data and return a response

from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    phone: str
    ask: str
    history: Optional[List[str]] = None

class ChatResponse(BaseModel):
    id: str
    answer: str
    is_allowed: Optional[bool] = True

@app.post("/chat/", response_model=ChatResponse)
async def create_item(chat: ChatRequest):
    if chat.phone not in ["1234567890", "8714446494"]:
        return ChatResponse(id=chat.phone, answer="Sorry, you are not allowed to ask questions.", is_allowed=False)
    return ChatResponse(id=chat.phone, answer=f"Received your question: {chat.ask}. History: {chat.history}")