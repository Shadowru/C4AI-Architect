import ollama
from typing import List, Dict, Optional
import json
import logging
from pathlib import Path

class LLMEngine:
    def __init__(self, model: str = "codellama:13b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.client = ollama.Client(host=base_url)
        self.logger = logging.getLogger(__name__)
        self._ensure_model()
        
    def _ensure_model(self):
        """Проверяет наличие модели и загружает при необходимости"""
        try:
            models = self.client.list()
            model_names = [m['name'] for m in models.get('models', [])]
            
            # Проверяем точное совпадение или с тегом
            model_exists = any(
                self.model == m or self.model in m 
                for m in model_names
            )
            
            if not model_exists:
                self.logger.info(f"Pulling model {self.model}...")
                self.client.pull(self.model)
                self.logger.info(f"Model {self.model} pulled successfully")
        except Exception as e:
            self.logger.warning(f"Error checking model: {e}")
            self.logger.warning("Continuing anyway, model might be available")
    
    def _generate_with_fallback(self, prompt: str, format: str = 'json', temperature: float = 0.1) -> str:
        """Генерирует ответ с обработкой ошибок"""
        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                format=format,
                options={'temperature': temperature}
            )
            return response.get('response', '{}')
        except Exception as e:
            self.logger.error(f"LLM generation error: {e}")
            return '{}'
    
    def analyze_code_structure(self, code: str, language: str) -> Dict:
        """Анализирует структуру кода с помощью LLM"""
        # Ограничиваем размер кода
        if len(code) > 8000:
            code = code[:8000] + "\n... (truncated)"
        
        prompt = f"""Analyze the following {language} code and extract:
1. Main components and their responsibilities
2. External dependencies and integrations
3. API endpoints or interfaces exposed
4. Database interactions
5. Message queue interactions

Code:
{language}
{code}Respond in JSON format with keys: components, dependencies, apis, database, messaging
Keep responses concise."""
        response_text = self._generate_with_fallback(prompt, format='json', temperature=0.1)
    
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return {
                'components': [],
                'dependencies': [],
                'apis': [],
                'database': [],
                'messaging': []
            }

    def infer_relationships(self, source_component: Dict, target_component: Dict, context: str) -> Dict:
        """Определяет отношения между компонентами"""
        prompt = f"""Given two software components, determine their relationship:Source Component:
{json.dumps(source_component, indent=2)[:500]}


Target Component:
{json.dumps(target_component, indent=2)[:500]}


Context: {context}


Determine:


Type of relationship (uses, depends_on, communicates_with, etc.)
Communication protocol (HTTP, gRPC, message queue, database, etc.)
Brief description of the interaction

Respond in JSON format with keys: relationship_type, protocol, description"""
        response_text = self._generate_with_fallback(prompt, format='json', temperature=0.1)
    
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {
                'relationship_type': context,
                'protocol': 'unknown',
                'description': f'{context} relationship'
            }

    def generate_component_description(self, component_info: Dict) -> str:
        """Генерирует описание компонента"""
    # Ограничиваем размер данных
        info_str = json.dumps(component_info, indent=2)[:1000]
    
        prompt = f"""Generate a concise architectural description for this component:{info_str}


The description should be 1-2 sentences explaining the component's purpose and role in the system.
Be specific and technical."""

        response_text = self._generate_with_fallback(prompt, format='', temperature=0.3)
    
        # Очищаем ответ
        description = response_text.strip()
        if not description:
        # Fallback описание
            name = component_info.get('name', 'Component')
            comp_type = component_info.get('type', 'component')
            return f"{name} - {comp_type} in the system"
    
    # Берём только первые 2 предложения
        sentences = description.split('.')[:2]
        return '.'.join(sentences).strip() + '.'

    def identify_system_boundaries(self, components: List[Dict]) -> Dict:
        """Идентифицирует границы систем"""
        if not components:
            return {'systems': []}
    
        # Ограничиваем количество компонентов для анализа
        components_sample = components[:20]
    
        # Упрощаем данные компонентов
        simplified_components = []
        for comp in components_sample:
            simplified_components.append({
            'id': comp.get('id', ''),
            'name': comp.get('name', ''),
            'type': comp.get('type', ''),
            'technology': comp.get('technology', ''),
            })
    
        prompt = f"""Given these software components, identify logical system boundaries:Components:
{json.dumps(simplified_components, indent=2)}


Group components into logical systems (2-5 systems) based on:


Shared responsibility
Deployment units
Business capabilities

Respond in JSON format with a list of systems, each containing:


name: system name
description: brief description
component_ids: list of component IDs belonging to this system

Example:
{{
"systems": [
{{
"name": "API Gateway",
"description": "Handles external requests",
"component_ids": ["container_api", "component_gateway"]
}}
]
}}"""
        response_text = self._generate_with_fallback(prompt, format='json', temperature=0.2)
    
        try:
            result = json.loads(response_text)
            if 'systems' not in result:
                result = {'systems': []}
            return result
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse system boundaries, using default")
            return {'systems': []}

    def analyze_architecture_patterns(self, components: List[Dict], relationships: List[Dict]) -> Dict:
        """Анализирует архитектурные паттерны в системе"""
        if not components:
            return {'patterns': [], 'recommendations': []}
    
        # Упрощаем данные
        simplified = {
            'component_count': len(components),
            'container_count': len([c for c in components if c.get('type') == 'container']),
            'relationship_count': len(relationships),
            'technologies': list(set(
                c.get('technology', '') for c in components 
                if c.get('technology')
            ))[:10]
        }
    
        prompt = f"""Analyze this software architecture and identify patterns:Architecture Summary:
{json.dumps(simplified, indent=2)}

Identify:

Architectural patterns (microservices, monolith, layered, etc.)
Potential issues or anti-patterns
Brief recommendations

Respond in JSON format with keys: patterns (list), issues (list), recommendations (list)"""
        response_text = self._generate_with_fallback(prompt, format='json', temperature=0.3)
    
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {
                'patterns': ['Unknown pattern'],
            'issues': [],
            'recommendations': []
            }
