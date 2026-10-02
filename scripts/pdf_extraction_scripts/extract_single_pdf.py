import json
import os
import traceback
from ollama import chat
from qdrant_client import QdrantClient
from docling.document_converter import DocumentConverter

def pdf_to_markdown_docling(pdf_path, output_md_path):
    if not os.path.exists(pdf_path):
        print(f"Hata: '{pdf_path}' bulunamadı.")
        return

    try:
        print("Belge analiz ediliyor (Tablolar ve düzen çıkarılıyor)...")
        converter = DocumentConverter()
        
        # PDF'i analiz et ve dönüştür
        result = converter.convert(pdf_path)
        
        # Sonucu Markdown formatında dışa aktar
        md_text = result.document.export_to_markdown()

        with open(output_md_path, 'w', encoding='utf-8') as md_file:
            md_file.write(md_text)
                
        print(f"✅ Başarılı! Tablolarla birlikte Markdown dosyası oluşturuldu: {output_md_path}")

    except Exception as e:
        print("❌ Bir hata oluştu! Detaylı hata raporu:")
        traceback.print_exc()

if __name__ == "__main__":
    girdi_pdf = "user_manual_pdfs/user_manuals/BIG-e_TR_R06.pdf"
    cikti_md = "sonuc.md"
    
    pdf_to_markdown_docling(girdi_pdf, cikti_md)

# print(qdrant_client.get_collections())
# print(response.message.content)