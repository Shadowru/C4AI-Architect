import os
import ast
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import yaml
import json
import javalang
from dataclasses import dataclass
from loguru import logger
import chromadb
from chromadb.utils import embedding_functions
from langchain.text_splitter import RecursiveCharacterTextSplitter

from config import Config

@dataclass
class CodeChunk:
    """Структура для хранения чанка кода с метаданными"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None

class RepositoryAnalyzer:
    """Анализатор репозитория с интеллектуальным чанкированием"""
    
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).absolute()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Инициализация ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=str(Config.CACHE_DIR / "chroma_db")
        )
        
        # Модель для эмбеддингов
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Коллекции для разных типов файлов
        self.collections = {}
        self._init_collections()
        
        logger.info(f"Инициализирован анализатор для репозитория: {self.repo_path}")
    
    def _init_collections(self):
        """Инициализация коллекций в векторной БД"""
        for category in Config.FILE_CATEGORIES.keys():
            collection_name = f"code_{category}"
            try:
                # Пытаемся получить существующую коллекцию
                collection = self.chroma_client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_fn
                )
            except:
                # Создаём новую
                collection = self.chroma_client.create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_fn,
                    metadata={"hnsw:space": "cosine"}
                )
            self.collections[category] = collection
    
    def _should_ignore(self, path: Path) -> bool:
        """Проверка, нужно ли игнорировать файл/папку"""
        path_str = str(path)
        
        # Проверка паттернов игнорирования
        for pattern in Config.IGNORE_PATTERNS:
            if pattern in path_str:
                return True
        
        # Проверка расширения
        if path.is_file():
            # Для Dockerfile (без расширения)
            if path.name in ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml']:
                return False
            
            # Проверка расширения
            suffix = path.suffix.lower()
            if suffix not in Config.SUPPORTED_EXTENSIONS:
                return True
        
        return False
    
    def _categorize_file(self, file_path: Path) -> str:
        """Определение категории файла"""
        file_name = file_path.name.lower()
        
        # Специальные файлы
        if file_name in ['dockerfile', 'docker-compose.yml', 'docker-compose.yaml']:
            return 'infra'
        
        suffix = file_path.suffix.lower()
        
        for category, extensions in Config.FILE_CATEGORIES.items():
            if suffix in extensions:
                return category
        
        return 'docs'  # По умолчанию
    
    def _extract_metadata(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Извлечение метаданных из файла"""
        metadata = {
            'file_path': str(file_path.relative_to(self.repo_path)),
            'file_name': file_path.name,
            'file_size': len(content),
            'file_category': self._categorize_file(file_path),
        }
        
        # Специфичная обработка для разных типов файлов
        try:
            if file_path.name in ['package.json', 'pom.xml', 'build.gradle', 'go.mod', 'Cargo.toml', 'requirements.txt']:
                metadata['type'] = 'dependencies'
                metadata['content_preview'] = content[:500]  # Превью для LLM
                
            elif file_path.name in ['docker-compose.yml', 'docker-compose.yaml']:
                metadata['type'] = 'docker_compose'
                # Парсим структуру docker-compose
                try:
                    compose_data = yaml.safe_load(content)
                    if compose_data and 'services' in compose_data:
                        metadata['services'] = list(compose_data['services'].keys())
                except:
                    pass
                    
            elif file_path.suffix in ['.yaml', '.yml'] and 'deployment' in file_path.name.lower():
                metadata['type'] = 'kubernetes'
                
            elif file_path.suffix == '.tf':
                metadata['type'] = 'terraform'
                
            elif file_path.name == 'Dockerfile':
                metadata['type'] = 'dockerfile'
                # Извлекаем базовый образ
                for line in content.split('\n'):
                    if line.strip().upper().startswith('FROM'):
                        metadata['base_image'] = line.strip()[5:].strip()
                        break
                        
        except Exception as e:
            logger.warning(f"Ошибка при обработке метаданных {file_path}: {e}")
        
        return metadata
    
    def _chunk_by_ast(self, content: str, metadata: Dict, language: str) -> List[CodeChunk]:
        """Чанкирование с использованием AST для разных языков"""
        chunks = []
        
        try:
            if language == 'python':
                # Используем стандартный ast для Python
                tree = ast.parse(content)
                
                # Собираем все функции и классы
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        start_line = node.lineno - 1  # Python использует 1-индексацию
                        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
                        
                        lines = content.split('\n')
                        node_code = '\n'.join(lines[start_line:end_line])
                        
                        chunk_id = f"{metadata['file_path']}_{node.name}_{start_line}_{end_line}"
                        chunk_metadata = metadata.copy()
                        chunk_metadata.update({
                            'start_line': start_line,
                            'end_line': end_line,
                            'node_type': type(node).__name__,
                            'node_name': node.name,
                            'language': 'python'
                        })
                        
                        chunks.append(CodeChunk(
                            id=chunk_id,
                            content=node_code,
                            metadata=chunk_metadata
                        ))
                        
            elif language == 'java':
                # Используем javalang для Java
                tree = javalang.parse.parse(content)
                
                for path, node in tree:
                    if isinstance(node, (javalang.tree.MethodDeclaration, javalang.tree.ClassDeclaration)):
                        # javalang не предоставляет end_line, используем эвристику
                        start_line = node.position.line - 1 if node.position else 0
                        
                        # Находим следующую сущность для определения конца
                        lines = content.split('\n')
                        # Эвристика: ищем следующую сущность на том же уровне вложенности
                        # Упрощённый вариант - берём следующие 50 строк или до конца файла
                        end_line = min(start_line + 50, len(lines))
                        
                        node_code = '\n'.join(lines[start_line:end_line])
                        
                        name = node.name if hasattr(node, 'name') else 'anonymous'
                        chunk_id = f"{metadata['file_path']}_{name}_{start_line}_{end_line}"
                        chunk_metadata = metadata.copy()
                        chunk_metadata.update({
                            'start_line': start_line,
                            'end_line': end_line,
                            'node_type': type(node).__name__,
                            'node_name': name,
                            'language': 'java'
                        })
                        
                        chunks.append(CodeChunk(
                            id=chunk_id,
                            content=node_code,
                            metadata=chunk_metadata
                        ))
                            
        except Exception as e:
            logger.warning(f"Ошибка AST-парсинга для {metadata['file_path']}: {e}")
        
        return chunks
    
    def _chunk_by_heuristics(self, content: str, metadata: Dict) -> List[CodeChunk]:
        """Чанкирование на основе эвристик для языков без AST-парсера"""
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        chunk_start_line = 0
        
        for i, line in enumerate(lines):
            current_chunk.append(line)
            
            # Обнаружение начала новой логической единицы
            is_new_unit = False
            line_stripped = line.strip()
            
            file_ext = metadata['file_path'].split('.')[-1].lower()
            
            # Эвристики для разных языков
            if file_ext in ['py']:
                if (line_stripped.startswith('def ') or 
                    line_stripped.startswith('class ') or
                    line_stripped.startswith('async def ')):
                    is_new_unit = True
            
            elif file_ext in ['js', 'ts', 'jsx', 'tsx']:
                if (line_stripped.startswith('function ') or
                    line_stripped.startswith('class ') or
                    line_stripped.startswith('const ') and '=' in line and ('=>' in line or 'function' in line) or
                    line_stripped.startswith('async function') or
                    line_stripped.startswith('export default')):
                    is_new_unit = True
            
            elif file_ext in ['java']:
                if (line_stripped.startswith('public ') or
                    line_stripped.startswith('private ') or
                    line_stripped.startswith('protected ') or
                    line_stripped.startswith('class ') or
                    ' void ' in line_stripped or
                    ' boolean ' in line_stripped):
                    is_new_unit = True
            
            elif file_ext in ['go']:
                if line_stripped.startswith('func ') or line_stripped.startswith('type '):
                    is_new_unit = True
            
            elif file_ext in ['rs']:
                if line_stripped.startswith('fn ') or line_stripped.startswith('struct ') or line_stripped.startswith('impl '):
                    is_new_unit = True
            
            # Если нашли новую единицу или чанк стал слишком большим
            if (is_new_unit and len(current_chunk) > 10) or len('\n'.join(current_chunk)) > Config.CHUNK_SIZE:
                if len(current_chunk) > 1:
                    # Если это новая единица, сохраняем предыдущий чанк без текущей строки
                    if is_new_unit:
                        chunk_content = '\n'.join(current_chunk[:-1])
                        chunk_end_line = i - 1
                    else:
                        chunk_content = '\n'.join(current_chunk)
                        chunk_end_line = i
                    
                    chunk_id = f"{metadata['file_path']}_lines_{chunk_start_line}_{chunk_end_line}"
                    chunk_metadata = metadata.copy()
                    chunk_metadata.update({
                        'start_line': chunk_start_line,
                        'end_line': chunk_end_line,
                        'chunking_method': 'heuristics'
                    })
                    
                    chunks.append(CodeChunk(
                        id=chunk_id,
                        content=chunk_content,
                        metadata=chunk_metadata
                    ))
                    
                    # Начинаем новый чанк
                    if is_new_unit:
                        current_chunk = [line]
                        chunk_start_line = i
                    else:
                        current_chunk = []
                        chunk_start_line = i + 1
        
        # Добавляем последний чанк
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunk_id = f"{metadata['file_path']}_lines_{chunk_start_line}_{len(lines)}"
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'start_line': chunk_start_line,
                'end_line': len(lines),
                'chunking_method': 'heuristics'
            })
            
            chunks.append(CodeChunk(
                id=chunk_id,
                content=chunk_content,
                metadata=chunk_metadata
            ))
        
        return chunks
    
    def _process_file(self, file_path: Path) -> List[CodeChunk]:
        """Обработка одного файла и разбиение на чанки"""
        try:
            # Чтение файла с правильной кодировкой
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            # Извлечение метаданных
            metadata = self._extract_metadata(file_path, content)
            
            # Выбор метода чанкирования в зависимости от типа файла
            chunks = []
            
            if metadata['file_category'] == 'app_code':
                file_ext = file_path.suffix.lower()
                
                # Пытаемся использовать AST для поддерживаемых языков
                if file_ext == '.py':
                    chunks = self._chunk_by_ast(content, metadata, 'python')
                elif file_ext == '.java':
                    chunks = self._chunk_by_ast(content, metadata, 'java')
                else:
                    chunks = self._chunk_by_heuristics(content, metadata)
                
                # Если AST не дало результатов, используем эвристики
                if not chunks:
                    chunks = self._chunk_by_heuristics(content, metadata)
                    
                # Если всё ещё нет чанков, используем текстовый сплиттер
                if not chunks:
                    chunks_text = self.text_splitter.split_text(content)
                    for i, chunk_text in enumerate(chunks_text):
                        chunk_id = f"{metadata['file_path']}_chunk_{i}"
                        chunk_metadata = metadata.copy()
                        chunk_metadata['chunk_index'] = i
                        chunk_metadata['chunking_method'] = 'text_splitter'
                        chunks.append(CodeChunk(
                            id=chunk_id,
                            content=chunk_text,
                            metadata=chunk_metadata
                        ))
            else:
                # Для конфигурации и документации используем текстовый сплиттер
                chunks_text = self.text_splitter.split_text(content)
                for i, chunk_text in enumerate(chunks_text):
                    chunk_id = f"{metadata['file_path']}_chunk_{i}"
                    chunk_metadata = metadata.copy()
                    chunk_metadata['chunk_index'] = i
                    chunk_metadata['chunking_method'] = 'text_splitter'
                    chunks.append(CodeChunk(
                        id=chunk_id,
                        content=chunk_text,
                        metadata=chunk_metadata
                    ))
            
            logger.debug(f"Обработан файл {file_path}: {len(chunks)} чанков")
            return chunks
            
        except Exception as e:
            logger.error(f"Ошибка при обработке файла {file_path}: {e}")
            return []
    
    def analyze_repository(self) -> Dict[str, Any]:
        """Основной метод анализа репозитория"""
        logger.info(f"Начинаем анализ репозитория: {self.repo_path}")
        
        # Сбор статистики
        stats = {
            'total_files': 0,
            'processed_files': 0,
            'total_chunks': 0,
            'chunks_by_category': {cat: 0 for cat in Config.FILE_CATEGORIES.keys()}
        }
        
        all_chunks = []
        
        # Рекурсивный обход репозитория
        for root, dirs, files in os.walk(self.repo_path):
            root_path = Path(root)
            
            # Фильтрация игнорируемых директорий
            dirs[:] = [d for d in dirs if not self._should_ignore(root_path / d)]
            
            for file in files:
                file_path = root_path / file
                stats['total_files'] += 1
                
                if self._should_ignore(file_path):
                    continue
                
                # Обработка файла
                chunks = self._process_file(file_path)
                stats['processed_files'] += 1
                stats['total_chunks'] += len(chunks)
                
                # Категоризация чанков
                for chunk in chunks:
                    category = chunk.metadata['file_category']
                    stats['chunks_by_category'][category] += 1
                    all_chunks.append(chunk)
        
        # Индексация в векторной БД
        self._index_chunks(all_chunks)
        
        # Извлечение ключевых метаданных
        repo_metadata = self._extract_repository_metadata(all_chunks)
        
        logger.info(f"Анализ завершен. Обработано {stats['processed_files']}/{stats['total_files']} файлов, создано {stats['total_chunks']} чанков")
        
        return {
            'stats': stats,
            'metadata': repo_metadata,
            'chunks': all_chunks
        }
    
    def _index_chunks(self, chunks: List[CodeChunk]):
        """Индексация чанков в соответствующих коллекциях"""
        logger.info("Начинаем индексацию чанков в векторной БД...")
        
        # Группировка чанков по категориям
        chunks_by_category = {cat: [] for cat in self.collections.keys()}
        
        for chunk in chunks:
            category = chunk.metadata['file_category']
            if category in chunks_by_category:
                chunks_by_category[category].append(chunk)
        
        # Индексация для каждой категории
        for category, category_chunks in chunks_by_category.items():
            if not category_chunks:
                continue
                
            collection = self.collections[category]
            
            # Подготовка данных для добавления
            ids = [chunk.id for chunk in category_chunks]
            documents = [chunk.content for chunk in category_chunks]
            metadatas = [chunk.metadata for chunk in category_chunks]
            
            # Добавление в коллекцию
            try:
                collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                logger.info(f"Добавлено {len(category_chunks)} чанков в коллекцию '{category}'")
            except Exception as e:
                logger.error(f"Ошибка при добавлении в коллекцию '{category}': {e}")
    
    def _extract_repository_metadata(self, chunks: List[CodeChunk]) -> Dict[str, Any]:
        """Извлечение метаданных репозитория из всех чанков"""
        metadata = {
            'detected_technologies': set(),
            'services': set(),
            'entry_points': [],
            'external_dependencies': set()
        }
        
        for chunk in chunks:
            # Извлечение технологий из различных файлов
            chunk_meta = chunk.metadata
            
            # Анализ Dockerfile
            if chunk_meta.get('type') == 'dockerfile' and 'base_image' in chunk_meta:
                metadata['detected_technologies'].add(f"Docker: {chunk_meta['base_image']}")
            
            # Анализ docker-compose
            elif chunk_meta.get('type') == 'docker_compose' and 'services' in chunk_meta:
                for service in chunk_meta['services']:
                    metadata['services'].add(service)
            
            # Анализ package.json, requirements.txt и т.д.
            elif chunk_meta.get('type') == 'dependencies':
                # Простая эвристика для определения зависимостей
                content_lower = chunk.content.lower()
                if 'express' in content_lower:
                    metadata['detected_technologies'].add('Express.js')
                if 'react' in content_lower:
                    metadata['detected_technologies'].add('React')
                if 'django' in content_lower:
                    metadata['detected_technologies'].add('Django')
                if 'flask' in content_lower:
                    metadata['detected_technologies'].add('Flask')
                if 'spring' in content_lower:
                    metadata['detected_technologies'].add('Spring')
            
            # Поиск entry points
            if 'main' in chunk_meta['file_name'].lower() or 'index' in chunk_meta['file_name'].lower():
                if chunk_meta['file_category'] == 'app_code':
                    metadata['entry_points'].append(chunk_meta['file_path'])
        
        # Преобразование множеств в списки для JSON-сериализации
        metadata['detected_technologies'] = list(metadata['detected_technologies'])
        metadata['services'] = list(metadata['services'])
        
        return metadata
    
    def query_repository(self, query: str, category: Optional[str] = None, top_k: int = 10) -> List[CodeChunk]:
        """Поиск релевантных чанков по запросу"""
        if category and category in self.collections:
            collections_to_search = [self.collections[category]]
        else:
            collections_to_search = self.collections.values()
        
        all_results = []
        
        for collection in collections_to_search:
            try:
                results = collection.query(
                    query_texts=[query],
                    n_results=top_k
                )
                
                if results and results['documents']:
                    for i in range(len(results['documents'][0])):
                        chunk = CodeChunk(
                            id=results['ids'][0][i],
                            content=results['documents'][0][i],
                            metadata=results['metadatas'][0][i],
                            embedding=results['embeddings'][0][i] if results['embeddings'] else None
                        )
                        all_results.append(chunk)
                        
            except Exception as e:
                logger.error(f"Ошибка при запросе к коллекции: {e}")
        
        # Сортировка по релевантности (если бы были скоринги)
        return all_results[:top_k]