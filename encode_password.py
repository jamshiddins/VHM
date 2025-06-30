from urllib.parse import quote_plus

password = "Shx5WM+#8Sh4uUq"
encoded_password = quote_plus(password)
print(f"Исходный пароль: {password}")
print(f"Закодированный: {encoded_password}")
print(f"Используйте в DATABASE_URL: postgresql://postgres.xuvdzxcafmrcmojicpgi:{encoded_password}@aws-0-eu-central-1.pooler.supabase.com:6543/postgres")
