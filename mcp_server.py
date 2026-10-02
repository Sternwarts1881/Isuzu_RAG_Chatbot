from mcp.server import MCPServer
import psycopg
from qdrant_client import QdrantClient, models, AsyncQdrantClient
import random
import asyncio
from dotenv import load_dotenv
import os
from pathlib import Path
from live_chat.fastapi_server import (
    EscalateRequest,
    EscalateResponse,
    SendMessageRequest,
    CloseSessionRequest,
)
from libs.tools import APPEND_LOG
import uuid
from fastapi import FastAPI
import requests
import json
import re

load_dotenv()
mcp = MCPServer("AnadoluIsuzuMCPServer")
"""
                ---                 ISTERLER                    ---

  - `get_warranty_status(sasi_no)` → sentetik garanti verisinden sorgu
  - `check_part_stock(parca_kodu)` → sentetik stok verisinden sorgu
  - `create_work_order(sasi_no, aciklama)` → sahte bir "iş emri" oluşturma (DB'ye/JSON'a yazma)

"""
qdrant_client = AsyncQdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6334"),
    timeout=60,
    prefer_grpc=True,
    check_compatibility=False,
)
collection_name = os.getenv("QDRANT_COLLECTION_NAME", "car_data")

fastapi_server_url = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000")


# YARDIMCI OLARAK EKLEDIM, SONUCU ÇAĞIRAN FONKSİYON İŞLEYECEK
async def _qdrant_metadata_query(value: str, filter_keyword: str) -> tuple | None:
    query_result = await qdrant_client.scroll(
        collection_name=collection_name,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key=filter_keyword,
                    match=models.MatchValue(value=value),
                ),
            ]
        ),
    )
    return query_result


@mcp.tool()
async def get_warranty_status(sasi_no: str):
    """
    Şasi numarası verilen aracın  garanti bilgilerini sunucudan getir.

    Args:
        sasi_no: Aracın 17 kelime uzunluğundaki şasi numarası

    """
    APPEND_LOG(f"get_warranty_status çağırıldı, şasi no : {sasi_no}\n")

    query_result = await _qdrant_metadata_query(sasi_no, "sasi_no")

    if query_result is None:
        error = f"{sasi_no} şasi numaralı aracın garanti kayıdı bulunmamaktadır"
        APPEND_LOG(f"get_warranty_status Hata! : {error}\n")
        return error

    else:
        record_list = query_result[0]

        if len(record_list) > 1 | len(record_list) <= 0:
            error = f"{sasi_no} şasi numaralı araca ait birden fazla veya 0 garanti kayıdı mevcut"
            APPEND_LOG(f"get_warranty_status Hata! : {error}\n")
            return error
        else:
            result_element = record_list[0]
            if result_element.payload:
                APPEND_LOG(f"get_warranty_status başarılı, şasi no : {sasi_no}\n")
                return result_element.payload
            else:
                error = (
                    f"{sasi_no} şasi numaralı araca ait garanti kayıdı bilgileri eksik"
                )
                APPEND_LOG(f"get_warranty_status Hata! : {error}\n")
                return error


@mcp.tool()
async def check_part_stock(parca_kodu: str):
    """
    Parça numarası verilen yedek parçanın bilgilerini sunucudan getir.

    Args:
        parca_kodu: Yedek parçanın kodu

    """
    APPEND_LOG(f"check_part_stock çağırıldı, parça kodu : {parca_kodu}\n")

    query_result = await _qdrant_metadata_query(parca_kodu, "kod")
    if query_result is None:
        error = (
            f"{parca_kodu} parça kodlu yedek parçanın sunucuda kayıdı bulunmamaktadır"
        )
        APPEND_LOG(f"check_part_stock Hata! : {error}\n")
        return error

    else:
        record_list = query_result[0]

        if len(record_list) > 1 | len(record_list) <= 0:
            error = f"{parca_kodu} parça koduna ait birden fazla veya 0 yedek parça kayıdı mevcut"
            APPEND_LOG(f"check_part_stock Hata! : {error}\n")
            return error
        else:
            result_element = record_list[0]

            if result_element.payload:
                APPEND_LOG(f"check_part_stock başarılı, parça kodu : {parca_kodu}\n")
                return result_element.payload
            else:
                error = f"{parca_kodu} parça koduna ait yedek parçanın bilgileri eksik"
                APPEND_LOG(f"check_part_stock Hata! : {error}\n")
                return error


