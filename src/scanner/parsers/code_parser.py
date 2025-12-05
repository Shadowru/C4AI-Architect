# src/scanner/parsers/docker_parser.py
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class DockerService:
    name: str
    image: Optional[str]
    build_context: Optional[str]
    ports: List[str]
    environment: Dict[str, str]
    depends_on: List[str]
    volumes: List[str]
    networks: List[str]

class DockerParser:
    def parse_dockerfile(self, file_path: Path) -> Dict:
        """Парсит Dockerfile"""
        with open(file_path, 'r') as f:
            content = f.read()
            
        info = {
            'base_image': None,
            'exposed_ports': [],
            'environment': {},
            'commands': [],
            'workdir': None
        }
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if line.startswith('FROM'):
                info['base_image'] = line.split()[1]
            elif line.startswith('EXPOSE'):
                ports = re.findall(r'\d+', line)
                info['exposed_ports'].extend(ports)
            elif line.startswith('ENV'):
                parts = line.split(maxsplit=2)
                if len(parts) >= 3:
                    key_value = parts[1:]
                    if '=' in key_value[0]:
                        key, value = key_value[0].split('=', 1)
                        info['environment'][key] = value
            elif line.startswith('WORKDIR'):
                info['workdir'] = line.split()[1]
            elif line.startswith(('RUN', 'CMD', 'ENTRYPOINT')):
                info['commands'].append(line)
                
        return info
    
    def parse_compose(self, file_path: Path) -> Dict[str, DockerService]:
        """Парсит docker-compose.yml"""
        with open(file_path, 'r') as f:
            compose_data = yaml.safe_load(f)
            
        services = {}
        
        for service_name, service_config in compose_data.get('services', {}).items():
            services[service_name] = DockerService(
                name=service_name,
                image=service_config.get('image'),
                build_context=service_config.get('build'),
                ports=service_config.get('ports', []),
                environment=service_config.get('environment', {}),
                depends_on=service_config.get('depends_on', []),
                volumes=service_config.get('volumes', []),
                networks=service_config.get('networks', [])
            )
            
        return services

# src/scanner/parsers/k8s_parser.py
import yaml
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class K8sResource:
    kind: str
    name: str
    namespace: str
    labels: Dict[str, str]
    spec: Dict

class KubernetesParser:
    def parse(self, file_path: Path) -> List[K8sResource]:
        """Парсит Kubernetes манифесты"""
        resources = []
        
        with open(file_path, 'r') as f:
            docs = yaml.safe_load_all(f)
            
            for doc in docs:
                if not doc:
                    continue
                    
                resource = K8sResource(
                    kind=doc.get('kind'),
                    name=doc.get('metadata', {}).get('name'),
                    namespace=doc.get('metadata', {}).get('namespace', 'default'),
                    labels=doc.get('metadata', {}).get('labels', {}),
                    spec=doc.get('spec', {})
                )
                resources.append(resource)
                
        return resources
    
    def extract_containers(self, resource: K8sResource) -> List[Dict]:
        """Извлекает информацию о контейнерах из ресурса"""
        containers = []
        
        if resource.kind in ['Deployment', 'StatefulSet', 'DaemonSet', 'Pod']:
            spec = resource.spec
            if resource.kind != 'Pod':
                spec = spec.get('template', {}).get('spec', {})
                
            for container in spec.get('containers', []):
                containers.append({
                    'name': container.get('name'),
                    'image': container.get('image'),
                    'ports': container.get('ports', []),
                    'env': container.get('env', []),
                    'resources': container.get('resources', {})
                })
                
        return containers

# src/scanner/parsers/terraform_parser.py
import hcl2
from pathlib import Path
from typing import Dict, List

class TerraformParser:
    def parse(self, file_path: Path) -> Dict:
        """Парсит Terraform файлы"""
        with open(file_path, 'r') as f:
            tf_data = hcl2.load(f)
            
        infrastructure = {
            'resources': [],
            'modules': [],
            'variables': [],
            'outputs': []
        }
        
        # Ресурсы
        for resource_type, resources in tf_data.get('resource', [{}])[0].items():
            for resource_name, resource_config in resources.items():
                infrastructure['resources'].append({
                    'type': resource_type,
                    'name': resource_name,
                    'config': resource_config
                })
                
        # Модули
        for module_name, module_config in tf_data.get('module', [{}])[0].items():
            infrastructure['modules'].append({
                'name': module_name,
                'source': module_config.get('source'),
                'config': module_config
            })
            
        return infrastructure

# src/scanner/parsers/code_parser.py
import ast
from pathlib import Path
from typing import List, Dict
import javalang

class PythonCodeParser:
    def parse(self, file_path: Path) -> Dict:
        """Парсит Python код"""
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                tree = ast.parse(f.read())
            except:
                return {}
                
        info = {
            'classes': [],
            'functions': [],
            'imports': [],
            'decorators': []
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                info['classes'].append({
                    'name': node.name,
                    'bases': [base.id for base in node.bases if isinstance(base, ast.Name)],
                    'methods': [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                    'decorators': [self._get_decorator_name(d) for d in node.decorator_list]
                })
            elif isinstance(node, ast.FunctionDef):
                if not any(node in cls.body for cls in ast.walk(tree) if isinstance(cls, ast.ClassDef)):
                    info['functions'].append({
                        'name': node.name,
                        'args': [arg.arg for arg in node.args.args],
                        'decorators': [self._get_decorator_name(d) for d in node.decorator_list]
                    })
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    info['imports'].extend([alias.name for alias in node.names])
                else:
                    info['imports'].append(node.module)
                    
        return info
    
    def _get_decorator_name(self, decorator) -> str:
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        return str(decorator)