import uuid
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import json
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from libs import file_path_finder
from libs.tools import get_dense_embedding, get_sparse_embedding

qdrant_client = QdrantClient(url="http://localhost:6334", timeout=60, prefer_grpc=True)
collection_name = "car_data"
data_dir_path = "data"
data_paths = file_path_finder.find_file_paths(data_dir_path, "json")
points = []

def process_and_create_point(text, payload_data):
    nomic_dense_vector = get_dense_embedding(text)
    qdrant_sparse_vector = get_sparse_embedding(text)

    point = PointStruct(
        id=str(uuid.uuid4()), 
        vector={
            "markdown_dense_vector": nomic_dense_vector,
            "json_sparse_vector": qdrant_sparse_vector
        },
        payload=payload_data
    )
    return point


for path in data_paths:
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Hata: {path} geçerli bir JSON değil, atlanıyor.")
            continue

        doc_type = None

        if isinstance(data, list) and len(data) > 0 and "sasi_no" in data[0]:
            doc_type = "garanti"

        elif isinstance(data, dict):
            if "parca_katalogu" in data:
                doc_type = "parca"
            elif "bakım_planı" in data:
                doc_type = "bakim"

        if doc_type is None:
            raise TypeError("failiure in determining json file type")

        if doc_type == "parca":
            print(f"Tespiti Yapıldı: {path} -> PARCA KATALOGU")
            arac_modeli = data.get("arac_modeli", "Bilinmeyen Model")
            for item in data["parca_katalogu"]:
                text_to_embed = f"{arac_modeli} nin {item['kod']} numaralı {item['ad']} yedek parçası, fiyatı {item['fiyat_tl']} stok adedi {item['stok_adedi']} "
                payload = item.copy()
                payload["arac_modeli"] = arac_modeli
                payload["veri_tipi"] = "parca_katalogu"
                payload["kaynak_dosya"] = path
                
                pt = process_and_create_point(text_to_embed, payload)
                points.append(pt)

        elif doc_type == "garanti":
            print(f"Tespiti Yapıldı: {path} -> GARANTİ KAYITLARI")
            for item in data:
                text_to_embed = f"{item['arac_modeli']} model {item['sasi_no']} şasi numaralı aracın garanti kayırları, satış tarihi {item['satis_tarihi']} garanti bitisi {item['garanti_bitis']}, km limiti {item['km_limiti']}"
                payload = item.copy()
                payload["veri_tipi"] = "garanti_kaydi"
                payload["kaynak_dosya"] = path
                
                pt = process_and_create_point(text_to_embed, payload)
                points.append(pt)

        elif doc_type == "bakim":
            print(f"Tespiti Yapıldı: {path} -> BAKIM PLANI")
            arac_modeli = data.get("arac_modeli", "Bilinmeyen Model")
            for item in data["bakım_planı"]:
                km_metinleri = []
                for km, islem in item.get("bakim_km", {}).items():
                    if islem is not None:
                        km_metinleri.append(f"{km} KM'de işlem: {islem}")

                km_detayi_str = ", ".join(km_metinleri)
                text_to_embed = f"{arac_modeli} arac modelinin {item['kategori']} indeki {item['parca_sistem']} kontrol işlemleri: {km_detayi_str}"
                payload = item.copy()
                payload["arac_modeli"] = arac_modeli
                payload["veri_tipi"] = "bakim_plani"
                payload["kaynak_dosya"] = path
                
                pt = process_and_create_point(text_to_embed, payload)
                points.append(pt)

        else:
            print(f"Uyarı: {path} dosya yapısı tanınamadı. Bu dosya atlanıyor.")

print(f"\nToplam {len(points)} adet hibrit vektör hazırlandı. Qdrant'a yükleniyor...")

qdrant_client.upload_points(
    collection_name=collection_name,
    points=points,
    batch_size=50, 
    wait=True
)

print("Tum Json verileri yuklendi")