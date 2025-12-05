# src/scanner/repository_scanner.py
import os
import git
from pathlib import Path
from typing import List, Dict
import logging
from dataclasses import dataclass

@dataclass
class RepositoryStructure:
    root_path: Path
    code_files: Dict[str, List[Path]]
    docker_files: List[Path]
    k8s_files: List[Path]
    terraform_files: List[Path]
    config_files: List[Path]

class RepositoryScanner:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.logger = logging.getLogger(__name__)
        
        self.file_patterns = {
            'code': {
                'python': ['*.py'],
                'java': ['*.java'],
                'javascript': ['*.js', '*.ts'],
                'go': ['*.go'],
            },
            'docker': ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml'],
            'kubernetes': ['*.yaml', '*.yml'],
            'terraform': ['*.tf', '*.tfvars'],
            'config': ['*.json', '*.yaml', '*.yml', '*.toml', '*.ini']
        }
        
    def scan(self) -> RepositoryStructure:
        """Сканирует репозиторий и классифицирует файлы"""
        self.logger.info(f"Scanning repository: {self.repo_path}")
        
        structure = RepositoryStructure(
            root_path=self.repo_path,
            code_files={},
            docker_files=[],
            k8s_files=[],
            terraform_files=[],
            config_files=[]
        )
        
        # Сканируем файлы
        for root, dirs, files in os.walk(self.repo_path):
            # Пропускаем служебные директории
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__']]
            
            root_path = Path(root)
            
            for file in files:
                file_path = root_path / file
                self._classify_file(file_path, structure)
                
        self.logger.info(f"Scan complete. Found {sum(len(files) for files in structure.code_files.values())} code files")
        return structure
    
    def _classify_file(self, file_path: Path, structure: RepositoryStructure):
        """Классифицирует файл по типу"""
        file_name = file_path.name.lower()
        
        # Docker файлы
        if any(pattern in file_name for pattern in self.file_patterns['docker']):
            structure.docker_files.append(file_path)
            return
            
        # Terraform файлы
        if file_path.suffix in ['.tf', '.tfvars']:
            structure.terraform_files.append(file_path)
            return
            
        # Kubernetes файлы (требуют дополнительной проверки содержимого)
        if file_path.suffix in ['.yaml', '.yml']:
            if self._is_k8s_file(file_path):
                structure.k8s_files.append(file_path)
            else:
                structure.config_files.append(file_path)
            return
            
        # Код
        for lang, patterns in self.file_patterns['code'].items():
            if any(file_path.match(pattern) for pattern in patterns):
                if lang not in structure.code_files:
                    structure.code_files[lang] = []
                structure.code_files[lang].append(file_path)
                return
    
    def _is_k8s_file(self, file_path: Path) -> bool:
        """Проверяет, является ли YAML файл конфигурацией Kubernetes"""
        try:
            import yaml
            with open(file_path, 'r') as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    return 'apiVersion' in content and 'kind' in content
        except:
            pass
        return False