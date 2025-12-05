# src/scanner/repository_scanner.py

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Set
import yaml
import json
from tree_sitter import Language, Parser
import hcl2

@dataclass
class RepositoryStructure:
    """Структура репозитория"""
    docker_files: List[Path]
    kubernetes_files: List[Path]
    terraform_files: List[Path]
    source_code: Dict[str, List[Path]]  # язык -> файлы
    config_files: List[Path]
    dependencies: Dict[str, any]

class RepositoryScanner:
    """Сканер репозитория для обнаружения артефактов"""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.structure = RepositoryStructure(
            docker_files=[],
            kubernetes_files=[],
            terraform_files=[],
            source_code={},
            config_files=[],
            dependencies={}
        )
    
    def scan(self) -> RepositoryStructure:
        """Сканирование репозитория"""
        self._scan_docker_files()
        self._scan_kubernetes_files()
        self._scan_terraform_files()
        self._scan_source_code()
        self._scan_dependencies()
        return self.structure
    
    def _scan_docker_files(self):
        """Поиск Dockerfile и docker-compose"""
        patterns = ['**/Dockerfile*', '**/docker-compose*.yml']
        for pattern in patterns:
            self.structure.docker_files.extend(
                self.repo_path.rglob(pattern)
            )
    
    def _scan_kubernetes_files(self):
        """Поиск K8s манифестов"""
        for yaml_file in self.repo_path.rglob('*.yaml'):
            if self._is_kubernetes_manifest(yaml_file):
                self.structure.kubernetes_files.append(yaml_file)
    
    def _scan_terraform_files(self):
        """Поиск Terraform файлов"""
        self.structure.terraform_files = list(
            self.repo_path.rglob('*.tf')
        )
    
    def _scan_source_code(self):
        """Сканирование исходного кода"""
        language_extensions = {
            'python': ['.py'],
            'java': ['.java'],
            'javascript': ['.js', '.ts'],
            'go': ['.go'],
            'csharp': ['.cs']
        }
        
        for lang, extensions in language_extensions.items():
            files = []
            for ext in extensions:
                files.extend(self.repo_path.rglob(f'*{ext}'))
            if files:
                self.structure.source_code[lang] = files
    
    def _scan_dependencies(self):
        """Анализ зависимостей"""
        dependency_files = {
            'requirements.txt': self._parse_requirements,
            'package.json': self._parse_package_json,
            'pom.xml': self._parse_pom,
            'go.mod': self._parse_go_mod
        }
        
        for filename, parser in dependency_files.items():
            for dep_file in self.repo_path.rglob(filename):
                self.structure.dependencies[str(dep_file)] = parser(dep_file)
    
    def _is_kubernetes_manifest(self, file_path: Path) -> bool:
        """Проверка, является ли файл K8s манифестом"""
        try:
            with open(file_path) as f:
                content = yaml.safe_load(f)
                return isinstance(content, dict) and 'kind' in content
        except:
            return False
    
    def _parse_requirements(self, file_path: Path) -> List[str]:
        with open(file_path) as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    def _parse_package_json(self, file_path: Path) -> Dict:
        with open(file_path) as f:
            data = json.load(f)
            return {
                'dependencies': data.get('dependencies', {}),
                'devDependencies': data.get('devDependencies', {})
            }
    
    def _parse_pom(self, file_path: Path) -> Dict:
        # Упрощенная версия
        return {'file': str(file_path)}
    
    def _parse_go_mod(self, file_path: Path) -> List[str]:
        with open(file_path) as f:
            return [line.strip() for line in f if line.strip().startswith('require')]