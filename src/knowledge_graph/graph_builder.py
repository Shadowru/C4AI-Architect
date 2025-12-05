# src/knowledge_graph/graph_builder.py

from typing import List, Dict, Set
import networkx as nx
from dataclasses import dataclass
import json

@dataclass
class GraphNode:
    """Узел графа знаний"""
    id: str
    type: str
    properties: Dict
    semantic_context: Optional[SemanticContext]

@dataclass
class GraphEdge:
    """Ребро графа знаний"""
    source: str
    target: str
    type: str
    properties: Dict

class KnowledgeGraphBuilder:
    """Построитель графа знаний системы"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
    
    def add_component(self, component: Component, semantic_context: SemanticContext):
        """Добавление компонента в граф"""
        
        node = GraphNode(
            id=component.name,
            type=component.type,
            properties={
                'technology': component.technology,
                'ports': component.exposed_ports,
                'env_vars': component.environment_vars,
                'endpoints': component.endpoints,
                'metadata': component.metadata
            },
            semantic_context=semantic_context
        )
        
        self.nodes[component.name] = node
        self.graph.add_node(
            component.name,
            **node.properties,
            semantic_purpose=semantic_context.purpose,
            business_capability=semantic_context.business_capability
        )
    
    def add_relationship(self, relationship: Relationship, semantic_info: Dict):
        """Добавление связи в граф"""
        
        edge = GraphEdge(
            source=relationship.source,
            target=relationship.target,
            type=relationship.type,
            properties={
                'protocol': relationship.protocol,
                'description': relationship.description,
                **semantic_info
            }
        )
        
        self.edges.append(edge)
        self.graph.add_edge(
            relationship.source,
            relationship.target,
            **edge.properties
        )
    
    def detect_subsystems(self) -> List[Set[str]]:
        """Обнаружение подсистем через кластеризацию"""
        
        # Используем алгоритм обнаружения сообществ
        undirected = self.graph.to_undirected()
        communities = nx.community.louvain_communities(undirected)
        
        return [set(community) for community in communities]
    
    def identify_entry_points(self) -> List[str]:
        """Определение точек входа (компоненты без входящих связей)"""
        
        entry_points = []
        for node in self.graph.nodes():
            if self.graph.in_degree(node) == 0:
                entry_points.append(node)
        
        return entry_points
    
    def identify_data_stores(self) -> List[str]:
        """Определение хранилищ данных"""
        
        data_stores = []
        for node_id, node in self.nodes.items():
            if node.type in ['database', 'cache', 'storage']:
                data_stores.append(node_id)
        
        return data_stores
    
    def calculate_criticality(self) -> Dict[str, float]:
        """Расчет критичности компонентов (по PageRank)"""
        
        return nx.pagerank(self.graph)
    
    def find_dependencies_chain(self, component: str) -> List[str]:
        """Поиск цепочки зависимостей компонента"""
        
        if component not in self.graph:
            return []
        
        # Все компоненты, от которых зависит данный
        descendants = nx.descendants(self.graph, component)
        
        return list(descendants)
    
    def export_to_json(self) -> str:
        """Экспорт графа в JSON"""
        
        data = {
            'nodes': [
                {
                    'id': node_id,
                    'type': node.type,
                    'properties': node.properties,
                    'semantic_context': {
                        'purpose': node.semantic_context.purpose if node.semantic_context else '',
                        'business_capability': node.semantic_context.business_capability if node.semantic_context else ''
                    }
                }
                for node_id, node in self.nodes.items()
            ],
            'edges': [
                {
                    'source': edge.source,
                    'target': edge.target,
                    'type': edge.type,
                    'properties': edge.properties
                }
                for edge in self.edges
            ]
        }
        
        return json.dumps(data, indent=2)