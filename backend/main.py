import sys
import os
import json
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import run_agent, stream_agent
from knowledge_base import build_knowledge_base

build_knowledge_base()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

class ChatRequest(BaseModel):
    messages: list[dict]

@app.post("/chat")
async def chat(request: ChatRequest):
    return run_agent(request.messages)

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    def generate():
        for event in stream_agent(request.messages):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )