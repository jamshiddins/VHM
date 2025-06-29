"""Initialize all models"""
import os
from pathlib import Path

# Получаем список всех файлов моделей
models_dir = Path(__file__).parent / "models"
model_files = [f.stem for f in models_dir.glob("*.py") if f.stem != "__init__"]

# Динамически импортируем все модели
for model_name in model_files:
    try:
        exec(f"from src.db.models.{model_name} import *")
    except ImportError:
        print(f"Warning: Could not import model {model_name}")