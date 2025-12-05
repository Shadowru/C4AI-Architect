# src/parser/ast_parser.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
from tree_sitter import Language, Parser
import tree_sitter_python
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_go

@dataclass
class Component:
    """Компонент системы"""
    name: str
    type: str  # service, database, queue, cache, etc.
    technology: str
    dependencies: List[str]
    exposed_ports: List[int]
    environment_vars: Dict[str, str]
    endpoints: List[str]
    metadata: Dict[str, any]

@dataclass
class Relationship:
    """Связь между компонентами"""
    source: str
    target: str
    type: str  # http, grpc, messaging, database, etc.
    protocol: str
    description: str

class ASTParser(ABC):
    """Базовый класс для парсеров AST"""
    
    @abstractmethod
    def parse(self, file_path: Path) -> List[Component]:
        pass
    
    @abstractmethod
    def extract_dependencies(self, file_path: Path) -> List[Relationship]:
        pass

class PythonASTParser(ASTParser):
    """Парсер для Python кода"""
    
    def __init__(self):
        self.parser = Parser()
        PY_LANGUAGE = Language(tree_sitter_python.language(), "python")
        self.parser.set_language(PY_LANGUAGE)
    
    def parse(self, file_path: Path) -> List[Component]:
        with open(file_path, 'rb') as f:
            tree = self.parser.parse(f.read())
        
        components = []
        
        # Поиск Flask/FastAPI приложений
        components.extend(self._find_web_frameworks(tree))
        
        # Поиск подключений к БД
        components.extend(self._find_database_connections(tree))
        
        # Поиск очередей сообщений
        components.extend(self._find_message_queues(tree))
        
        return components
    
    def _find_web_frameworks(self, tree) -> List[Component]:
        """Поиск веб-фреймворков"""
        components = []
        query = """
        (call
          function: (attribute
            object: (identifier) @framework
            attribute: (identifier) @method)
          arguments: (argument_list) @args)
        """
        # Упрощенная логика
        return components
    
    def _find_database_connections(self, tree) -> List[Component]:
        """Поиск подключений к БД"""
        # Поиск паттернов типа:
        # - SQLAlchemy create_engine
        # - psycopg2.connect
        # - pymongo.MongoClient
        return []
    
    def _find_message_queues(self, tree) -> List[Component]:
        """Поиск очередей сообщений"""
        # Поиск паттернов типа:
        # - pika (RabbitMQ)
        # - kafka-python
        # - redis pub/sub
        return []
    
    def extract_dependencies(self, file_path: Path) -> List[Relationship]:
        """Извлечение зависимостей из кода"""
        with open(file_path, 'rb') as f:
            tree = self.parser.parse(f.read())
        
        relationships = []
        
        # Поиск HTTP вызовов
        relationships.extend(self._find_http_calls(tree))
        
        # Поиск gRPC вызовов
        relationships.extend(self._find_grpc_calls(tree))
        
        return relationships
    
    def _find_http_calls(self, tree) -> List[Relationship]:
        """Поиск HTTP вызовов (requests, httpx, aiohttp)"""
        return []
    
    def _find_grpc_calls(self, tree) -> List[Relationship]:
        """Поиск gRPC вызовов"""
        return []

class DockerfileParser:
    """Парсер Dockerfile"""
    
    def parse(self, file_path: Path) -> Component:
        """Парсинг Dockerfile"""
        with open(file_path) as f:
            lines = f.readlines()
        
        component = Component(
            name=file_path.parent.name,
            type='container',
            technology='docker',
            dependencies=[],
            exposed_ports=[],
            environment_vars={},
            endpoints=[],
            metadata={}
        )
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('FROM'):
                base_image = line.split()[1]
                component.metadata['base_image'] = base_image
                component.technology = self._detect_technology(base_image)
            
            elif line.startswith('EXPOSE'):
                ports = line.split()[1:]
                component.exposed_ports.extend([int(p) for p in ports])
            
            elif line.startswith('ENV'):
                parts = line.split(maxsplit=2)
                if len(parts) >= 3:
                    component.environment_vars[parts[1]] = parts[2]
        
        return component
    
    def _detect_technology(self, base_image: str) -> str:
        """Определение технологии по базовому образу"""
        tech_map = {
            'python': 'python',
            'node': 'nodejs',
            'openjdk': 'java',
            'golang': 'go',
            'nginx': 'nginx',
            'postgres': 'postgresql',
            'mongo': 'mongodb',
            'redis': 'redis'
        }
        
        for key, value in tech_map.items():
            if key in base_image.lower():
                return value
        
        return 'unknown'

