import re
import sys
import uuid
from io import BytesIO
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from libs import file_path_finder
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from libs.tools import get_dense_embedding, get_sparse_embedding
from transformers import AutoTokenizer
from chonkie import SemanticChunker
from chonkie.embeddings import BaseEmbeddings
from markdown_chunker import MarkdownChunkingStrategy
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.types.io import DocumentStream

COLLECTION_NAME = "car_data"
DATA_PATH = "data"
EMBEDDING_MODEL = "nomic-embed-text-v2-moe"
qdrant_client = QdrantClient(
    url="http://localhost:6334",
    timeout=60,
    prefer_grpc=True,
)
def _upload_chunks(
    chunks: Iterable[str],
    data_path: str | Path,
) -> int:
    path = Path(data_path)
    model_name = path.parent.name
    chunks = list(chunks)
    points = []
    window_size = 1

    for chunk_index, chunk in enumerate(chunks):
        chunk_text = str(getattr(chunk, "text", chunk)).strip()
        if not chunk_text:
            continue

        start_index = max(0, chunk_index - window_size)
        end_index = min(len(chunks), chunk_index + window_size + 1)
        context = "\n\n".join(
            str(getattr(chunks[index], "text", chunks[index]))
            for index in range(start_index, end_index)
        )

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "markdown_dense_vector": get_dense_embedding(chunk_text),
                    "json_sparse_vector": get_sparse_embedding(chunk_text),
                },
                payload={
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "window_context": context,
                    "kaynak_dosya": str(path),
                    "arac_modeli": model_name,
                    "veri_tipi": "servis_kılavuzu",
                },
            )
        )

    if points:
        qdrant_client.upload_points(
            collection_name=COLLECTION_NAME,
            points=points,
            batch_size=50,
            wait=True,
        )

    print(f"{len(points)} chunk {COLLECTION_NAME} koleksiyonuna yüklendi: {path}")
    return len(points)


def structural_chunking(data_path: str | Path) -> int:
    """Split a Markdown file structurally, embed its chunks, and upload them."""
    path = Path(data_path)
    with path.open("r", encoding="utf-8") as file:
        content = file.read()

    fixed_text = re.sub(
        r"^##\s*(Arıza Giderilmesi.*)",
        r"### \1",
        content,
        flags=re.MULTILINE,
    )
    strategy = MarkdownChunkingStrategy(add_metadata=False,parallel_processing=True,max_workers=None)
    chunks = strategy.chunk_markdown(fixed_text)
    for chunk in chunks:
        print("------------------------------------------------------------------------------------------------------------------------")
        print(chunk)
    return _upload_chunks(chunks, path)


class _OllamaEmbedder(BaseEmbeddings):
    def __init__(self, model_name: str, embed_dimension: int = 768):
        super().__init__()
        self.model_name = model_name
        self._dimension = embed_dimension
        self.tokenizer = AutoTokenizer.from_pretrained(
            "dbmdz/bert-base-turkish-cased",
            model_max_length=8192
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    def get_tokenizer(self):
        return self.tokenizer

    def embed(self, text: str) -> np.ndarray:
        return np.asarray(get_dense_embedding(text))

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        return [np.asarray(get_dense_embedding(text)) for text in texts]


def semantic_chunking(data_path: str | Path) -> int:
    """Split a Markdown file semantically, embed its chunks, and upload them."""
    path = Path(data_path)
    with path.open("r", encoding="utf-8") as file:
        content = file.read()
        fixed_text = re.sub(
        r"^##\s*(Arıza Giderilmesi.*)",
        r"### \1",
        content,
        flags=re.MULTILINE,
    )

    semantic_chunker = SemanticChunker(
        embedding_model=_OllamaEmbedder(EMBEDDING_MODEL),
        chunk_size=400,
        threshold=0.7,
        similarity_window=10,
        skip_window=1,
        min_sentences_per_chunk=5,
    )
    chunks = semantic_chunker.chunk(fixed_text)
    for chunk in chunks:
        print("------------------------------------------------------------------------------------------------------------------------")
        print(chunk.text)
    return _upload_chunks(chunks, path)


def hybrid_chunking(data_path: str | Path) -> int:
    """Split a document with Docling HybridChunker, embed it, and upload it."""
    path = Path(data_path)
    with path.open("r", encoding="utf-8") as file:
        markdown = file.read()

    # Docling's Markdown backend can fail while restoring HTML comment blocks.
    markdown = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    document_stream = DocumentStream(
        name=path.name,
        stream=BytesIO(markdown.encode("utf-8")),
    )
    document = DocumentConverter().convert(source=document_stream).document

    tokenizer = HuggingFaceTokenizer(
        tokenizer=AutoTokenizer.from_pretrained(
            "dbmdz/bert-base-turkish-cased",
            model_max_length=8192,
        ),
        max_tokens=8192,
    )
    chunker = HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,
    )
    chunks = list(chunker.chunk(dl_doc=document))
    contextualized_chunks = [
        chunker.contextualize(chunk=chunk)
        for chunk in chunks
    ]

    
    for chunk in contextualized_chunks:
        print("-" * 120)
        print(chunk)
    
    return _upload_chunks(contextualized_chunks, path)




#--------------------------------------------------------

if __name__ == "__main__":
    car_paths = file_path_finder.find_file_paths(
        data_path=DATA_PATH,
        file_extention_to_find="md",
    )
    for paths in car_paths:
        print(f"İşleniyor: {paths}")
        structural_chunking(paths)



