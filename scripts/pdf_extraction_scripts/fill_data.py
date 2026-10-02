import os
import json
import random
import string
import copy
from datetime import datetime, timedelta

def harfleri_rastgelelestir(veri):
    islem_tipleri = ["K", "D", "A", "Y",None] # Kontrol, Değişim, Ayar, "Yağlama"
    
    if isinstance(veri, list):
        for eleman in veri:
            harfleri_rastgelelestir(eleman)
    elif isinstance(veri, dict):
        for anahtar, deger in veri.items():
            if anahtar == "bakim_km" and isinstance(deger, dict) and deger:
                for km in deger.keys():
                    deger[km] = random.choice(islem_tipleri)
            else:
                harfleri_rastgelelestir(deger)

def generate_vin():
    chars = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"
    return "".join(random.choice(chars) for _ in range(17))

def generate_part_code():
    return f"{random.choice(string.ascii_uppercase)}{random.randint(1,9)}{random.choice(string.ascii_uppercase)}{random.randint(1000,9999)}{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}"

arac_listesi = [
    "BIG-E", "CITIBUS", 
    "CITIVOLT", "CITIPORT", 
    "D-MAX", "ELF-2600", 
    "GRAND_NOVO", "GRAND_NOVOULTRA", 
    "GRAND_TORO", "INTERLINER", 
    "KENDO", "NOVO_NOVOLUX",
    "NOVOCITI_LIFE", "NOVOCITY_VOLT",
    "TURKUAZ","VISIGO"
]

with open("CITIBUS_BAKIM_PLANI.json", "r", encoding="utf-8") as f:
    bakim_periyotlari_template = json.load(f)

with open("CITIBUS_SERVIS_KILAVUZU.md", "r", encoding="utf-8") as f:
    md_template = f.read()

parca_isimleri = ["On-Fren-Diski", "Yag-Filtresi", "Hava-Filtresi", "Motor-Yagi-5W30", "Silecek-Takimi", "DPF-Filtresi", "Fren-Balatasi", "Amortisor", "Mars-Motoru", "Aku-24V", "Enjektor-Takimi", "Su-Pompasi", "V-Kayisi"]

os.makedirs("arac_verileri", exist_ok=True)
start_date = datetime.now() - timedelta(days=1825) # 5 yıl önce

for arac in arac_listesi:

    arac_bilgisi = []
    for _ in range(random.randint(5, 10)):
        rastgele_gun = random.randint(0, 1800)
        satis_tarihi = start_date + timedelta(days=rastgele_gun)
        garanti_bitis = satis_tarihi + timedelta(days=365*5)
        arac_bilgisi.append({
        "arac_modeli": arac,
        "sasi_no": generate_vin(),
        "satis_tarihi": satis_tarihi.strftime("%d/%m/%Y"),
        "garanti_bitis": garanti_bitis.strftime("%d/%m/%Y"),
        "km_limiti": str(random.choice([1000000, 1500000, 2000000]))
        })

    # WEAKPOINT CHECK FOR ERROR 
    yedek_parcalar = []
    for names in parca_isimleri:
        yedek_parcalar.append({
            "kod": generate_part_code(),
            "ad": names,
            "fiyat_tl": str(random.randint(500, 15000)),
            "stok_adedi": str(random.randint(0, 500))
        })

    arac_bakim_plani = copy.deepcopy(bakim_periyotlari_template)
     
    
    harfleri_rastgelelestir(arac_bakim_plani)
    
    dosya_adi_koku = arac.replace(" ", "_").upper()
    
    with open(f"arac_verileri/{dosya_adi_koku}_GARANTI_KAYITLARI.json", "w", encoding="utf-8") as f:
        json.dump(arac_bilgisi, f, ensure_ascii=False, indent=4)
        
    with open(f"arac_verileri/{dosya_adi_koku}_PARCA_KATALOGU.json", "w", encoding="utf-8") as f:
        json.dump(yedek_parcalar, f, ensure_ascii=False, indent=4)
    
    with open(f"arac_verileri/{dosya_adi_koku}_BAKIM_PLANI.json", "w", encoding="utf-8") as f:
        json.dump(arac_bakim_plani, f, ensure_ascii=False, indent=4)
        
    md_content = md_template.replace("{arac_adi}", arac.upper())
    with open(f"arac_verileri/{dosya_adi_koku}_SERVIS_KILAVUZU.md", "w", encoding="utf-8") as f:
        f.write(md_content)

print("İşlem tamam!")