@mcp.tool()
async def create_work_order(sasi_no: str, aciklama: str) -> str:
    """
    Şasi numarası verilen araç için sunucuda iş emri açma.

    Args:
        sasi_no: Aracın 17 kelime uzunluğundaki şasi numarası
        aciklama: Yapılacak işin detaylı açıklaması

    """
    APPEND_LOG(f"create_work_order çağırıldı, şasi no : {sasi_no}\n")

    if not sasi_no or not sasi_no.strip():
        error = "İş emri oluşturulamadı: şasi numarası boş olamaz"
        APPEND_LOG(f"create_work_order Hata! : {error}\n")
        return error

    if not aciklama or not aciklama.strip():
        error = "İş emri oluşturulamadı: iş emri açıklaması boş olamaz"
        APPEND_LOG(f"create_work_order Hata! : {error}\n")
        return error

    postgres_dbname = os.getenv("POSTGRES_DATABASE_NAME", "AnadoluIsuzuDB")
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")

    with psycopg.connect(
        f"dbname={postgres_dbname} host={postgres_host} port={postgres_port}"
    ) as connection:
        with connection.cursor() as cursor:
            while True:
                rand_id = random.randint(0, 999999999)
                # POTANSIYEL OLARAK SONSUZ DONGUYE GIREBILIR, BUNU ONLEMEK ICIN BASKA BIR SAFEGUARD ILERDE EKLENEBILIR
                cursor.execute(
                    """
                    INSERT INTO work_orders (work_order_id, vin, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (work_order_id) DO NOTHING
                    RETURNING work_order_id
                    """,
                    (rand_id, sasi_no, aciklama),
                )

                if cursor.fetchone() is not None:
                    APPEND_LOG(
                        f"create_work_order başarılı, iş emri no : {rand_id}, şasi no : {sasi_no}\n"
                    )
                    return f"{rand_id} numaralı iş emri oluşturuldu"

@mcp.tool()
async def get_error_code_info(errcode: str, arac_modeli: str | None = None) -> str:
    """
    Hata Kodu ve opsiyonel olarak araç modeli verilen aracın hata kodu ile ilgili bilgiyi sunucudan getirir.

    Args:
        errcode: Aracın hata kodu
        arac_modeli: Aracın modeli

    """
    APPEND_LOG(
        f"get_error_code_info çağırıldı, hata kodu: {errcode}, model: {arac_modeli}\n"
    )

    if not isinstance(errcode, str):
        return "Hata kodu metin olarak gönderilmelidir."

    errcode = re.sub(r"[\s_-]+", "", errcode)
    if not errcode:
        return "Hata kodu boş olamaz."

    postgres_dbname = os.getenv("POSTGRES_DATABASE_NAME", "AnadoluIsuzuDB")
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")

    if arac_modeli:
        query_str = """
            SELECT error_explanation
            FROM error_codes
            WHERE error_code = %s AND car_model = %s
        """
        arac_modeli = arac_modeli.replace("_",' ')
    else:
        query_str = """
            SELECT error_explanation
            FROM error_codes
            WHERE error_code = %s
        """
    with psycopg.connect(
        f"dbname={postgres_dbname} host={postgres_host} port={postgres_port}"
    ) as connection:
        with connection.cursor() as cursor:
            if arac_modeli:
                cursor.execute(query_str, (errcode, arac_modeli))
            else:
                cursor.execute(query_str, (errcode,))

            result = cursor.fetchone()

    if result is not None:
        APPEND_LOG(f"get_error_code_info başarılı, alınan metin: {result[0]}\n")
        return result[0]

    not_found = f"{errcode} hata kodu için kayıt bulunamadı."
    if arac_modeli:
        not_found = f"{arac_modeli} modeli için {errcode} hata kodu bulunamadı."
    APPEND_LOG(f"get_error_code_info Hata!: {not_found}\n")
    return not_found

