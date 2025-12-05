# src/models/architecture_model.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any
from enum import Enum

class ElementType(Enum):
    PERSON = "person"
    SOFTWARE_SYSTEM = "software_system"
    CONTAINER = "container"
    COMPONENT = "component"
    
class Technology(Enum):
    PYTHON = "Python"
    JAVA = "Java"
    NODEJS = "Node.js"
    DOCKER = "Docker"
    KUBERNETES = "Kubernetes"
    POSTGRES = "PostgreSQL"
    REDIS = "Redis"
    KAFKA = "Apache Kafka"
    GOLANG = "Go"
    CSHARP = "C#"

@dataclass
class ArchitectureElement:
    """Базовый элемент архитектуры"""
    id: str
    name: str
    type: ElementType
    description: str
    technology: Optional[List[Technology]] = None
    tags: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class Relationship:
    """Связь между элементами"""
    source_id: str
    target_id: str
    description: str
    technology: Optional[str] = None
    protocol: Optional[str] = None
    
@dataclass
class Container:
    """Контейнер (приложение, сервис, база данных и т.д.)"""
    id: str
    name: str
    description: str
    type: ElementType = ElementType.CONTAINER
    technology: Optional[List[Technology]] = None
    tags: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)
    runtime_environment: Optional[str] = None
    exposed_ports: List[int] = field(default_factory=list)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    def to_element(self) -> ArchitectureElement:
        """Конвертирует в базовый элемент"""
        return ArchitectureElement(
            id=self.id,
            name=self.name,
            type=self.type,
            description=self.description,
            technology=self.technology,
            tags=self.tags,
            properties=self.properties
        )
    
@dataclass
class Component:
    """Компонент внутри контейнера"""
    id: str
    name: str
    description: str
    container_id: str
    type: ElementType = ElementType.COMPONENT
    technology: Optional[List[Technology]] = None
    tags: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)
    source_files: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)
    
    def to_element(self) -> ArchitectureElement:
        """Конвертирует в базовый элемент"""
        return ArchitectureElement(
            id=self.id,
            name=self.name,
            type=self.type,
            description=self.description,
            technology=self.technology,
            tags=self.tags,
            properties=self.properties
        )
    
@dataclass
class C4Model:
    """Полная C4 модель системы"""
    name: str
    description: str
    people: List[ArchitectureElement] = field(default_factory=list)
    systems: List[ArchitectureElement] = field(default_factory=list)
    containers: List[Container] = field(default_factory=list)
    components: List[Component] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    
    def get_container_by_id(self, container_id: str) -> Optional[Container]:
        """Находит контейнер по ID"""
        return next((c for c in self.containers if c.id == container_id), None)
    
    def get_component_by_id(self, component_id: str) -> Optional[Component]:
        """Находит компонент по ID"""
        return next((c for c in self.components if c.id == component_id), None)
    
    def get_system_by_id(self, system_id: str) -> Optional[ArchitectureElement]:
        """Находит систему по ID"""
        return next((s for s in self.systems if s.id == system_id), None)
    
    def get_components_by_container(self, container_id: str) -> List[Component]:
        """Получает все компоненты контейнера"""
        return [c for c in self.components if c.container_id == container_id]
    
    def get_relationships_for_element(self, element_id: str) -> List[Relationship]:
        """Получает все связи элемента"""
        return [r for r in self.relationships 
                if r.source_id == element_id or r.target_id == element_id]