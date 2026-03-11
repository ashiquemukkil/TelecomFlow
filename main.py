# sample fastapi application with post endpoint to receive data and return a response

from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

from orc.orchestrator import run

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
    return ChatResponse(id=chat.phone, answer=response, is_allowed=not is_agent_required)
    # if chat.phone not in ["1234567890", "8714446494"]:
    #     return ChatResponse(id=chat.phone, answer="Sorry, you are not allowed to ask questions.", is_allowed=False)
    # return ChatResponse(id=chat.phone, answer=f"Received your question: {chat.ask}. History: {chat.history}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # https://telecomflow.onrender.com