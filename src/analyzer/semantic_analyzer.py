from typing import List, Dict, Set, Optional
import networkx as nx
from pathlib import Path
import logging

from src.scanner.repository_scanner import RepositoryStructure
from src.scanner.parsers.code_parser import PythonCodeParser
from src.scanner.parsers.docker_parser import DockerParser
from src.scanner.parsers.k8s_parser import KubernetesParser
from src.scanner.parsers.terraform_parser import TerraformParser
from src.analyzer.llm_engine import LLMEngine

class SemanticAnalyzer:
    def __init__(self, llm_engine: LLMEngine):
        self.llm = llm_engine
        self.logger = logging.getLogger(__name__)
        self.dependency_graph = nx.DiGraph()
        
        # Парсеры
        self.parsers = {
            'python': PythonCodeParser(),
            'docker': DockerParser(),
            'k8s': KubernetesParser(),
            'terraform': TerraformParser()
        }
        
    def analyze(self, structure: RepositoryStructure) -> Dict:
        """Выполняет семантический анализ репозитория"""
        self.logger.info("Starting semantic analysis...")
        
        analysis_result = {
            'containers': [],
            'components': [],
            'infrastructure': {},
            'dependencies': [],
            'insights': {}
        }
        
        # Анализ Docker
        containers = self._analyze_docker(structure.docker_files)
        analysis_result['containers'] = containers
        
        # Анализ Kubernetes
        k8s_resources = self._analyze_kubernetes(structure.k8s_files)
        analysis_result['infrastructure']['kubernetes'] = k8s_resources
        
        # Анализ Terraform
        tf_resources = self._analyze_terraform(structure.terraform_files)
        analysis_result['infrastructure']['terraform'] = tf_resources
        
        # Анализ кода
        components = self._analyze_code(structure.code_files, containers)
        analysis_result['components'] = components
        
        # Построение графа зависимостей
        self._build_dependency_graph(analysis_result)
        
        # Извлечение insights с помощью LLM
        analysis_result['insights'] = self._extract_insights(analysis_result)
        
        return analysis_result
    
    def _analyze_docker(self, docker_files: List[Path]) -> List[Dict]:
        """Анализирует Docker файлы"""
        containers = []
        
        for file_path in docker_files:
            if file_path.name == 'Dockerfile':
                dockerfile_info = self.parsers['docker'].parse_dockerfile(file_path)
                container_name = file_path.parent.name
                
                containers.append({
                    'id': f"container_{container_name}",
                    'name': container_name,
                    'type': 'container',
                    'technology': dockerfile_info.get('base_image', ''),
                    'ports': dockerfile_info.get('exposed_ports', []),
                    'source_path': str(file_path.parent)
                })
                
            elif 'docker-compose' in file_path.name:
                services = self.parsers['docker'].parse_compose(file_path)
                
                for service_name, service in services.items():
                    containers.append({
                        'id': f"container_{service_name}",
                        'name': service_name,
                        'type': 'container',
                        'image': service.image,
                        'ports': service.ports,
                        'depends_on': service.depends_on,
                        'environment': service.environment
                    })
                    
        return containers
    
    def _analyze_kubernetes(self, k8s_files: List[Path]) -> List[Dict]:
        """Анализирует Kubernetes манифесты"""
        resources = []
        
        for file_path in k8s_files:
            k8s_resources = self.parsers['k8s'].parse(file_path)
            
            for resource in k8s_resources:
                resource_info = {
                    'kind': resource.kind,
                    'name': resource.name,
                    'namespace': resource.namespace,
                    'labels': resource.labels
                }
                
                # Извлекаем контейнеры
                if resource.kind in ['Deployment', 'StatefulSet', 'DaemonSet']:
                    resource_info['containers'] = self.parsers['k8s'].extract_containers(resource)
                    
                resources.append(resource_info)
                
        return resources
    
    def _analyze_terraform(self, tf_files: List[Path]) -> List[Dict]:
        """Анализирует Terraform файлы"""
        all_resources = []
        
        for file_path in tf_files:
            try:
                infrastructure = self.parsers['terraform'].parse(file_path)
                all_resources.extend(infrastructure['resources'])
            except Exception as e:
                self.logger.warning(f"Failed to parse {file_path}: {e}")
                
        return all_resources
    
    def _analyze_code(self, code_files: Dict[str, List[Path]], containers: List[Dict]) -> List[Dict]:
        """Анализирует исходный код"""
        components = []
        
        for language, files in code_files.items():
            if language not in self.parsers:
                continue
                
            parser = self.parsers[language]
            
            for file_path in files:
                try:
                    code_info = parser.parse(file_path)
                    
                    # Читаем код для LLM анализа
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code_content = f.read()
                    
                    # Анализируем с помощью LLM (для небольших файлов)
                    if len(code_content) < 10000:
                        llm_analysis = self.llm.analyze_code_structure(code_content, language)
                        code_info.update(llm_analysis)
                    
                    # Определяем контейнер
                    container_id = self._match_file_to_container(file_path, containers)
                    
                    component = {
                        'id': f"component_{file_path.stem}",
                        'name': file_path.stem,
                        'type': 'component',
                        'language': language,
                        'container_id': container_id,
                        'file_path': str(file_path),
                        'details': code_info
                    }
                    
                    components.append(component)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse {file_path}: {e}")
                    
        return components
    
    def _match_file_to_container(self, file_path: Path, containers: List[Dict]) -> Optional[str]:
        """Сопоставляет файл с контейнером"""
        for container in containers:
            if 'source_path' in container:
                if str(file_path).startswith(container['source_path']):
                    return container['id']
        return None
    
    def _build_dependency_graph(self, analysis: Dict):
        """Строит граф зависимостей"""
        # Добавляем узлы
        for container in analysis['containers']:
            self.dependency_graph.add_node(container['id'], **container)
            
        for component in analysis['components']:
            self.dependency_graph.add_node(component['id'], **component)
            
        # Добавляем рёбра из docker-compose depends_on
        for container in analysis['containers']:
            for dep in container.get('depends_on', []):
                dep_id = f"container_{dep}"
                if self.dependency_graph.has_node(dep_id):
                    self.dependency_graph.add_edge(container['id'], dep_id, 
                                                  relationship='depends_on')
        
        # Добавляем рёбра компонент -> контейнер
        for component in analysis['components']:
            if component.get('container_id'):
                self.dependency_graph.add_edge(component['id'], 
                                              component['container_id'],
                                              relationship='deployed_in')
        
        # Анализируем импорты для связей между компонентами
        self._analyze_code_dependencies(analysis['components'])
    
    def _analyze_code_dependencies(self, components: List[Dict]):
        """Анализирует зависимости в коде"""
        # Строим карту модулей
        module_map = {}
        for component in components:
            details = component.get('details', {})
            for cls in details.get('classes', []):
                module_map[cls['name']] = component['id']
                
        # Находим зависимости
        for component in components:
            details = component.get('details', {})
            imports = details.get('imports', [])
            
            for imp in imports:
                # Упрощённая логика - можно улучшить
                for module_name, target_id in module_map.items():
                    if module_name in imp and target_id != component['id']:
                        self.dependency_graph.add_edge(
                            component['id'], target_id,
                            relationship='imports'
                        )
    
    def _extract_insights(self, analysis: Dict) -> Dict:
        """Извлекает архитектурные insights с помощью LLM"""
        insights = {
            'systems': {'systems': []},
            'total_containers': len(analysis.get('containers', [])),
            'total_components': len(analysis.get('components', [])),
            'dependency_depth': 0,
            'patterns': {},
        }
        
        try:
            # Группируем компоненты в системы
            all_components = analysis.get('containers', []) + analysis.get('components', [])
            
            if all_components:
                self.logger.info("Identifying system boundaries...")
                systems = self.llm.identify_system_boundaries(all_components)
                insights['systems'] = systems
            
            # Вычисляем глубину зависимостей
            if self.dependency_graph and nx.is_directed_acyclic_graph(self.dependency_graph):
                try:
                    insights['dependency_depth'] = nx.dag_longest_path_length(self.dependency_graph)
                except:
                    insights['dependency_depth'] = 0
            
            # Анализируем архитектурные паттерны
            if all_components:
                self.logger.info("Analyzing architecture patterns...")
                patterns = self.llm.analyze_architecture_patterns(
                    all_components,
                    list(self.dependency_graph.edges(data=True))
                )
                insights['patterns'] = patterns
                
        except Exception as e:
            self.logger.error(f"Error extracting insights: {e}")
            # Возвращаем базовые insights при ошибке
        
        return insights