"""
Jamie Rivera — On-Demand Brief Synthesizer
Entry point: python -m app.main

This agent synthesizes briefs on-demand when triggered (from Flask API or CLI).

Usage:
    python -m app.main "search query"          # Synthesize brief
    python -m app.main "aws" --vertical general
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# Path setup
JAMIE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(JAMIE_ROOT))

from app.config import load_config
from app.orchestrator import SynthesisOrchestrator


def setup_logging():
    """Configure logging."""
    log_format = '[%(asctime)s] [Jamie Rivera] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        stream=sys.stdout,
    )


def main():
    parser = argparse.ArgumentParser(description='Jamie Rivera - On-demand Brief Synthesizer')
    parser.add_argument('query', nargs='?', help='Search query (optional)')
    parser.add_argument('--vertical', default='general', help='Vertical (default: general)')
    parser.add_argument('--no-llm', action='store_true', help='Skip LLM for summary')
    parser.add_argument('--test', action='store_true', help='Run test synthesis')
    
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    config = load_config()
    orchestrator = SynthesisOrchestrator(config)
    
    if args.test or not args.query:
        # Test mode: generate sample brief
        logger.info("Running test synthesis...")
        result = orchestrator.synthesize(
            query='aws' if args.test else 'test',
            vertical=args.vertical,
            use_llm=not args.no_llm,
        )
    else:
        # On-demand synthesis
        result = orchestrator.synthesize(
            query=args.query,
            vertical=args.vertical,
            use_llm=not args.no_llm,
        )
    
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
