from qdrant_client import QdrantClient
from qdrant_client.models import (
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
    FieldCondition,
    MatchValue,
)
from libs.tools import get_dense_embedding, get_sparse_embedding


qdrant_client = QdrantClient(url="http://localhost:6334", timeout=60, prefer_grpc=True)
collection_name = "car_data"



query_text ="E 45 numaralı hata kodu nedir"

arac_modeli_filtresi = "CITIPORT"
veri_tipi_filtresi = None

filter_conditions = []
if arac_modeli_filtresi is not None:
    filter_conditions.append(
        FieldCondition(
            key="arac_modeli",
            match=MatchValue(value=arac_modeli_filtresi),
        )
    )
if veri_tipi_filtresi is not None:
    filter_conditions.append(
        FieldCondition(
            key="veri_tipi",
            match=MatchValue(value=veri_tipi_filtresi),
        )
    )

query_filter = Filter(must=filter_conditions) if filter_conditions else None

print(f"'{query_text}' için embedding oluşturuluyor...")

nomic_dense_vector = get_dense_embedding(query_text)
qdrant_sparse_vector = get_sparse_embedding(query_text)


print("Qdrant'ta en yakın sonuçlar aranıyor...")
# HİBRİT
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
        )
    ],
    # Combine the prefetch lists using Reciprocal Rank Fusion (RRF)
    query=FusionQuery(
        fusion=Fusion.DBSF
    ),
    limit=3
)

"""
# SADECE  DENSE
search_results = qdrant_client.query_points(
    collection_name=collection_name,
    query=nomic_dense_vector,
    using="markdown_dense_vector",
    limit=3,  # En yüksek skorlu ilk 3 eşleşmeyi getir
    with_payload=True  # Payload'ı (metni ve metadata'yı) getirmesini zorunlu kılıyoruz
)
"""


# 5. Sonuçları ekrana yazdır
if search_results.points:
    for i, hit in enumerate(search_results.points):
        print("------------------------------------------------------------------------------------")
        print(f"SONUÇ {i+1} | Benzerlik Skoru: {hit.score:.4f}")
        print("------------------------------------------------------------------------------------")
        
        payload = hit.payload
        
        print("Dosya:", payload.get("kaynak_dosya", payload.get("source_file", "Bilinmiyor")))
        
        print("\n--- METİN ---")
        text_to_show = payload.get("window_context", payload.get("text", "Metin bulunamadı"))
        print(text_to_show)
        print(payload)
else:
    print("Hiç sonuç bulunamadı.")




