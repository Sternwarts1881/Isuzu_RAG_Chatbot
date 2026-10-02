import os
from dotenv import load_dotenv

load_dotenv()

from ollama import Client
from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient
from pathlib import Path
from qdrant_client.models import (
    SparseVector,
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
    FieldCondition,
    MatchValue,
)
from pathlib import Path
from typing import Literal
import json

ollama_client = Client(
    host=os.getenv("OLLAMA_HOST", "http://localhost:11434")
)

AracModeli = Literal[
    "BIG-E",
    "CITIBUS",
    "CITIPORT",
    "CITIVOLT",
    "D-MAX",
    "ELF-2600",
    "GRAND_NOVO",
    "GRAND_TORO",
    "INTERLINER",
    "KENDO",
    "NOVOCITI_LIFE",
    "NOVOCITI_VOLT",
    "NOVO_NOVOLUX",
    "TURKUAZ",
    "VISIGO",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "logs.txt"


def APPEND_LOG(text: str) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as logs_file:
        logs_file.write(text)

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6334"),
    timeout=60,
    prefer_grpc=True,
    check_compatibility=False,
)
collection_name = os.getenv("QDRANT_COLLECTION_NAME", "car_data")
embedding_model = os.getenv("DENSE_EMBEDDING_MODEL", "nomic-embed-text-v2-moe")
sparse_embedding_model = None
data_path = os.getenv("DATA_PATH", "data")


def _load_sparse_model():
    global sparse_embedding_model
    if sparse_embedding_model is None:
        sparse_embedding_model = BGEM3FlagModel(
            "BAAI/bge-m3", use_fp16=False, devices="cpu"
        )
    return sparse_embedding_model


def get_dense_embedding(text: str) -> list[float]:
    response = ollama_client.embed(model=embedding_model, input=text)

    if hasattr(response, "embeddings"):
        return response.embeddings[0]
    if isinstance(response, dict) and "embeddings" in response:
        return response["embeddings"][0]
    if isinstance(response, list):
        return response[0]
    return response


def get_sparse_embedding(text: str) -> SparseVector:
    sparse_output = _load_sparse_model().encode(
        text,
        return_dense=False,
        return_sparse=True,
        return_colbert_vecs=False,
        max_length=8192,
    )
    lexical_weights = sparse_output["lexical_weights"]
    if isinstance(lexical_weights, list):
        lexical_weights = lexical_weights[0]

    return SparseVector(
        indices=[int(index) for index in lexical_weights.keys()],
        values=[float(value) for value in lexical_weights.values()],
    )

def hybrid_query(
    query_text: str, arac_modeli_filtresi: AracModeli | None = None
) -> list[str] | None:
    APPEND_LOG(
        f"hybrid_query çağırıldı, query : {query_text}, filtreler: {arac_modeli_filtresi}\n"
    )
    # başka filtre türleri de ileride eklenebilir
    filter_conditions = []
    if arac_modeli_filtresi is not None:
        arac_modeli_filtresi = arac_modeli_filtresi.upper()
        try:
            path = Path(data_path)
            car_names = [car.name for car in path.iterdir() if car.is_dir()]
            # KABUL EDILEBILIR ISIMLER: BIG-E CITIBUS CITIPORT CITIVOLT D-MAX ELF-2600 GRAND_NOVO
            # NOVO_NOVOLUX NOVOCITI_LIFE NOVOCITI_VOLT TURKUAZ VISIGO INTERLINER KENDO GRAND_TORO
        except Exception as e:
            error = [
                "Araba isimleri bulunamadı, data klasörüne erişilemiyor. Kullanıcıyı bilgilendir."
            ]
            APPEND_LOG(f"hybrid_query Hata! : {error[0]}\n")
            return error
        if arac_modeli_filtresi not in car_names:
            error = [
                "Filtre için kullanılacak araç modeli ismi kullanılabilir isimlerde bulunamadı, query yeniden yapılmalı."
            ]
            APPEND_LOG(f"hybrid_query Hata! : {error[0]}\n")
            return error
        filter_conditions.append(
            FieldCondition(
                key="arac_modeli",
                match=MatchValue(value=arac_modeli_filtresi),
            )
        )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None

    try:
        nomic_dense_vector = get_dense_embedding(query_text)
    except Exception as e:
        error = [f"hyrid_query Hata!, Nomic ile dense embedding yapılamadı! : {e}"]
        APPEND_LOG(f"hybrid_query Hata! : {error[0]}\n")
        return error

    try:
        qdrant_sparse_vector = get_sparse_embedding(query_text)

    except Exception as e:
        error = [f"hyrid_query Hata!, BGE-M3 ile sparse embedding yapılamadı! : {e}"]
        APPEND_LOG(f"hybrid_query Hata! : {error[0]}\n")
        return error

    try:
        search_results = qdrant_client.query_points(
            collection_name=collection_name,
            prefetch=[
                Prefetch(
                    query=nomic_dense_vector,
                    using="markdown_dense_vector",
                    limit=20,
                    filter=query_filter,
                ),
                Prefetch(
                    query=qdrant_sparse_vector,
                    using="json_sparse_vector",
                    limit=20,
                    filter=query_filter,
                ),
            ],
            # RRF OR DBSF CAN BE USED
            query=FusionQuery(fusion=Fusion.DBSF),
            limit=3,
        )

    except Exception as e:
        error = [f"hyrid_query Hata!, Qdrant sunucusuna sorgu gönderilemedi! : {e}"]
        APPEND_LOG(f"hybrid_query Hata! : {error[0]}\n")
        return error

    if search_results.points:
        results = []
        for i, hit in enumerate(search_results.points):

            payload = hit.payload

            result = "-" * 10
            result = f"\n{'='*10} SORGU SONUCU {i+1} {'='*10}\n"
            result += f"ARAÇ MODELİ: {payload.get('arac_modeli','Bilinmiyor')}\n"
            result += f"BENZERLİK SKORU: {hit.score:.4f}\n"
            result += "METİN:\n"
            text_to_show = payload.get("window_context", payload.get("text", None))
            if text_to_show:
                result += str(text_to_show)
            else:
                result += json.dumps(payload, ensure_ascii=False, default=str)
            results.append(result)

        APPEND_LOG("hybrid_query Başarılı! :\n")
        for r in results:
            APPEND_LOG(f"{r}\n")
        return "\n\n".join(results)
    else:
        return ["Query sonucunda değerler bulunamadı."]
