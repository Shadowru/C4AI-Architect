# src/generator/c4_model_builder.py
from typing import List, Dict, Optional
import logging
from src.models.architecture_model import *
from src.analyzer.semantic_analyzer import SemanticAnalyzer
from src.analyzer.llm_engine import LLMEngine

class C4ModelBuilder:
    def __init__(self, semantic_analyzer: SemanticAnalyzer, llm_engine: LLMEngine):
        self.analyzer = semantic_analyzer
        self.llm = llm_engine
        self.logger = logging.getLogger(__name__)
        
    def build(self, analysis: Dict, repository_name: str) -> C4Model:
        """Строит C4 модель из результатов анализа"""
        self.logger.info("Building C4 model...")
        
        model = C4Model(
            name=repository_name,
            description=f"Architecture model for {repository_name}"
        )
        
        # Уровень 1: System Context
        self._build_context_level(model, analysis)
        
        # Уровень 2: Containers
        self._build_container_level(model, analysis)
        
        # Уровень 3: Components
        self._build_component_level(model, analysis)
        
        # Relationships
        self._build_relationships(model, analysis)
        
        return model
    
    def _build_context_level(self, model: C4Model, analysis: Dict):
        """Строит System Context диаграмму"""
        insights = analysis.get('insights', {})
        systems = insights.get('systems', {}).get('systems', [])
        
        if not systems:
            # Создаём одну систему по умолчанию
            system = ArchitectureElement(
                id="main_system",
                name=model.name,
                type=ElementType.SOFTWARE_SYSTEM,
                description=self.llm.generate_component_description({
                    'name': model.name,
                    'containers': len(analysis.get('containers', [])),
                    'components': len(analysis.get('components', []))
                })
            )
            model.systems.append(system)
        else:
            for sys in systems:
                system = ArchitectureElement(
                    id=f"system_{sys['name'].lower().replace(' ', '_')}",
                    name=sys['name'],
                    type=ElementType.SOFTWARE_SYSTEM,
                    description=sys.get('description', '')
                )
                model.systems.append(system)
        
        # Добавляем внешние системы из анализа
        self._identify_external_systems(model, analysis)
    
    def _identify_external_systems(self, model: C4Model, analysis: Dict):
        """Идентифицирует внешние системы"""
        external_systems = set()
        
        # Из Terraform ресурсов
        for resource in analysis.get('infrastructure', {}).get('terraform', []):
            if resource['type'] in ['aws_rds_instance', 'aws_elasticache_cluster']:
                external_systems.add(('Database', 'External database system'))
            elif resource['type'] in ['aws_sqs_queue', 'aws_sns_topic']:
                external_systems.add(('Message Queue', 'External messaging system'))
        
        # Из Docker зависимостей
        for container in analysis.get('containers', []):
            image = container.get('image', '')
            if 'postgres' in image or 'mysql' in image:
                external_systems.add(('Database', 'Database system'))
            elif 'redis' in image:
                external_systems.add(('Cache', 'Caching system'))
            elif 'kafka' in image or 'rabbitmq' in image:
                external_systems.add(('Message Queue', 'Messaging system'))
        
        # Добавляем внешние системы в модель
        for name, desc in external_systems:
            system = ArchitectureElement(
                id=f"external_{name.lower().replace(' ', '_')}",
                name=name,
                type=ElementType.SOFTWARE_SYSTEM,
                description=desc,
                tags={'external'}
            )
            model.systems.append(system)
    
    def _build_container_level(self, model: C4Model, analysis: Dict):
        """Строит Container диаграмму"""
        for container_data in analysis.get('containers', []):
            # Генерируем описание с помощью LLM
            description = self.llm.generate_component_description(container_data)
            
            # Определяем технологии
            technologies = self._extract_technologies(container_data)
            
            container = Container(
                id=container_data['id'],
                name=container_data['name'],
                description=description,
                technology=technologies,
                runtime_environment=container_data.get('image', container_data.get('technology', '')),
                exposed_ports=[int(p) for p in container_data.get('ports', []) if str(p).isdigit()],
                environment_vars=container_data.get('environment', {}),
                dependencies=container_data.get('depends_on', [])
            )
            
            model.containers.append(container)
    
    def _extract_technologies(self, container_data: Dict) -> List[Technology]:
        """Извлекает технологии из данных контейнера"""
        technologies = []
        
        image = container_data.get('image', '').lower()
        tech = container_data.get('technology', '').lower()
        
        tech_mapping = {
            'python': Technology.PYTHON,
            'java': Technology.JAVA,
            'node': Technology.NODEJS,
            'postgres': Technology.POSTGRES,
            'redis': Technology.REDIS,
            'kafka': Technology.KAFKA,
            'go': Technology.GOLANG,
            'csharp': Technology.CSHARP,
            'dotnet': Technology.CSHARP,
        }
        
        combined = f"{image} {tech}"
        for key, tech_enum in tech_mapping.items():
            if key in combined:
                technologies.append(tech_enum)
        
        return technologies if technologies else None
    
    def _build_component_level(self, model: C4Model, analysis: Dict):
        """Строит Component диаграмму"""
        for component_data in analysis.get('components', []):
            description = self.llm.generate_component_description(component_data)
            
            lang_tech = self._language_to_technology(component_data.get('language', ''))
            
            component = Component(
                id=component_data['id'],
                name=component_data['name'],
                description=description,
                container_id=component_data.get('container_id', ''),
                technology=[lang_tech] if lang_tech else None,
                source_files=[component_data.get('file_path', '')]
            )
            
            # Извлекаем интерфейсы из деталей
            details = component_data.get('details', {})
            if 'classes' in details:
                component.interfaces = [cls['name'] for cls in details['classes']]
            
            model.components.append(component)
    
    def _language_to_technology(self, language: str) -> Optional[Technology]:
        """Конвертирует язык в Technology enum"""
        mapping = {
            'python': Technology.PYTHON,
            'java': Technology.JAVA,
            'javascript': Technology.NODEJS,
            'typescript': Technology.NODEJS,
            'go': Technology.GOLANG,
            'csharp': Technology.CSHARP,
        }
        return mapping.get(language.lower())
    
    def _build_relationships(self, model: C4Model, analysis: Dict):
        """Строит связи между элементами"""
        graph = self.analyzer.dependency_graph
        
        for source, target, data in graph.edges(data=True):
            relationship_type = data.get('relationship', 'uses')
            
            # Получаем информацию об узлах
            source_node = graph.nodes.get(source, {})
            target_node = graph.nodes.get(target, {})
            
            # Используем LLM для определения деталей связи
            relationship_details = self.llm.infer_relationships(
                source_node, target_node, relationship_type
            )
            
            relationship = Relationship(
                source_id=source,
                target_id=target,
                description=relationship_details.get('description', f"{relationship_type} relationship"),
                technology=relationship_details.get('protocol', ''),
                protocol=relationship_details.get('protocol', '')
            )
            
            model.relationships.append(relationship)