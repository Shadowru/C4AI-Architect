# src/scanner/parsers/docker_parser.py
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

@dataclass
class DockerService:
    name: str
    image: Optional[str] = None
    build_context: Optional[str] = None
    ports: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    volumes: List[str] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)

class DockerParser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_dockerfile(self, file_path: Path) -> Dict:
        """Парсит Dockerfile"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            self.logger.warning(f"Failed to read {file_path}: {e}")
            return {}
            
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
                parts = line.split()
                if len(parts) > 1:
                    info['base_image'] = parts[1]
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
                    else:
                        info['environment'][key_value[0]] = key_value[1] if len(key_value) > 1 else ''
            elif line.startswith('WORKDIR'):
                parts = line.split()
                if len(parts) > 1:
                    info['workdir'] = parts[1]
            elif line.startswith(('RUN', 'CMD', 'ENTRYPOINT')):
                info['commands'].append(line)
                
        return info
    
    def parse_compose(self, file_path: Path) -> Dict[str, DockerService]:
        """Парсит docker-compose.yml"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                compose_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error in {file_path}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Failed to read {file_path}: {e}")
            return {}
        
        if not compose_data or not isinstance(compose_data, dict):
            self.logger.warning(f"Invalid compose file format: {file_path}")
            return {}
            
        services = {}
        
        for service_name, service_config in compose_data.get('services', {}).items():
            if not isinstance(service_config, dict):
                continue
                
            # Обработка портов
            ports = []
            for port in service_config.get('ports', []):
                if isinstance(port, (str, int)):
                    ports.append(str(port))
                elif isinstance(port, dict):
                    # Формат: target: 80, published: 8080
                    if 'published' in port:
                        ports.append(str(port['published']))
            
            # Обработка environment
            environment = {}
            env_data = service_config.get('environment', {})
            if isinstance(env_data, dict):
                environment = {k: str(v) for k, v in env_data.items()}
            elif isinstance(env_data, list):
                for item in env_data:
                    if '=' in str(item):
                        key, value = str(item).split('=', 1)
                        environment[key] = value
            
            # Обработка depends_on
            depends_on = []
            depends_data = service_config.get('depends_on', [])
            if isinstance(depends_data, list):
                depends_on = [str(d) for d in depends_data]
            elif isinstance(depends_data, dict):
                depends_on = list(depends_data.keys())
            
            # Обработка build
            build_context = None
            build_data = service_config.get('build')
            if isinstance(build_data, str):
                build_context = build_data
            elif isinstance(build_data, dict):
                build_context = build_data.get('context', build_data.get('dockerfile'))
            
            services[service_name] = DockerService(
                name=service_name,
                image=service_config.get('image'),
                build_context=build_context,
                ports=ports,
                environment=environment,
                depends_on=depends_on,
                volumes=service_config.get('volumes', []) if isinstance(service_config.get('volumes'), list) else [],
                networks=service_config.get('networks', []) if isinstance(service_config.get('networks'), list) else []
            )
            
        return services