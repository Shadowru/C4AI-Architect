# src/orchestrator.py

from pathlib import Path
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class C4ArchitectureRecovery:
    """Главный оркестратор системы"""
    
    def __init__(
        self,
        repo_path: Path,
        llm_model_path: str,
        output_dir: Path,
        model_type: str = "llama"
    ):
        self.repo_path = repo_path
        self.output_dir = output_dir
        
        # Инициализация компонентов
        logger.info("Initializing components...")
        
        self.scanner = RepositoryScanner(repo_path)
        self.llm_engine = LocalLLMEngine(llm_model_path, model_type)
        self.semantic_enricher = SemanticEnricher(self.llm_engine)
        self.knowledge_graph = KnowledgeGraphBuilder()
        
        # Парсеры
        self.python_parser = PythonASTParser()
        self.dockerfile_parser = DockerfileParser()
        self.k8s_parser = KubernetesParser()
        self.terraform_parser = TerraformParser()
    
    def run(self):
        """Запуск процесса восстановления архитектуры"""
        
        logger.info("Step 1: Scanning repository...")
        structure = self.scanner.scan()
        
        logger.info("Step 2: Parsing infrastructure files...")
        components = self._parse_all_files(structure)
        
        logger.info("Step 3: Extracting relationships...")
        relationships = self._extract_relationships(structure, components)
        
        logger.info("Step 4: Semantic enrichment with LLM...")
        semantic_contexts = self.semantic_enricher.enrich_components(components)
        semantic_relationships = self.semantic_enricher.enrich_relationships(relationships)
        
        logger.info("Step 5: Building knowledge graph...")
        self._build_knowledge_graph(components, semantic_contexts, relationships, semantic_relationships)
        
        logger.info("Step 6: Generating C4 diagrams...")
        self._generate_diagrams()
        
        logger.info("Step 7: Exporting results...")
        self._export_results()
        
        logger.info("Done! C4 diagrams generated in: %s", self.output_dir)
    
    def _parse_all_files(self, structure: RepositoryStructure) -> List[Component]:
        """Парсинг всех файлов"""
        
        components = []
        
        # Docker files
        for dockerfile in structure.docker_files:
            try:
                component = self.dockerfile_parser.parse(dockerfile)
                components.append(component)
            except Exception as e:
                logger.warning(f"Failed to parse {dockerfile}: {e}")
        
        # Kubernetes files
        for k8s_file in structure.kubernetes_files:
            try:
                k8s_components = self.k8s_parser.parse(k8s_file)
                components.extend(k8s_components)
            except Exception as e:
                logger.warning(f"Failed to parse {k8s_file}: {e}")
        
        # Terraform files
        for tf_file in structure.terraform_files:
            try:
                tf_components = self.terraform_parser.parse(tf_file)
                components.extend(tf_components)
            except Exception as e:
                logger.warning(f"Failed to parse {tf_file}: {e}")
        
        # Source code
        for lang, files in structure.source_code.items():
            if lang == 'python':
                for py_file in files[:10]:  # Ограничиваем для примера
                    try:
                        code_components = self.python_parser.parse(py_file)
                        components.extend(code_components)
                    except Exception as e:
                        logger.warning(f"Failed to parse {py_file}: {e}")
        
        return components
    
    def _extract_relationships(
        self, 
        structure: RepositoryStructure, 
        components: List[Component]
    ) -> List[Relationship]:
        """Извлечение связей"""
        
        relationships = []
        
        # Из исходного кода
        for lang, files in structure.source_code.items():
            if lang == 'python':
                for py_file in files[:10]:
                    try:
                        rels = self.python_parser.extract_dependencies(py_file)
                        relationships.extend(rels)
                    except Exception as e:
                        logger.warning(f"Failed to extract deps from {py_file}: {e}")
        
        # Из K8s манифестов (Service -> Deployment связи)
        relationships.extend(self._extract_k8s_relationships(structure.kubernetes_files))
        
        # Из Docker Compose
        relationships.extend(self._extract_docker_compose_relationships(structure.docker_files))
        
        return relationships
    
    def _extract_k8s_relationships(self, k8s_files: List[Path]) -> List[Relationship]:
        """Извлечение связей из K8s манифестов"""
        relationships = []
        
        # Парсим все манифесты
        services = {}
        deployments = {}
        
        for k8s_file in k8s_files:
            try:
                with open(k8s_file) as f:
                    manifests = list(yaml.safe_load_all(f))
                
                for manifest in manifests:
                    if not manifest:
                        continue
                    
                    kind = manifest.get('kind')
                    name = manifest.get('metadata', {}).get('name')
                    
                    if kind == 'Service':
                        selector = manifest.get('spec', {}).get('selector', {})
                        services[name] = selector
                    elif kind == 'Deployment':
                        labels = manifest.get('spec', {}).get('template', {}).get('metadata', {}).get('labels', {})
                        deployments[name] = labels
            except Exception as e:
                logger.warning(f"Failed to extract K8s relationships from {k8s_file}: {e}")
        
        # Связываем Services с Deployments через селекторы
        for svc_name, selector in services.items():
            for deploy_name, labels in deployments.items():
                if all(labels.get(k) == v for k, v in selector.items()):
                    relationships.append(Relationship(
                        source=svc_name,
                        target=deploy_name,
                        type='routes_to',
                        protocol='kubernetes',
                        description=f'Service routes traffic to deployment'
                    ))
        
        return relationships
    
    def _extract_docker_compose_relationships(self, docker_files: List[Path]) -> List[Relationship]:
        """Извлечение связей из docker-compose"""
        relationships = []
        
        for docker_file in docker_files:
            if 'docker-compose' not in docker_file.name:
                continue
            
            try:
                with open(docker_file) as f:
                    compose = yaml.safe_load(f)
                
                services = compose.get('services', {})
                
                for service_name, service_config in services.items():
                    # depends_on
                    depends_on = service_config.get('depends_on', [])
                    for dep in depends_on:
                        relationships.append(Relationship(
                            source=service_name,
                            target=dep,
                            type='depends_on',
                            protocol='docker',
                            description='Service dependency'
                        ))
                    
                    # links
                    links = service_config.get('links', [])
                    for link in links:
                        target = link.split(':')[0]
                        relationships.append(Relationship(
                            source=service_name,
                            target=target,
                            type='links_to',
                            protocol='docker',
                            description='Network link'
                        ))
            except Exception as e:
                logger.warning(f"Failed to extract docker-compose relationships: {e}")
        
        return relationships
    
    def _build_knowledge_graph(
        self,
        components: List[Component],
        semantic_contexts: Dict[str, SemanticContext],
        relationships: List[Relationship],
        semantic_relationships: List[Dict]
    ):
        """Построение графа знаний"""
        
        # Добавляем компоненты
        for component in components:
            semantic_context = semantic_contexts.get(component.name)
            if semantic_context:
                self.knowledge_graph.add_component(component, semantic_context)
        
        # Добавляем связи
        for rel_data in semantic_relationships:
            relationship = rel_data['relationship']
            semantic_info = rel_data['semantic_info']
            self.knowledge_graph.add_relationship(relationship, semantic_info)
    
    def _generate_diagrams(self):
        """Генерация C4 диаграмм"""
        
        c4_generator = C4Generator(self.knowledge_graph)
        c4_generator.generate_all_diagrams(self.output_dir)
    
    def _export_results(self):
        """Экспорт результатов"""
        
        # Экспорт графа знаний
        graph_json = self.knowledge_graph.export_to_json()
        (self.output_dir / "knowledge_graph.json").write_text(graph_json)
        
        # Экспорт метрик
        criticality = self.knowledge_graph.calculate_criticality()
        metrics = {
            'component_criticality': criticality,
            'subsystems': [list(s) for s in self.knowledge_graph.detect_subsystems()],
            'entry_points': self.knowledge_graph.identify_entry_points(),
            'data_stores': self.knowledge_graph.identify_data_stores()
        }
        
        import json
        (self.output_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2)
        )

# Точка входа
def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Recover C4 architecture diagrams from code repository'
    )
    parser.add_argument('repo_path', type=Path, help='Path to repository')
    parser.add_argument('--llm-model', required=True, help='Path to LLM model')
    parser.add_argument('--model-type', default='llama', choices=['llama', 'mistral'])
    parser.add_argument('--output', type=Path, default=Path('./output'), help='Output directory')
    
    args = parser.parse_args()
    
    recovery = C4ArchitectureRecovery(
        repo_path=args.repo_path,
        llm_model_path=args.llm_model,
        output_dir=args.output,
        model_type=args.model_type
    )
    
    recovery.run()

if __name__ == '__main__':
    main()