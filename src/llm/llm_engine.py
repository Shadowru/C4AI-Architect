# src/llm/llm_engine.py

from typing import List, Dict, Optional
from dataclasses import dataclass
import json
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from langchain.llms import LlamaCpp
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

@dataclass
class SemanticContext:
    """Семантический контекст компонента"""
    component_name: str
    purpose: str
    business_capability: str
    interactions: List[str]
    technology_stack: List[str]

class LocalLLMEngine:
    """Движок для работы с локальными LLM"""
    
    def __init__(self, model_path: str, model_type: str = "llama"):
        self.model_type = model_type
        
        if model_type == "llama":
            self.llm = LlamaCpp(
                model_path=model_path,
                n_ctx=4096,
                n_batch=512,
                n_gpu_layers=32,  # Для GPU ускорения
                temperature=0.1,
                max_tokens=2000,
                top_p=0.95,
            )
        elif model_type == "mistral":
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="auto"
            )
        
        self._init_prompts()
    
    def _init_prompts(self):
        """Инициализация промптов"""
        
        self.component_analysis_prompt = PromptTemplate(
            input_variables=["component_info"],
            template="""
Analyze the following software component and provide semantic information:

Component Information:
{component_info}

Please provide:
1. Primary purpose of this component
2. Business capability it supports
3. Key responsibilities
4. Suggested C4 component type (Container, Component, or Code level)

Respond in JSON format:
{{
    "purpose": "...",
    "business_capability": "...",
    "responsibilities": ["...", "..."],
    "c4_level": "container|component|code",
    "component_type": "service|database|queue|cache|frontend|..."
}}
"""
        )
        
        self.relationship_analysis_prompt = PromptTemplate(
            input_variables=["source", "target", "interaction_details"],
            template="""
Analyze the relationship between two components:

Source Component: {source}
Target Component: {target}
Interaction Details: {interaction_details}

Determine:
1. Type of relationship (synchronous/asynchronous)
2. Communication protocol
3. Purpose of interaction
4. Data flow direction

Respond in JSON format:
{{
    "relationship_type": "sync|async",
    "protocol": "http|grpc|messaging|database|...",
    "purpose": "...",
    "direction": "unidirectional|bidirectional"
}}
"""
        )
        
        self.architecture_summary_prompt = PromptTemplate(
            input_variables=["components", "relationships"],
            template="""
Given the following system components and relationships, provide a high-level architecture summary:

Components:
{components}

Relationships:
{relationships}

Provide:
1. System architecture pattern (microservices, monolith, event-driven, etc.)
2. Key architectural characteristics
3. Identified subsystems/bounded contexts
4. Recommended C4 diagram levels

Respond in JSON format:
{{
    "architecture_pattern": "...",
    "characteristics": ["...", "..."],
    "subsystems": [
        {{"name": "...", "components": ["...", "..."]}}
    ],
    "recommended_diagrams": ["context", "container", "component"]
}}
"""
        )
    
    def analyze_component(self, component: Component) -> SemanticContext:
        """Семантический анализ компонента"""
        
        component_info = f"""
Name: {component.name}
Type: {component.type}
Technology: {component.technology}
Exposed Ports: {component.exposed_ports}
Dependencies: {component.dependencies}
Metadata: {json.dumps(component.metadata, indent=2)}
"""
        
        if self.model_type == "llama":
            chain = LLMChain(llm=self.llm, prompt=self.component_analysis_prompt)
            response = chain.run(component_info=component_info)
        else:
            response = self._generate_mistral(
                self.component_analysis_prompt.format(component_info=component_info)
            )
        
        try:
            result = json.loads(response)
            return SemanticContext(
                component_name=component.name,
                purpose=result.get('purpose', ''),
                business_capability=result.get('business_capability', ''),
                interactions=[],
                technology_stack=[component.technology]
            )
        except json.JSONDecodeError:
            # Fallback если LLM не вернул валидный JSON
            return SemanticContext(
                component_name=component.name,
                purpose=f"Component: {component.type}",
                business_capability="Unknown",
                interactions=[],
                technology_stack=[component.technology]
            )
    
    def analyze_relationship(self, relationship: Relationship) -> Dict:
        """Анализ связи между компонентами"""
        
        interaction_details = f"""
Type: {relationship.type}
Protocol: {relationship.protocol}
Description: {relationship.description}
"""
        
        if self.model_type == "llama":
            chain = LLMChain(llm=self.llm, prompt=self.relationship_analysis_prompt)
            response = chain.run(
                source=relationship.source,
                target=relationship.target,
                interaction_details=interaction_details
            )
        else:
            response = self._generate_mistral(
                self.relationship_analysis_prompt.format(
                    source=relationship.source,
                    target=relationship.target,
                    interaction_details=interaction_details
                )
            )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "relationship_type": relationship.type,
                "protocol": relationship.protocol,
                "purpose": relationship.description,
                "direction": "unidirectional"
            }
    
    def generate_architecture_summary(
        self, 
        components: List[Component], 
        relationships: List[Relationship]
    ) -> Dict:
        """Генерация общего описания архитектуры"""
        
        components_summary = "\n".join([
            f"- {c.name} ({c.type}, {c.technology})" 
            for c in components
        ])
        
        relationships_summary = "\n".join([
            f"- {r.source} -> {r.target} ({r.type})" 
            for r in relationships
        ])
        
        if self.model_type == "llama":
            chain = LLMChain(llm=self.llm, prompt=self.architecture_summary_prompt)
            response = chain.run(
                components=components_summary,
                relationships=relationships_summary
            )
        else:
            response = self._generate_mistral(
                self.architecture_summary_prompt.format(
                    components=components_summary,
                    relationships=relationships_summary
                )
            )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "architecture_pattern": "microservices",
                "characteristics": ["distributed", "containerized"],
                "subsystems": [],
                "recommended_diagrams": ["context", "container"]
            }
    
    def _generate_mistral(self, prompt: str) -> str:
        """Генерация с использованием Mistral"""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=2000,
            temperature=0.1,
            do_sample=True,
            top_p=0.95
        )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Извлекаем только ответ (после промпта)
        return response[len(prompt):].strip()

class SemanticEnricher:
    """Обогащение компонентов семантической информацией"""
    
    def __init__(self, llm_engine: LocalLLMEngine):
        self.llm_engine = llm_engine
    
    def enrich_components(
        self, 
        components: List[Component]
    ) -> Dict[str, SemanticContext]:
        """Обогащение компонентов семантикой"""
        
        enriched = {}
        
        for component in components:
            context = self.llm_engine.analyze_component(component)
            enriched[component.name] = context
        
        return enriched
    
    def enrich_relationships(
        self, 
        relationships: List[Relationship]
    ) -> List[Dict]:
        """Обогащение связей семантикой"""
        
        enriched = []
        
        for relationship in relationships:
            analysis = self.llm_engine.analyze_relationship(relationship)
            enriched.append({
                'relationship': relationship,
                'semantic_info': analysis
            })
        
        return enriched