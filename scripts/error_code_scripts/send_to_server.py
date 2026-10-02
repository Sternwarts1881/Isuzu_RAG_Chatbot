from parse_manuals import Error_Code_Class, get_error_information
import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

try:
    list_to_upload = get_error_information()
except Exception as error:
    print(f"get_error_information'da hata yaşandı: {error}")
else:
    postgres_dbname = os.getenv("POSTGRES_DATABASE_NAME", "AnadoluIsuzuDB")
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")

    try:
        with psycopg.connect(
            f"dbname={postgres_dbname} host={postgres_host} port={postgres_port}"
        ) as connection:
            with connection.cursor() as cursor:
                for elements in list_to_upload:
                    cursor.execute(
                        """
                        INSERT INTO error_codes (error_code, car_model, error_explanation)
                        VALUES (%s, %s, %s)
                        """,
                        (elements.ERROR_CODE, elements.CAR_TYPE, elements.DETAILS),
                    )

        print("Operasyon Başarılı, Hata kodları sunucuya aktarıldı")
    except Exception as error:
        print(f"Sunucu bağlantısında hata : {error}")