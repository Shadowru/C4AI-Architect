#!/usr/bin/env python3
"""
C4AI Architect - Система восстановления архитектурных схем из кода
"""

import sys
from pathlib import Path
from loguru import logger
import argparse

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from config import Config
from modules.repository_analyzer import RepositoryAnalyzer

def setup_logging():
    """Настройка логирования"""
    logger.remove()  # Убираем дефолтный обработчик
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        Config.OUTPUT_DIR / "logs" / "c4ai_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG"
    )

def main():
    """Основная функция"""
    setup_logging()
    
    parser = argparse.ArgumentParser(description='C4AI Architect - Восстановление архитектуры из кода')
    parser.add_argument('repo_path', type=str, help='Путь к репозиторию')
    parser.add_argument('--analyze', action='store_true', help='Выполнить анализ репозитория')
    parser.add_argument('--query', type=str, help='Запрос к проиндексированному репозиторию')
    
    args = parser.parse_args()
    
    repo_path = Path(args.repo_path)
    if not repo_path.exists():
        logger.error(f"Путь не существует: {repo_path}")
        sys.exit(1)
    
    # Инициализация анализатора
    analyzer = RepositoryAnalyzer(repo_path)
    
    if args.analyze:
        logger.info(f"Запуск анализа репозитория: {repo_path}")
        result = analyzer.analyze_repository()
        
        # Сохранение результатов
        import json
        output_file = Config.OUTPUT_DIR / "analysis_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'stats': result['stats'],
                'metadata': result['metadata']
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Результаты сохранены в {output_file}")
        
        # Вывод краткого отчёта
        print("\n" + "="*60)
        print("ОТЧЁТ ПО АНАЛИЗУ РЕПОЗИТОРИЯ")
        print("="*60)
        print(f"Всего файлов: {result['stats']['total_files']}")
        print(f"Обработано файлов: {result['stats']['processed_files']}")
        print(f"Создано чанков: {result['stats']['total_chunks']}")
        
        print("\nЧанки по категориям:")
        for category, count in result['stats']['chunks_by_category'].items():
            print(f"  {category}: {count}")
        
        print("\nОбнаруженные технологии:")
        for tech in result['metadata'].get('detected_technologies', []):
            print(f"  • {tech}")
        
        if result['metadata'].get('services'):
            print("\nОбнаруженные сервисы (docker-compose):")
            for service in result['metadata']['services']:
                print(f"  • {service}")
    
    elif args.query:
        logger.info(f"Выполнение запроса: {args.query}")
        results = analyzer.query_repository(args.query, top_k=5)
        
        print(f"\nРезультаты запроса '{args.query}':")
        print("="*60)
        for i, chunk in enumerate(results, 1):
            print(f"\n{i}. {chunk.metadata['file_path']}")
            print(f"   Категория: {chunk.metadata['file_category']}")
            print(f"   Предпросмотр: {chunk.content[:200]}...")
    
    else:
        logger.info("Используйте --analyze для анализа или --query для поиска")
        parser.print_help()

if __name__ == "__main__":
    main()