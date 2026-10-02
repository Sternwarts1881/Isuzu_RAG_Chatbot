import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

from ollama import Client
from qdrant_client import QdrantClient
from . import tools
from mcp_client import call_mcp_tool
from mcp_server import MCP_TOOL_SCHEMAS
import json

ollama_client = Client(
    host=os.getenv("OLLAMA_HOST", "http://localhost:11434")
)

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6334"),
    timeout=60,
    prefer_grpc=True,
    check_compatibility=False,
)

collection_name = os.getenv("QDRANT_COLLECTION_NAME", "car_data")
embedding_model = os.getenv("DENSE_EMBEDDING_MODEL", "nomic-embed-text-v2-moe")
data_path = os.getenv("DATA_PATH", "data")

MCP_FUNCTION_NAMES = {
    schema["function"]["name"]
    for schema in MCP_TOOL_SCHEMAS
}

def icerik_cikar(icerik):
    if isinstance(icerik, str):
        return icerik
    if isinstance(icerik, list):
        return " ".join(
            item.get("text", "") for item in icerik if isinstance(item, dict)
        )
    return str(icerik) if icerik is not None else ""


def chat_agent(user_message, history):
    qwen_model = "qwen3.5:9b"

    sistem_bilgisi = f"""
        Sen, Anadolu Isuzu araçları hakkında bilgi veren ve atölyedeki İŞÇİ/USTALARA yardımcı olan uzman bir teknik asistansın.
        Kullanıcı sorularını yanıtlamak için sana sağlanan fonksiyonları (tools) kullanman ZORUNLUDUR.

        # ARAÇLAR (TOOLS) VE KULLANIM ÖNCELİKLERİ
        Kullanıcının isteğini yerine getirmek için MÜMKÜN OLDUĞUNDA öncelikle aşağıdaki 6 özel fonksiyonu kullanmalısın. Eğer kullanıcının talebi bu araçlarla elde edilemiyorsa (örneğin tamir adımları, teknik kılavuz bilgisi veya hata kodu çözümü gerektiriyorsa) o zaman "hybrid_query" fonksiyonunu kullan.

        1. get_warranty_status(sasi_no): Kullanıcı bir aracın garanti durumunu sorduğunda KESİNLİKLE bu fonksiyonu kullan. (Şasi numarası 17 karakter uzunluğundadır).
        2. check_part_stock(parca_kodu): Kullanıcı belirli bir yedek parçanın durumunu, bilgisini veya stokta olup olmadığını sorduğunda KESİNLİKLE bu fonksiyonu kullan.
        3. create_work_order(sasi_no, aciklama): Kullanıcı bir araç için iş emri (iş kaydı) açmak/oluşturmak istediğinde KESİNLİKLE bu fonksiyonu kullan. İşlemin detayını 'aciklama' parametresine ekle.
        4. get_error_code_info(errcode,arac_modeli): Kullanıcı bir arabada aldığı hata kodu hakkında bilgi ister ise KESİNLİKLE bu fonksiyonu kullan. Eğer aracın modeli var ise arac_modeli'ne ekle, opsiyonel. Eğer filtre eklediğinde bulamazsa araç filtresiz aramayı dene.
        5. escalate_live_chat(chat_summary): Kullanıcı aldığı yanıtları BEĞENMEZ İSE ve bunu belirtirse, bu fonksiyonu KESİNLİKLE çağır.
        6. hybrid_query(query_text, arac_modeli_filtresi): Kullanıcının sorusu yukarıdaki 5 işlem ile çözülemiyorsa Qdrant sunucusuna hibrit arama (hybrid search) yapmak için bu fonksiyonu kullan.

        # HEDEF KİTLE VE ÇIKTI FORMATI (ÇOK ÖNEMLİ)
        1. KULLANICI KİTLESİ: Bu sistemi kullanan kişiler atölyedeki ustalar ve teknisyenlerdir. Yanıtların her zaman onların kolayca okuyabileceği, net, anlaşılır ve sade bir Türkçe ile yazılmalıdır.
        2. JSON VE KOD YASAK: Ekrana KESİNLİKLE JSON verisi, süslü parantezler, kod blokları, tool parametreleri veya ham veritabanı çıktıları YANSITMA. Arka planda tool'dan gelen veriyi sadece oku ve doğal insan diline çevirerek (düz metin olarak) cevap ver.
        3. DOĞRUDAN YANIT VER: "Belgelerde bu bilgi mevcut", "İşte aradığınız veriler", "Sorgu sonucunda şunlar bulundu" gibi gereksiz giriş cümleleri kurma. Usta "Yağ değişimi nasıl yapılır?" diye soruyorsa, doğrudan 1. adım, 2. adım şeklinde işlemleri listele. "Garanti var mı?" diyorsa direkt garanti sonucunu söyle. Lafı uzatma.
        4. SADECE EŞLEŞEN BİLGİLER: Örneğin hata kodu anlamı veya parça değişim aşamaları soruluyorsa sadece belirtilen konu ile ilgili bilgileri getir, başka hata kodları, tablolar gibi şeyleri kullanma, tamamen eşleşen bilgiler en öncelikli.

        # HİBRİT ARAMA (HYBRID QUERY), get_error_code_info VE FİLTRELEME MANTIĞI
        Filtre kullanırken `arac_modeli_filtresi` parametresi YALNIZCA tek bir string değer alabilir. Boolean, dict veya liste GÖNDERİLEMEZ.

        Geçerli Araç Modelleri:
        BIG-E, CITIBUS, CITIPORT, CITIVOLT, D-MAX, ELF-2600, GRAND_NOVO, NOVO_NOVOLUX, NOVOCITI_LIFE, NOVOCITI_VOLT, TURKUAZ, VISIGO, INTERLINER, KENDO, GRAND_TORO

        Doğru format örneği: "query_text": "yağ değişimi", "arac_modeli_filtresi": "CITIVOLT"
        Yanlış format örneği: "CITIVOLT": 1, "BIG-E": 0

        - Model Belirtilmişse: Kullanıcı mesajında yukarıdaki modellerden biri geçiyorsa KESİNLİKLE o modeli filtre olarak kullan.
        - Model Belirtilmemişse: Kullanıcıya "Hangi araç?" diye sorma. KESİNLİKLE filtreye `null` göndererek genel arama yap.

        # VERİ İŞLEME VE GÜVENİLİRLİK
        1. SONUÇLARI EŞLEŞME PUANINA GÖRE İNCELE (Qdrant Aramalarında): Sonuçları skor sırasına göre incele. Ancak kullanıcının sorduğu spesifik terim (hata kodu, parça adı vb.) hangi sonuçta birebir geçiyorsa, skor sırası ne olursa olsun o sonucu kullan. Örneğin kullanıcı 200 numaralı hata kodunu soruyorsa sadece o kodun bilgisini getir.
        2. HALÜSİNASYON YASAK: Tool'lardan veya dökümanlardan gelen yanıtlarda istenen bilgi yoksa, kendi veritabanından bilgi uydurma. Sadece sana sunulan araçlara ve Isuzu dökümanlarına sadık kal. Bilgi yoksa "Bu konuda sistemde veya dökümanlarda bilgi bulunamadı" de.

        # BAKIM KISALTMALARI
        K: Gerektiğinde kontrol, temizlik, düzeltme 
        D: Değiştiriniz 
        A: Ayarlayınız 
        Y: Yağlayınız
    """
    raw_messages = [{"role": "system", "content": sistem_bilgisi}]

    for msg in history:
        raw_messages.append(
            {"role": msg.get("role", "user"), "content": msg.get("content", "")}
        )

    raw_messages.append({"role": "user", "content": user_message})

    final_messages = []
    for m in raw_messages:
        final_messages.append(
            {
                "role": m["role"],
                "content": icerik_cikar(m.get("content", "")),
            }
        )

    """
    final_messages.append(
        {
            "role": "tool",
            "content": str(tools.hybrid_query(user_message)),
            "name": "hybrid_query",
        }
    )
    """

    max_adim = 40
    adim_sayisi = 0
    session_id = None

    tool_definitions = [
        {
            "type": "function",
            "function": {
                "name": "hybrid_query",
                "description": "Qdrant sunucusunda arama yapıp ilgili sonuçları getirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_text": {"type": "string"},
                        "arac_modeli_filtresi": {
                            "type": ["string", "null"],
                            "description": "İsteğe bağlı araç modeli filtresi. Örnek: CITIVOLT",
                        },
                    },
                    "required": ["query_text"],
                },
            },
        }
    ] + MCP_TOOL_SCHEMAS
    while adim_sayisi < max_adim:
        response = ollama_client.chat(
            model=qwen_model,
            messages=final_messages,
            tools=tool_definitions,
            options={'temperature': 0.0}
        )

        if not response.message.tool_calls:
            content = response.message.content or ""
            if content:
                return content, session_id
            return "Yanıt oluşturulamadı. Lütfen soruyu tekrar deneyin.", session_id

        final_messages.append(response.message)

        for tool_call in response.message.tool_calls:
            fonksiyon_adi = tool_call.function.name
            argumanlar = tool_call.function.arguments

            if fonksiyon_adi == "hybrid_query":
                if not isinstance(argumanlar, dict):
                    fonksiyon_ciktisi = "Tool argümanları geçerli JSON objesi değil."
                elif not isinstance(argumanlar.get("query_text"), str):
                    fonksiyon_ciktisi = "query_text string olmalıdır."
                elif (
                    "arac_modeli_filtresi" in argumanlar
                    and argumanlar["arac_modeli_filtresi"] is not None
                    and not isinstance(argumanlar["arac_modeli_filtresi"], str)
                ):
                    fonksiyon_ciktisi = (
                        "arac_modeli_filtresi tek bir model adı olarak string gönderilmelidir; "
                        "obje veya 0/1 listesi gönderilemez."
                    )
                else:
                    fonksiyon_ciktisi = tools.hybrid_query(**argumanlar)
            elif fonksiyon_adi == "escalate_live_chat":
                fonksiyon_ciktisi = call_mcp_tool(fonksiyon_adi, argumanlar)
                tools.APPEND_LOG(f"ÇIKTI : {fonksiyon_ciktisi}\n")
                try:
                    escalation_result = json.loads(fonksiyon_ciktisi)
                    session_id = escalation_result.get("session_id")
                    return ("Canlı Sohbete geçiş yapılıyor", session_id)
                except (json.JSONDecodeError, TypeError):
                    tools.APPEND_LOG("type error\n")
                    session_id = None
            elif fonksiyon_adi in MCP_FUNCTION_NAMES:
                fonksiyon_ciktisi = call_mcp_tool(fonksiyon_adi, argumanlar)
            else:
                fonksiyon_ciktisi = f"Hata: {fonksiyon_adi} adında bir araç yok."

            final_messages.append(
                {
                    "role": "tool",
                    "content": str(fonksiyon_ciktisi),
                    "name": fonksiyon_adi,
                }
            )
        adim_sayisi += 1

    return (
        "Üzgünüm, işlemi tamamlamak için çok fazla alt adım gerektiği için durduruldu.",
        session_id,
    )
