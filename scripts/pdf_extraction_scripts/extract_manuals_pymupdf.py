import torch
import os
import glob
import traceback
import pymupdf4llm  # docling yerine eklendi
from ollama import chat
from qdrant_client import QdrantClient

def pdf_to_markdown_pymupdf(pdf_dir_path, output_dir=None):
    if not os.path.exists(pdf_dir_path):
        print(f"Hata: '{pdf_dir_path}' bulunamadı.")
        return

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        print("Belge dönüştürücü başlatılıyor (PyMuPDF4LLM ile)...")

        search_pattern = os.path.join(pdf_dir_path, "**", "*.pdf")
        pdf_files = glob.glob(search_pattern, recursive=True)

        if not pdf_files:
            print("Belirtilen dizinde hiç PDF dosyası bulunamadı.")
            return

        print(f"Toplam {len(pdf_files)} PDF bulundu. İşlem başlıyor...\n")

        for pdf_file in pdf_files:
            print(f"İşleniyor: {pdf_file}")

            # PyMuPDF4LLM ile PDF dosyasını doğrudan Markdown formatına çeviriyoruz
            md_text = pymupdf4llm.to_markdown(pdf_file)

            base_name = os.path.splitext(os.path.basename(pdf_file))[0]
            yeni_dosya_adi = f"{base_name}_SERVIS_KILAVUZU.md"

            if output_dir:
                output_md_path = os.path.join(output_dir, yeni_dosya_adi)
            else:
                file_dir = os.path.dirname(pdf_file)
                output_md_path = os.path.join(file_dir, yeni_dosya_adi)

            with open(output_md_path, 'w', encoding='utf-8') as md_file:
                md_file.write(md_text)
                
            print(f"✅ Başarılı! Oluşturuldu: {output_md_path}\n")

    except Exception as e:
        print("❌ Bir hata oluştu! Detaylı hata raporu:")
        traceback.print_exc()

if __name__ == "__main__":

    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")


    # Check GPU memory
    if torch.cuda.is_available():
        print(f"GPU Memory allocated: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
        print(f"GPU Memory reserved: {torch.cuda.memory_reserved(0) / 1024**3:.2f} GB")


    girdi_pdf_dizini = "/home/flkr/Desktop/Isuzu_Embed_Proje/user_manual_pdfs/user_manuals/"
    
    cikti_md_dizini = "/home/flkr/Desktop/Isuzu_Embed_Proje/markdown_outputs_pymupdf/"
    
    # Güncellenmiş fonksiyon çağrısı
    pdf_to_markdown_pymupdf(girdi_pdf_dizini, cikti_md_dizini)