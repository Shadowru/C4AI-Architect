# main.py
import argparse
import logging
from pathlib import Path
import yaml
import sys

from src.scanner.repository_scanner import RepositoryScanner
from src.analyzer.semantic_analyzer import SemanticAnalyzer
from src.analyzer.llm_engine import LLMEngine
from src.generator.c4_model_builder import C4ModelBuilder
from src.renderer.plantuml_renderer import PlantUMLRenderer

def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('c4_recovery.log', encoding='utf-8')
        ]
    )

def load_config(config_path: str) -> dict:
    """Загружает конфигурацию из файла"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logging.warning(f"Config file {config_path} not found, using defaults")
        return {
            'ollama': {
                'base_url': 'http://localhost:11434',
                'model': 'codellama:13b'
            }
        }

def main():
    parser = argparse.ArgumentParser(
        description='C4 Architecture Recovery System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py /path/to/repo
  python main.py /path/to/repo -o ./output -v
  python main.py /path/to/repo --model llama2:13b
        """
    )
    parser.add_argument('repo_path', help='Path to repository')
    parser.add_argument('--output', '-o', default='./output', help='Output directory')
    parser.add_argument('--config', '-c', default='./config/config.yaml', help='Config file')
    parser.add_argument('--model', '-m', default='codellama:13b', help='Ollama model')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--skip-llm', action='store_true', help='Skip LLM analysis (faster, less detailed)')
    
    args = parser.parse_args()
    
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Проверяем путь к репозиторию
        repo_path = Path(args.repo_path)
        if not repo_path.exists():
            logger.error(f"Repository path does not exist: {args.repo_path}")
            return 1
        
        # Загружаем конфигурацию
        config = load_config(args.config)
        
        # Инициализация компонентов
        logger.info("=" * 60)
        logger.info("C4 Architecture Recovery System")
        logger.info("=" * 60)
        
        logger.info(f"Repository: {args.repo_path}")
        logger.info(f"Output: {args.output}")
        logger.info(f"Model: {args.model}")
        
        # Инициализация LLM
        logger.info("\nInitializing LLM Engine...")
        llm_engine = LLMEngine(
            model=args.model,
            base_url=config.get('ollama', {}).get('base_url', 'http://localhost:11434')
        )
        
        # Сканирование репозитория
        logger.info("\nScanning repository...")
        scanner = RepositoryScanner(args.repo_path)
        structure = scanner.scan()
        
        logger.info(f"Found files:")
        logger.info(f"  - Code files: {sum(len(files) for files in structure.code_files.values())}")
        for lang, files in structure.code_files.items():
            logger.info(f"    - {lang}: {len(files)}")
        logger.info(f"  - Docker files: {len(structure.docker_files)}")
        logger.info(f"  - Kubernetes files: {len(structure.k8s_files)}")
        logger.info(f"  - Terraform files: {len(structure.terraform_files)}")
        
        # Семантический анализ
        logger.info("\nPerforming semantic analysis...")
        analyzer = SemanticAnalyzer(llm_engine)
        analysis = analyzer.analyze(structure)
        
        logger.info(f"Analysis complete:")
        logger.info(f"  - Containers found: {len(analysis.get('containers', []))}")
        logger.info(f"  - Components found: {len(analysis.get('components', []))}")
        logger.info(f"  - Dependencies: {len(analysis.get('dependencies', []))}")
        
        # Построение C4 модели
        logger.info("\nBuilding C4 model...")
        builder = C4ModelBuilder(analyzer, llm_engine)
        repo_name = Path(args.repo_path).name
        c4_model = builder.build(analysis, repo_name)
        
        # Рендеринг диаграмм
        logger.info("\nRendering diagrams...")
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        
        renderer = PlantUMLRenderer(output_path)
        diagram_files = renderer.render_all(c4_model)
        
        # Результаты
        logger.info("\n" + "=" * 60)
        logger.info("SUCCESS! C4 diagrams generated")
        logger.info("=" * 60)
        
        logger.info(f"\nGenerated {len(diagram_files)} diagrams:")
        for file in diagram_files:
            logger.info(f"  ✓ {file}")
        
        logger.info(f"\nC4 Model Summary:")
        logger.info(f"  - Systems: {len(c4_model.systems)}")
        logger.info(f"  - Containers: {len(c4_model.containers)}")
        logger.info(f"  - Components: {len(c4_model.components)}")
        logger.info(f"  - Relationships: {len(c4_model.relationships)}")
        
        # Insights
        insights = analysis.get('insights', {})
        if insights.get('patterns'):
            patterns = insights['patterns']
            logger.info(f"\nArchitecture Patterns:")
            for pattern in patterns.get('patterns', [])[:3]:
                logger.info(f"  - {pattern}")
        
        logger.info(f"\nOutput directory: {output_path.absolute()}")
        logger.info("\nTo view diagrams:")
        logger.info("  1. Install PlantUML: https://plantuml.com/download")
        logger.info("  2. Open .puml files with PlantUML viewer")
        logger.info("  3. Or use online: https://www.plantuml.com/plantuml/")
        
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())