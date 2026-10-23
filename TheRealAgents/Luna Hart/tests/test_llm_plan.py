#!/usr/bin/env python3
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from shared.llm_client import llm_call

prompt = "You are Luna Hart. Decide next content. Return JSON: {\"type\": \"x_post\", \"topic\": \"test\", \"style\": \"insight\", \"reason\": \"test\"}"

result = llm_call(prompt=prompt, model="deepseek/deepseek-v3.2", max_tokens=5000, temperature=0.7, timeout=30)
print("Length:", len(result) if result else 0)
print("Raw:", repr(result[:500]) if result else "EMPTY")

# Try parsing
try:
    parsed = json.loads(result)
    print("JSON parse OK:", parsed)
except json.JSONDecodeError as e:
    print("JSON parse failed:", e)
    # Try extracting JSON from markdown
    if "```json" in result:
        start = result.find("```json") + 7
        end = result.find("```", start)
        json_str = result[start:end].strip()
        try:
            parsed = json.loads(json_str)
            print("Extracted JSON OK:", parsed)
        except:
            print("Extraction also failed")
