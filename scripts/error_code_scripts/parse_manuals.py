from pathlib import Path
from dotenv import load_dotenv
import os
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from libs.file_path_finder import find_file_paths

load_dotenv()
data_path = Path(os.getenv("DATA_PATH", str(PROJECT_ROOT / "data")))
if not data_path.is_absolute():
    data_path = PROJECT_ROOT / data_path


class Error_Code_Class:
    ERROR_CODE: str
    CAR_TYPE: str
    DETAILS: str

    def __init__(self, errcode: str, cartype: str, details: str):
        self.ERROR_CODE = errcode
        self.CAR_TYPE = cartype
        self.DETAILS = details

    def print_info(self):
        print(
            f"Hata Kodu : {self.ERROR_CODE}\n"
            f"Araç Modeli: {self.CAR_TYPE}\n"
            f"Açıklama  : {self.DETAILS.strip()}"
        )


def get_error_information(
    data_path: str = os.getenv("DATA_PATH", str(PROJECT_ROOT / "data"))
):
    """
    İŞLEYİŞ AKIŞI:
    1) "## E" ile başlayan satır tespit edilir.
    2) O satırdan hata kodu ayıklanır.Ayıklanan kod error_code'a atanır.
    3) Bir sonraki "## E" başlayana kadar diğer satırlar error_body'e atanır.
    4) "## E" tekrardan tespit edildiğinde, error body'e atanan değerler tek cümle haline getirilir, list_to_return'e eklenir, error body temizlenir, yeni hata kodu alınır ve döngü yeniden devam eder.
    4-A) Eğer "###" tespit edilir ise bu hata kodlarının bittiğini gösterir, okunan md dosyasından çıkılır ve sonraki md dosyası okunmaya başlanır.
    """

    md_paths = find_file_paths(str(data_path), "md")
    list_to_return = []

    for md_path in md_paths:

        path = Path(md_path)
        car_model = path.parent.name.replace("_", " ")
        error_code: str
        error_body = []
        append_flag = False

        with path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.rstrip("\n")
                if (
                    line.lstrip().startswith("## E")
                    or line.lstrip().startswith("### E")
                    or re.match(
                        r"^\s*###\s*[A-Za-z](?=[A-Za-z0-9]*\d)[A-Za-z0-9]*",
                        line,
                    )
                ):
                    match = re.match(r"^\s*##\s*(E\s*\d+)", line)
                    if not match:
                        match = re.match(
                            r"^\s*###\s*([A-Za-z](?=[A-Za-z0-9]*\d)[A-Za-z0-9]*)",
                            line,
                        )
                    if not match:
                        match = re.match(
                            r"^\s*###\s*([A-Za-z]\s*\d{3,4})", line
                        )
                    if match:
                        if append_flag and error_body:
                            error_body_concat = ""
                            for elem in error_body:
                                elem = elem.replace("#", "").replace("*", "")
                                error_body_concat += elem
                            element = Error_Code_Class(
                                error_code, car_model, error_body_concat
                            )
                            list_to_return.append(element)
                            error_body = []

                        error_code = re.sub(r"\s+", "", match.group(1))
                        append_flag = True

                if line.lstrip().startswith("####") or re.match(
                    r"^\s*##\s*\d+\.", line
                ):
                    append_flag = False

                if append_flag:
                    error_body.append(line)

    return list_to_return
