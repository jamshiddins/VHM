import psycopg2
from urllib.parse import quote_plus

# Параметры подключения
host = "db.kyqmdazuzzynpcdbopjn.supabase.co"
database = "postgres"
user = "postgres"
password = "Shx5WM+#8Sh4uUq"
port = 5432

try:
    # Подключение
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port
    )
    
    cursor = conn.cursor()
    cursor.execute("SELECT version()")
    version = cursor.fetchone()
    print(f" Подключение успешно!")
    print(f"PostgreSQL версия: {version[0]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f" Ошибка: {e}")
