from pathlib import Path
from urllib.parse import quote
import os

import gradio as gr
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_PATH = PROJECT_ROOT / "logs.txt"

load_dotenv()

from libs import agent_loop, tools

with open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write("")


def chat_agent_with_live_chat(user_message, history):
    agent_result = agent_loop.chat_agent(user_message, history)
    if isinstance(agent_result, tuple):
        response = agent_result[0]
        session_id = agent_result[1] if len(agent_result) > 1 else None
    else:
        response = agent_result
        session_id = None

    if not session_id:
        return response, gr.skip(), gr.skip()

    fastapi_url = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000").rstrip("/")
    iframe_url = (
        f"{fastapi_url}/live-chat-ui"
        f"?session_id={quote(str(session_id))}&role=user"
    )
    return (
        response,
        gr.update(elem_id="live_chat", visible=True),
        f'<iframe src="{iframe_url}" width="100%" '
        'style="height: calc(100vh - 180px); min-height: 500px; border: 0;"></iframe>',
    )



with gr.Blocks(fill_height=True, css="html, body { min-height: 100%; } .gradio-container { min-height: 100vh; }") as demo:
    gr.Markdown("## Sanal Servis Danışmanı")
    with gr.Row(scale=1):
        with gr.Column(scale=1, visible=False, elem_id="live_chat") as live_chat:
            gr.Markdown("### Canlı Destek Sohbeti:")
            live_chat_frame = gr.HTML()
        with gr.Column(scale=1) as llm_assistant:
            gr.ChatInterface(
                fn=chat_agent_with_live_chat,
                chatbot=gr.Chatbot(height="calc(100vh - 250px)"),
                additional_outputs=[live_chat, live_chat_frame],
                title="Anadolu Isuzu Yardımcı Asistan",
            )

demo.launch()