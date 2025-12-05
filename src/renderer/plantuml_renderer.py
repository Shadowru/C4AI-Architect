# src/renderer/plantuml_renderer.py
from pathlib import Path
from typing import List
from src.models.architecture_model import *

class PlantUMLRenderer:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def render_context(self, model: C4Model) -> str:
        """Генерирует System Context диаграмму"""
        puml = ["@startuml", "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml", ""]
        
        puml.append(f"title System Context diagram for {model.name}")
        puml.append("")
        
        # Люди (если есть)
        for person in model.people:
            puml.append(f'Person({person.id}, "{person.name}", "{person.description}")')
        
        # Системы
        for system in model.systems:
            if 'external' in system.tags:
                puml.append(f'System_Ext({system.id}, "{system.name}", "{system.description}")')
            else:
                puml.append(f'System({system.id}, "{system.name}", "{system.description}")')
        
        puml.append("")
        
        # Связи на уровне систем
        for rel in model.relationships:
            if (any(s.id == rel.source_id for s in model.systems) and 
                any(s.id == rel.target_id for s in model.systems)):
                puml.append(f'Rel({rel.source_id}, {rel.target_id}, "{rel.description}")')
        
        puml.append("@enduml")
        
        output_file = self.output_dir / "01-system-context.puml"
        output_file.write_text("\n".join(puml))
        
        return str(output_file)
    
    def render_container(self, model: C4Model) -> str:
        """Генерирует Container диаграмму"""
        puml = ["@startuml", "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml", ""]
        
        puml.append(f"title Container diagram for {model.name}")
        puml.append("")
        
        # Основная система как граница
        main_system = next((s for s in model.systems if 'external' not in s.tags), None)
        if main_system:
            puml.append(f'System_Boundary({main_system.id}, "{main_system.name}") {{')
            
            # Контейнеры
            for container in model.containers:
                tech_str = ", ".join([t.value for t in container.technology]) if container.technology else ""
                puml.append(f'  Container({container.id}, "{container.name}", "{tech_str}", "{container.description}")')
            
            puml.append("}")
            puml.append("")
        
        # Внешние системы
        for system in model.systems:
            if 'external' in system.tags:
                puml.append(f'System_Ext({system.id}, "{system.name}", "{system.description}")')
        
        puml.append("")
        
        # Связи
        for rel in model.relationships:
            if (any(c.id == rel.source_id for c in model.containers) or 
                any(c.id == rel.target_id for c in model.containers)):
                protocol = f", {rel.protocol}" if rel.protocol else ""
                puml.append(f'Rel({rel.source_id}, {rel.target_id}, "{rel.description}"{protocol})')
        
        puml.append("@enduml")
        
        output_file = self.output_dir / "02-container.puml"
        output_file.write_text("\n".join(puml))
        
        return str(output_file)
    
    def render_component(self, model: C4Model, container_id: str) -> str:
        """Генерирует Component диаграмму для конкретного контейнера"""
        container = next((c for c in model.containers if c.id == container_id), None)
        if not container:
            return ""
        
        puml = ["@startuml", "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml", ""]
        
        puml.append(f"title Component diagram for {container.name}")
        puml.append("")
        
        # Контейнер как граница
        puml.append(f'Container_Boundary({container.id}, "{container.name}") {{')
        
        # Компоненты этого контейнера
        components = [c for c in model.components if c.container_id == container_id]
        for component in components:
            tech_str = ", ".join([t.value for t in component.technology]) if component.technology else ""
            puml.append(f'  Component({component.id}, "{component.name}", "{tech_str}", "{component.description}")')
        
        puml.append("}")
        puml.append("")
        
        # Другие контейнеры
        for other_container in model.containers:
            if other_container.id != container_id:
                tech_str = ", ".join([t.value for t in other_container.technology]) if other_container.technology else ""
                puml.append(f'Container({other_container.id}, "{other_container.name}", "{tech_str}")')
        
        puml.append("")
        
        # Связи компонентов
        component_ids = {c.id for c in components}
        for rel in model.relationships:
            if rel.source_id in component_ids or rel.target_id in component_ids:
                protocol = f", {rel.protocol}" if rel.protocol else ""
                puml.append(f'Rel({rel.source_id}, {rel.target_id}, "{rel.description}"{protocol})')
        
        puml.append("@enduml")
        
        output_file = self.output_dir / f"03-component-{container.name}.puml"
        output_file.write_text("\n".join(puml))
        
        return str(output_file)
    
    def render_all(self, model: C4Model) -> List[str]:
        """Генерирует все диаграммы"""
        files = []
        
        files.append(self.render_context(model))
        files.append(self.render_container(model))
        
        for container in model.containers:
            component_file = self.render_component(model, container.id)
            if component_file:
                files.append(component_file)
        
        return files