@mcp.tool()
async def escalate_live_chat(chat_summary: str) -> str:
    """
    Eğer kullanıcı aldığı yanıtları beğenmezse bu fonksiyonu çağırarak sohbeti canlı desteklere ilet.

    Args:
        chat_summary: Kullanıcının yaşadığı problemin özeti
    """
    APPEND_LOG(f"escalate_live_chat çağırıldı, özet : {chat_summary}\n")

    if not chat_summary or not chat_summary.strip():
        error = "Canlı destek escalation başlatılamadı: sohbet özeti boş olamaz"
        APPEND_LOG(f"escalate_live_chat Hata! : {error}\n")
        return error

    user_id = uuid.uuid4()
    api_url = fastapi_server_url + "/escalate"
    payload = EscalateRequest(
        runtime_user_id=str(user_id), summary=chat_summary
    ).model_dump()

    try:
        result = requests.post(api_url, json=payload, timeout=10)
        result.raise_for_status()

        result_data = result.json()
        assigned = result_data["assigned"]

        if not assigned:
            error = "Teknik eleman bulunamadı!"
            APPEND_LOG(f"escalate_live_chat Hata! : {error}\n")
            return error

        session_id = result_data["session_id"]

        APPEND_LOG(
            f"/escalate başarılı, kullanıcı id : {user_id}, status : {result.status_code}, session_id : {session_id}\n"
        )

        # chat_summary' nin sistem mesajı olarak atılması:
        chat_summary = "SİSTEM: KULLANICININ YAŞADIĞI PROBLEMİN ÖZETİ: " + chat_summary
        try:
            send_message_url = fastapi_server_url + f"/sessions/{session_id}/messages"
            send_message_payload = SendMessageRequest(
                sender_role="system", message_text=chat_summary
            ).model_dump()

            send_message_result = requests.post(
                send_message_url, json=send_message_payload, timeout=10
            )
            send_message_result.raise_for_status()
        except requests.RequestException as exc:
            error = f"Sohbet özeti gönderilemedi, {exc}"
            APPEND_LOG(f"escalate_live_chat Hata! : {error}\n")
            return error

        # ESCALATE SONRASI SİSTEMİ AÇMAK LAZIM BURAYA YA DA BAŞKA YERE KOYARIM

        return json.dumps(
            {
                "status": "started",
                "session_id": str(session_id),
            },
            ensure_ascii=False,
        )
    except requests.RequestException as exc:
        error = f"Canlı destek escalation başarısız oldu: {exc}"
        APPEND_LOG(f"escalate_live_chat Hata! : {error}\n")
        return error


# OLLAMA İÇİN LAZIM BUNLAR
MCP_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_warranty_status",
            "description": "Şasi numarası verilen aracın  garanti bilgilerini sunucudan getir.",
            "parameters": {
                "type": "object",
                "properties": {"sasi_no": {"type": "string"}},
                "required": ["sasi_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_part_stock",
            "description": "Parça numarası verilen yedek parçanın bilgilerini sunucudan getir.",
            "parameters": {
                "type": "object",
                "properties": {"parca_kodu": {"type": "string"}},
                "required": ["parca_kodu"],
            },
        },
    },    
    {
        "type": "function",
        "function": {
            "name": "get_error_code_info",
            "description": "Hata Kodu ve opsiyonel olarak araç modeli verilen aracın hata kodu ile ilgili bilgiyi sunucudan getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "errcode": {"type": "string"},
                    "arac_modeli": {"type": ["string", "null"]},
                },
                "required": ["errcode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_live_chat",
            "description": "Eğer kullanıcı aldığı yanıtları beğenmezse bu fonksiyonu çağırarak sohbeti canlı desteklere ilet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_summary": {
                        "type": "string",
                        "description": "LLM tarafından üretilen, kullanıcının istediği şeyleri içeren sohbet özeti.",
                    }
                },
                "required": ["chat_summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_work_order",
            "description": "Şasi numarası verilen araç için sunucuda iş emri açma.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sasi_no": {"type": "string"},
                    "aciklama": {"type": "string"},
                },
                "required": ["sasi_no", "aciklama"],
            },
        },
    },
]


if __name__ == "__main__":
    mcp.run(transport="stdio")
