import os
from pathlib import Path
from typing import List, Dict, Any

class Config:
    """Конфигурация системы C4AI Architect"""
    
    # Пути
    BASE_DIR = Path(__file__).parent
    OUTPUT_DIR = BASE_DIR / "outputs"
    CACHE_DIR = BASE_DIR / ".cache"
    
    # Настройки LLM (Ollama)
    OLLAMA_BASE_URL = "http://localhost:11434"
    LLM_MODEL = "llama3.1:8b"  # Или codellama:13b для лучшего понимания кода
    
    # Настройки анализа репозитория
    SUPPORTED_EXTENSIONS = {
        # Код приложения
        '.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.cs',
        # Конфигурация
        '.yml', '.yaml', '.json', '.xml', '.toml', 
        # Инфраструктура
        '.tf', '.hcl',  # Terraform
        # Документация
        '.md', '.rst',
        # Docker
        'Dockerfile', 'docker-compose.yml', '.dockerfile'
    }
    
    # Игнорируемые пути
    IGNORE_PATTERNS = [
        '__pycache__', '.git', 'node_modules', 'venv',
        '.env', '.venv', 'dist', 'build', 'target',
        '*.log', '*.tmp', '.DS_Store'
    ]
    
    # Настройки чанкинга
    CHUNK_SIZE = 1000  # символов
    CHUNK_OVERLAP = 200  # символов
    
    # Типы файлов для разных индексов векторной БД
    FILE_CATEGORIES = {
        'app_code': ['.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.cs'],
        'infra': ['.tf', '.hcl', 'Dockerfile', '.yml', '.yaml', 'docker-compose.yml'],
        'config': ['.json', '.xml', '.toml', '.env', '.cfg', '.ini'],
        'docs': ['.md', '.rst', '.txt']
    }
    
    @classmethod
    def setup_directories(cls):
        """Создание необходимых директорий"""
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        cls.CACHE_DIR.mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "diagrams").mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "reports").mkdir(exist_ok=True)

# Инициализация директорий
Config.setup_directories()