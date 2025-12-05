# src/c4/c4_generator.py

from typing import List, Dict, Set
from dataclasses import dataclass
from pathlib import Path

@dataclass
class C4Element:
    """Элемент C4 диаграммы"""
    id: str
    name: str
    type: str  # person, system, container, component
    description: str
    technology: str = ""
    tags: List[str] = None

@dataclass
class C4Relationship:
    """Связь в C4 диаграмме"""
    source: str
    target: str
    description: str
    technology: str = ""

class C4Generator:
    """Генератор C4 диаграмм"""
    
    def __init__(self, knowledge_graph: KnowledgeGraphBuilder):
        self.kg = knowledge_graph
    
    def generate_context_diagram(self) -> str:
        """Генерация Context диаграммы (Level 1)"""
        
        elements = []
        relationships = []
        
        # Определяем систему
        system_name = self._infer_system_name()
        elements.append(C4Element(
            id="system",
            name=system_name,
            type="system",
            description="The main system"
        ))
        
        # Определяем внешние системы
        external_systems = self._identify_external_systems()
        for ext_sys in external_systems:
            elements.append(C4Element(
                id=ext_sys['id'],
                name=ext_sys['name'],
                type="system",
                description=ext_sys['description']
            ))
            
            relationships.append(C4Relationship(
                source="system",
                target=ext_sys['id'],
                description=ext_sys['interaction']
            ))
        
        # Определяем пользователей/акторов
        actors = self._identify_actors()
        for actor in actors:
            elements.append(C4Element(
                id=actor['id'],
                name=actor['name'],
                type="person",
                description=actor['description']
            ))
            
            relationships.append(C4Relationship(
                source=actor['id'],
                target="system",
                description=actor['interaction']
            ))
        
        return self._render_plantuml_context(elements, relationships)
    
    def generate_container_diagram(self) -> str:
        """Генерация Container диаграммы (Level 2)"""
        
        elements = []
        relationships = []
        
        # Группируем компоненты по типам
        containers = self._identify_containers()
        
        for container in containers:
            elements.append(C4Element(
                id=container['id'],
                name=container['name'],
                type="container",
                description=container['description'],
                technology=container['technology']
            ))
        
        # Добавляем связи между контейнерами
        for edge in self.kg.edges:
            if edge.source in [c['id'] for c in containers] and \
               edge.target in [c['id'] for c in containers]:
                relationships.append(C4Relationship(
                    source=edge.source,
                    target=edge.target,
                    description=edge.properties.get('description', ''),
                    technology=edge.properties.get('protocol', '')
                ))
        
        return self._render_plantuml_container(elements, relationships)
    
    def generate_component_diagram(self, container_name: str) -> str:
        """Генерация Component диаграммы (Level 3)"""
        
        # Находим все компоненты внутри контейнера
        components = self._get_components_in_container(container_name)
        
        elements = []
        relationships = []
        
        for comp in components:
            elements.append(C4Element(
                id=comp['id'],
                name=comp['name'],
                type="component",
                description=comp['description'],
                technology=comp['technology']
            ))
        
        # Связи между компонентами
        for edge in self.kg.edges:
            if edge.source in [c['id'] for c in components] and \
               edge.target in [c['id'] for c in components]:
                relationships.append(C4Relationship(
                    source=edge.source,
                    target=edge.target,
                    description=edge.properties.get('description', ''),
                    technology=edge.properties.get('protocol', '')
                ))
        
        return self._render_plantuml_component(container_name, elements, relationships)
    
    def _infer_system_name(self) -> str:
        """Определение имени системы"""
        # Можно взять из git repo name или из доминирующих компонентов
        return "System"
    
    def _identify_external_systems(self) -> List[Dict]:
        """Определение внешних систем"""
        external = []
        
        # Ищем компоненты, которые явно внешние
        for node_id, node in self.kg.nodes.items():
            if 'external' in node.properties.get('metadata', {}).get('tags', []):
                external.append({
                    'id': node_id,
                    'name': node_id,
                    'description': node.semantic_context.purpose if node.semantic_context else '',
                    'interaction': 'Uses'
                })
        
        return external
    
    def _identify_actors(self) -> List[Dict]:
        """Определение акторов/пользователей"""
        # Можно определить по entry points
        entry_points = self.kg.identify_entry_points()
        
        actors = []
        for ep in entry_points:
            node = self.kg.nodes.get(ep)
            if node and node.type in ['frontend', 'api_gateway', 'ingress']:
                actors.append({
                    'id': 'user',
                    'name': 'User',
                    'description': 'System user',
                    'interaction': 'Uses'
                })
                break
        
        return actors
    
    def _identify_containers(self) -> List[Dict]:
        """Определение контейнеров"""
        containers = []
        
        for node_id, node in self.kg.nodes.items():
            if node.type in ['service', 'database', 'cache', 'queue', 'frontend']:
                containers.append({
                    'id': node_id,
                    'name': node_id,
                    'description': node.semantic_context.purpose if node.semantic_context else '',
                    'technology': node.properties['technology']
                })
        
        return containers
    
    def _get_components_in_container(self, container_name: str) -> List[Dict]:
        """Получение компонентов внутри контейнера"""
        # Это требует более глубокого анализа кода
        # Для простоты возвращаем пустой список
        return []
    
    def _render_plantuml_context(
        self, 
        elements: List[C4Element], 
        relationships: List[C4Relationship]
    ) -> str:
        """Рендеринг Context диаграммы в PlantUML"""
        
        lines = [
            "@startuml",
            "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml",
            "",
            "LAYOUT_WITH_LEGEND()",
            ""
        ]
        
        # Элементы
        for elem in elements:
            if elem.type == "person":
                lines.append(f'Person({elem.id}, "{elem.name}", "{elem.description}")')
            elif elem.type == "system":
                if elem.id == "system":
                    lines.append(f'System({elem.id}, "{elem.name}", "{elem.description}")')
                else:
                    lines.append(f'System_Ext({elem.id}, "{elem.name}", "{elem.description}")')
        
        lines.append("")
        
        # Связи
        for rel in relationships:
            lines.append(f'Rel({rel.source}, {rel.target}, "{rel.description}")')
        
        lines.append("@enduml")
        
        return "\n".join(lines)
    
    def _render_plantuml_container(
        self, 
        elements: List[C4Element], 
        relationships: List[C4Relationship]
    ) -> str:
        """Рендеринг Container диаграммы в PlantUML"""
        
        lines = [
            "@startuml",
            "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml",
            "",
            "LAYOUT_WITH_LEGEND()",
            ""
        ]
        
        # Элементы
        for elem in elements:
            container_type = self._map_to_container_type(elem.type)
            lines.append(
                f'{container_type}({elem.id}, "{elem.name}", '
                f'"{elem.technology}", "{elem.description}")'
            )
        
        lines.append("")
        
        # Связи
        for rel in relationships:
            tech_info = f", {rel.technology}" if rel.technology else ""
            lines.append(
                f'Rel({rel.source}, {rel.target}, "{rel.description}"{tech_info})'
            )
        
        lines.append("@enduml")
        
        return "\n".join(lines)
    
    def _render_plantuml_component(
        self,
        container_name: str,
        elements: List[C4Element],
        relationships: List[C4Relationship]
    ) -> str:
        """Рендеринг Component диаграммы в PlantUML"""
        
        lines = [
            "@startuml",
            "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml",
            "",
            "LAYOUT_WITH_LEGEND()",
            "",
            f'Container_Boundary({container_name}, "{container_name}") {{'
        ]
        
        # Компоненты
        for elem in elements:
            lines.append(
                f'  Component({elem.id}, "{elem.name}", '
                f'"{elem.technology}", "{elem.description}")'
            )
        
        lines.append("}")
        lines.append("")
        
        # Связи
        for rel in relationships:
            lines.append(
                f'Rel({rel.source}, {rel.target}, "{rel.description}")'
            )
        
        lines.append("@enduml")
        
        return "\n".join(lines)
    
    def _map_to_container_type(self, component_type: str) -> str:
        """Маппинг типа компонента на тип контейнера C4"""
        mapping = {
            'service': 'Container',
            'database': 'ContainerDb',
            'cache': 'ContainerDb',
            'queue': 'ContainerQueue',
            'frontend': 'Container'
        }
        return mapping.get(component_type, 'Container')
    
    def generate_all_diagrams(self, output_dir: Path):
        """Генерация всех диаграмм"""
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Context diagram
        context = self.generate_context_diagram()
        (output_dir / "context.puml").write_text(context)
        
        # Container diagram
        container = self.generate_container_diagram()
        (output_dir / "container.puml").write_text(container)
        
        # Component diagrams для каждого контейнера
        containers = self._identify_containers()
        for cont in containers:
            if cont['type'] == 'service':  # Только для сервисов
                component = self.generate_component_diagram(cont['id'])
                (output_dir / f"component_{cont['id']}.puml").write_text(component)