class KubernetesParser:
    """Парсер Kubernetes манифестов"""
    
    def parse(self, file_path: Path) -> List[Component]:
        """Парсинг K8s манифестов"""
        with open(file_path) as f:
            manifests = list(yaml.safe_load_all(f))
        
        components = []
        
        for manifest in manifests:
            if not manifest:
                continue
            
            kind = manifest.get('kind', '')
            
            if kind == 'Deployment':
                components.append(self._parse_deployment(manifest))
            elif kind == 'Service':
                components.append(self._parse_service(manifest))
            elif kind == 'StatefulSet':
                components.append(self._parse_statefulset(manifest))
            elif kind == 'Ingress':
                components.append(self._parse_ingress(manifest))
        
        return components
    
    def _parse_deployment(self, manifest: Dict) -> Component:
        """Парсинг Deployment"""
        metadata = manifest.get('metadata', {})
        spec = manifest.get('spec', {})
        template = spec.get('template', {})
        containers = template.get('spec', {}).get('containers', [])
        
        component = Component(
            name=metadata.get('name', 'unknown'),
            type='service',
            technology='kubernetes',
            dependencies=[],
            exposed_ports=[],
            environment_vars={},
            endpoints=[],
            metadata={
                'kind': 'Deployment',
                'namespace': metadata.get('namespace', 'default'),
                'labels': metadata.get('labels', {})
            }
        )
        
        # Извлечение информации из контейнеров
        for container in containers:
            component.metadata['image'] = container.get('image', '')
            
            # Порты
            for port in container.get('ports', []):
                component.exposed_ports.append(port.get('containerPort'))
            
            # Переменные окружения
            for env in container.get('env', []):
                component.environment_vars[env['name']] = env.get('value', '')
        
        return component
    
    def _parse_service(self, manifest: Dict) -> Component:
        """Парсинг Service"""
        metadata = manifest.get('metadata', {})
        spec = manifest.get('spec', {})
        
        return Component(
            name=metadata.get('name', 'unknown'),
            type='service',
            technology='kubernetes',
            dependencies=[],
            exposed_ports=[p.get('port') for p in spec.get('ports', [])],
            environment_vars={},
            endpoints=[],
            metadata={
                'kind': 'Service',
                'type': spec.get('type', 'ClusterIP'),
                'selector': spec.get('selector', {})
            }
        )
    
    def _parse_statefulset(self, manifest: Dict) -> Component:
        """Парсинг StatefulSet (обычно БД)"""
        metadata = manifest.get('metadata', {})
        
        return Component(
            name=metadata.get('name', 'unknown'),
            type='database',
            technology='kubernetes',
            dependencies=[],
            exposed_ports=[],
            environment_vars={},
            endpoints=[],
            metadata={'kind': 'StatefulSet'}
        )
    
    def _parse_ingress(self, manifest: Dict) -> Component:
        """Парсинг Ingress"""
        metadata = manifest.get('metadata', {})
        spec = manifest.get('spec', {})
        
        endpoints = []
        for rule in spec.get('rules', []):
            host = rule.get('host', '')
            for path in rule.get('http', {}).get('paths', []):
                endpoints.append(f"{host}{path.get('path', '')}")
        
        return Component(
            name=metadata.get('name', 'unknown'),
            type='ingress',
            technology='kubernetes',
            dependencies=[],
            exposed_ports=[80, 443],
            environment_vars={},
            endpoints=endpoints,
            metadata={'kind': 'Ingress'}
        )

class TerraformParser:
    """Парсер Terraform файлов"""
    
    def parse(self, file_path: Path) -> List[Component]:
        """Парсинг Terraform файлов"""
        with open(file_path) as f:
            tf_config = hcl2.load(f)
        
        components = []
        
        # Парсинг ресурсов
        for resource_type, resources in tf_config.get('resource', {}).items():
            for resource_name, resource_config in resources.items():
                component = self._parse_resource(
                    resource_type, 
                    resource_name, 
                    resource_config
                )
                if component:
                    components.append(component)
        
        return components
    
    def _parse_resource(self, resource_type: str, name: str, config: Dict) -> Optional[Component]:
        """Парсинг отдельного ресурса"""
        
        # AWS Resources
        if resource_type == 'aws_instance':
            return Component(
                name=name,
                type='compute',
                technology='aws_ec2',
                dependencies=[],
                exposed_ports=[],
                environment_vars={},
                endpoints=[],
                metadata={
                    'instance_type': config.get('instance_type'),
                    'ami': config.get('ami')
                }
            )
        
        elif resource_type == 'aws_rds_instance':
            return Component(
                name=name,
                type='database',
                technology='aws_rds',
                dependencies=[],
                exposed_ports=[config.get('port', 5432)],
                environment_vars={},
                endpoints=[],
                metadata={
                    'engine': config.get('engine'),
                    'instance_class': config.get('instance_class')
                }
            )
        
        elif resource_type == 'aws_elasticache_cluster':
            return Component(
                name=name,
                type='cache',
                technology='aws_elasticache',
                dependencies=[],
                exposed_ports=[],
                environment_vars={},
                endpoints=[],
                metadata={
                    'engine': config.get('engine'),
                    'node_type': config.get('node_type')
                }
            )
        
        elif resource_type == 'aws_lb':
            return Component(
                name=name,
                type='load_balancer',
                technology='aws_alb',
                dependencies=[],
                exposed_ports=[80, 443],
                environment_vars={},
                endpoints=[],
                metadata={
                    'load_balancer_type': config.get('load_balancer_type')
                }
            )
        
        return None