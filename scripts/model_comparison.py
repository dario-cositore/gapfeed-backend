#!/usr/bin/env python3
"""Compare 4 models on the same signal classification task."""
import sqlite3, json, requests, re, time

LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

MODELS = [
    ('google/gemini-2.5-flash-lite', '$0.078/M'),
    ('qwen/qwen3-coder', '$0'),
    ('z-ai/glm-4.5-air', '$0.040/M'),
    ('qwen/qwen3-coder-flash', '$0'),
]

# Get 50 random signals with content
conn = sqlite3.connect(LIVE)
signals = conn.execute('''
    SELECT id, source, title, content FROM signals 
    WHERE length(content) >= 100
    ORDER BY RANDOM()
    LIMIT 30
''').fetchall()

print(f"Testing {len(signals)} signals across 4 models\n")
print("="*80)

results = {}
for model_name, cost in MODELS:
    print(f"\nTesting: {model_name} ({cost})")
    print("-" * 60)
    
    pain_count = 0
    noise_count = 0
    errors = 0
    scores = []
    start = time.time()
    
    for sid, source, title, content in signals:
        text = (title or '') + ' ' + (content or '')
        text = text[:200].replace('"', '\\"')
        
        prompt = f'Is this customer pain/complaint? "{text}" Return 1.0 for YES, 0.0 for NO:'
        
        try:
            r = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {KEY}'},
                json={
                    'model': model_name,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.0,
                    'max_tokens': 10
                },
                timeout=30
            )
            
            if r.status_code == 200:
                response = r.json()['choices'][0]['message']['content']
                m = re.search(r'([01]\.?[0]?)', response)
                if m:
                    match = m.group(1)
                    if match in ['1', '1.0', '1.00']:
                        score = 1.0
                    elif match in ['0', '0.0', '0.00']:
                        score = 0.0
                    else:
                        score = 0.0
                        errors += 1
                else:
                    score = 0.0
                    errors += 1
                
                scores.append(score)
                if score >= 0.5:
                    pain_count += 1
                else:
                    noise_count += 1
            else:
                errors += 1
                print(f"  Error {r.status_code}")
                
        except Exception as e:
            errors += 1
            if errors < 3:
                print(f"  Exception: {e}")
        
        time.sleep(0.2)
    
    elapsed = time.time() - start
    pain_pct = pain_count / len(signals) * 100
    
    results[model_name] = {
        'pain': pain_count,
        'noise': noise_count,
        'errors': errors,
        'pain_pct': pain_pct,
        'elapsed': elapsed,
        'cost': cost,
        'scores': scores
    }
    
    print(f"  Pain: {pain_count}/{len(signals)} ({pain_pct:.1f}%)")
    print(f"  Errors: {errors}")
    print(f"  Time: {elapsed:.1f}s")

print("\n" + "="*80)
print("COMPARISON TABLE")
print("="*80)
print(f"{'Model':<35} {'Pain%':>7} {'Time':>7} {'Errors':>7} {'Cost':>10}")
print("-" * 80)

for model_name, cost in MODELS:
    r = results[model_name]
    print(f"{model_name:<35} {r['pain_pct']:>6.1f}% {r['elapsed']:>6.1f}s {r['errors']:>6} {r['cost']:>12}")

print("\n" + "="*80)
print("AGREEMENT MATRIX (vs Gemini baseline)")
print("="*80)
print(f"{'Model':<35} {'Agree':>7} {'Disagree':>9}")
print("-" * 80)

gemini_scores = results['google/gemini-2.5-flash-lite']['scores']
for model_name, cost in MODELS[1:]:
    scores = results[model_name]['scores']
    agree = sum(1 for a, b in zip(gemini_scores, scores) if a == b)
    disagree = len(gemini_scores) - agree
    agreement_pct = agree / len(gemini_scores) * 100
    print(f"{model_name:<35} {agree:>5} ({agreement_pct:.0f}%) {disagree:>5} ({100-agreement_pct:.0f}%)")

print("\n" + "="*80)
print("SAMPLE DISAGREEMENTS")
print("="*80)
disagreements = []
for model_name, _ in MODELS[1:]:
    scores = results[model_name]['scores']
    for i, sig in enumerate(signals):
        if results[model_name]['scores'][i] != results['google/gemini-2.5-flash-lite']['scores'][i]:
            disagreements.append((model_name, sig[2][:60], results['google/gemini-2.5-flash-lite']['scores'][i], results[model_name]['scores'][i]))

for i, (model, title, gemini, other) in enumerate(disagreements[:10]):
    print(f"  {i+1}. {model}")
    print(f"     Title: {title}")
    print(f"     Gemini: {gemini} vs {model.split('/')[-1]}: {other}")
    print()

conn.close()
