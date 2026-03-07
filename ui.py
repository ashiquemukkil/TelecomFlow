# file equalant to main.py for chainlit, which will be called by the fastapi application to run the orchestrator and return a response
import chainlit as cl

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

@cl.on_chat_start
async def start():
    # Ask phone number before chat
    res = await cl.AskUserMessage(
        content="📱 Please enter your phone number to start the chat:",
        timeout=300
    ).send()

    if res:
        phone_number = res["output"]

        # store in session
        cl.user_session.set("phone_number", phone_number)

        await cl.Message(
            content=f"✅ Phone number received: {phone_number}\n\nHow can I help you today?"
        ).send()

@cl.on_message
async def main(message: cl.Message):
    # for testing, we can use a fixed phone number and history

    phone = cl.user_session.get("phone_number")

    response = await run(phone, message.content)
    await cl.Message(content=response).send()