"""
Agent_4 - Orchestrator

On-demand synthesis. When called, fetches signals and generates a brief.
Unlike Alex/Maya, Jamie doesn't run continuously - he's triggered by requests.
"""
import sys
import logging
from pathlib import Path
from typing import Optional

# Path setup
MAYA_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MAYA_DIR))

from app.config import load_config
from app.database.data_loader import fetch_signals_by_query
from app.synthesizer.brief_generator import generate_brief


class SynthesisOrchestrator:
    """Main orchestrator for on-demand brief synthesis."""
    
    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.logger = logging.getLogger(__name__)
    
    def synthesize(
        self,
        query: str,
        vertical: str = 'general',
        max_signals: int = None,
        min_urgency: float = 0.0,
        use_llm: bool = True,
    ) -> dict:
        """
        On-demand synthesis: fetch signals and generate a brief.
        
        Args:
            query: Search query string
            vertical: Which vertical to query (default: general)
            max_signals: Max number of signals to fetch (default from config)
            min_urgency: Minimum urgency threshold
            use_llm: Whether to use LLM for summary generation
        
        Returns:
            dict with brief data
        """
        if max_signals is None:
            max_signals = self.config.get('synthesis', {}).get('max_signals', 500)
        
        self.logger.info(f"Jamie synthesizing brief for query: '{query}'")
        
        # Fetch signals
        signals = fetch_signals_by_query(
            query=query,
            vertical=vertical,
            max_signals=max_signals,
            min_urgency=min_urgency,
        )
        
        # Generate brief
        brief = generate_brief(
            query=query,
            signals=signals,
            max_complaints=10,
            max_wants=10,
            use_llm=use_llm,
        )
        
        result = brief.to_dict()
        self.logger.info(f"Jamie complete: {len(signals)} signals, {brief.signal_count} in brief")
        
        return result


if __name__ == '__main__':
    # Command-line usage: python orchestrator.py "search query"
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent_4 - On-demand synthesis')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--vertical', default='general', help='Vertical (default: general)')
    parser.add_argument('--no-llm', action='store_true', help='Skip LLM for summary')
    
    args = parser.parse_args()
    
    config = load_config()
    orchestrator = SynthesisOrchestrator(config)
    
    result = orchestrator.synthesize(
        query=args.query,
        vertical=args.vertical,
        use_llm=not args.no_llm,
    )
    
    print(json.dumps(result, indent=2))
