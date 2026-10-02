from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()
DB_CONNINFO = os.getenv("POSTGRES_URL", "postgresql://localhost:5432/AnadoluIsuzuDB")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncConnectionPool(
        conninfo=DB_CONNINFO, min_size=2, max_size=10
    ) as pool:
        app.state.pool = pool
        app.state.manager = ConnectionManager()
        yield
    # pool `async with` çıkışında otomatik kapanır


app = FastAPI(lifespan=lifespan)
LIVE_CHAT_DIR = Path(__file__).resolve().parent
app.mount("/live-chat", StaticFiles(directory=LIVE_CHAT_DIR), name="live-chat")


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(session_id, []).append(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        conns = self.active.get(session_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.active.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict):
            dead_connections = []
            for ws in self.active.get(session_id, []):
                try:
                    await ws.send_json(message)
                except RuntimeError:
                    dead_connections.append(ws)
                except Exception:
                    dead_connections.append(ws)
            
            for dead_ws in dead_connections:
                self.disconnect(session_id, dead_ws)


class EscalateRequest(BaseModel):
    runtime_user_id: str
    summary: str


class EscalateResponse(BaseModel):
    escalate: bool
    assigned: bool = False
    reason: Optional[str] = None
    session_id: str
    staff_name: str


class SendMessageRequest(BaseModel):
    sender_role: str  # user - staff - system
    message_text: str


class CloseSessionRequest(BaseModel):
    reason: Optional[str] = None

@app.post("/escalate", response_model=EscalateResponse)
async def escalate(payload: EscalateRequest, request: Request):

    pool: AsyncConnectionPool = request.app.state.pool

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT uid, name, surname
                FROM technical_staff
                WHERE currently_available = true
                ORDER BY random()
                LIMIT 1
                """,
            )
            staff = await cur.fetchone()

            if not staff:
                return EscalateResponse(
                    escalate=True,
                    assigned=False,
                    reason="Canlı Sohbet için müsait personel yok",
                )

            await cur.execute(
                """
                INSERT INTO chat_sessions (technical_staff_uid, runtime_user_id)
                VALUES (%s, %s)
                RETURNING session_id
                """,
                (staff["uid"], payload.runtime_user_id),
            )
            session = await cur.fetchone()
            session_id = session["session_id"]

            # personeli meşgul işaretle
            await cur.execute(
                "UPDATE technical_staff SET currently_available = false WHERE uid = %s",
                (staff["uid"],),
            )

            # sistem mesajı olarak context'i logla
            await cur.execute(
                """
                INSERT INTO chat_messages (session_id, sender_role, message_text)
                VALUES (%s, 'system', %s)
                """,
                (session_id, f"Oturum açıldı."),
            )

        await conn.commit()

    return EscalateResponse(
        escalate=True,
        assigned=True,
        session_id=str(session_id),
        staff_name=f"{staff['name']} {staff['surname']}",
        reason="Oturum açıldı.",
    )


@app.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, payload: SendMessageRequest, request: Request):
    pool: AsyncConnectionPool = request.app.state.pool
    manager: ConnectionManager = request.app.state.manager

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT status FROM chat_sessions WHERE session_id = %s",
                (session_id,),
            )
            session = await cur.fetchone()
            if session is None:
                raise HTTPException(status_code=404, detail="Session bulunamadı")
            if session["status"] != "active":
                raise HTTPException(status_code=400, detail="Session aktif değil")

            await cur.execute(
                """
                INSERT INTO chat_messages (session_id, sender_role, message_text)
                VALUES (%s, %s, %s)
                RETURNING message_id, created_at
                """,
                (session_id, payload.sender_role, payload.message_text),
            )
            row = await cur.fetchone()
        await conn.commit()

    message = {
        "message_id": row["message_id"],
        "sender_role": payload.sender_role,
        "message_text": payload.message_text,
        "created_at": row["created_at"].isoformat(),
    }
    await manager.broadcast(session_id, message)
    return {"status": "ok", "message": message}


@app.post("/sessions/{session_id}/close")
async def close_session(
    session_id: str, payload: CloseSessionRequest, request: Request
):
    pool: AsyncConnectionPool = request.app.state.pool

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT technical_staff_uid, status
                FROM chat_sessions
                WHERE session_id = %s
                FOR UPDATE
                """,
                (session_id,),
            )
            session = await cur.fetchone()
            if session is None:
                raise HTTPException(status_code=404, detail="Session bulunamadı")

            if session["status"] == "active":
                await cur.execute(
                    "UPDATE chat_sessions SET status = 'closed' WHERE session_id = %s",
                    (session_id,),
                )

                if session["technical_staff_uid"] is not None:
                    await cur.execute(
                        "UPDATE technical_staff SET currently_available = true WHERE uid = %s",
                        (session["technical_staff_uid"],),
                    )

            if payload.reason and session["status"] == "active":
                await cur.execute(
                    """
                    INSERT INTO chat_messages (session_id, sender_role, message_text)
                    VALUES (%s, 'system', %s)
                    """,
                    (session_id, f"Oturum kapatıldı: {payload.reason}"),
                )

        await conn.commit()

    return {"status": "closed", "session_id": str(session_id)}


@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, request: Request):
    pool: AsyncConnectionPool = request.app.state.pool

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT message_id, sender_role, message_text, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
            rows = await cur.fetchall()

    return {
        "session_id": session_id,
        "messages": [
            {
                "message_id": r["message_id"],
                "sender_role": r["sender_role"],
                "message_text": r["message_text"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    pool: AsyncConnectionPool = websocket.app.state.pool
    manager: ConnectionManager = websocket.app.state.manager

    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # beklenen format: {"sender_role": "...", "message_text": "..."}
            sender_role = data.get("sender_role", "unknown")
            message_text = data.get("message_text", "")

            async with pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        """
                        INSERT INTO chat_messages (session_id, sender_role, message_text)
                        VALUES (%s, %s, %s)
                        RETURNING message_id, created_at
                        """,
                        (session_id, sender_role, message_text),
                    )
                    row = await cur.fetchone()
                await conn.commit()

            message = {
                "message_id": row["message_id"],
                "sender_role": sender_role,
                "message_text": message_text,
                "created_at": row["created_at"].isoformat(),
            }
            await manager.broadcast(session_id, message)
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
    finally:
        manager.disconnect(session_id,websocket)

@app.get("/live-chat-ui")
async def get_live_chat_ui():
    html_path = LIVE_CHAT_DIR / "live_chat.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))