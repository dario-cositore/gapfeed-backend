#!/usr/bin/env python3
"""
DRY RUN: Test 4 LLM models for YouTube pain classification
Compare scoring consistency on the same 10 comments
"""
import requests, json

KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

DOCUMENTS = [
    ("PAIN", "Stripe keeps freezing my account for no reason, I'm losing customers every day and can't even contact support"),
    ("PAIN", "Shopify checkout has been broken for 3 hours and I'm losing $500/hour in sales. This is unacceptable"),
    ("PAIN", "Worst customer support I've ever experienced. Sent 12 tickets over 2 months, zero responses. Absolutely terrible"),
    ("PAIN", "QuickBooks completely destroyed my accounting data during the last update. 3 years of records gone"),
    ("PAIN", "GoDaddy randomly charged me $400 for domain renewal. Hidden fees everywhere, absolute scam"),
    ("MID", "The pricing has gone up 3x in the last year, starting to look at alternatives"),
    ("MID", "Setup was confusing, took me 3 days to figure out the basic configuration"),
    ("NOT", "Really helpful video, thanks for sharing this!"),
    ("NOT", "I use this tool daily and it's saved me so much time"),
    ("NOT", "Great tutorial, can you cover integrations next?"),
]

MODELS = [
    "cohere/rerank-4-pro",
    "mistralai/mistral-small-2603",
    "openai/gpt-5.4-nano",
    "google/gemini-3.1-flash-lite-preview",
]

RESULTS = {}

for model in MODELS:
    print(f"\nTesting: {model}")
    
    try:
        if 'rerank' in model:
            # Cohere rerank endpoint
            r = requests.post(
                'https://openrouter.ai/api/v1/rerank',
                headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'},
                json={
                    'model': model,
                    'query': 'Real customer pain, complaint, or negative experience about a product or service. Something is broken, terrible, or causing problems.',
                    'documents': [d[1] for d in DOCUMENTS],
                    'top_n': len(DOCUMENTS)
                },
                timeout=30
            )
            
            if r.status_code == 200:
                data = r.json()
                # Results come back sorted by score
                results = data.get('results', [])
                scores = {}
                for item in results:
                    idx = item['index']
                    scores[idx] = item['relevance_score']
                # Sort by index
                RESULTS[model] = [scores.get(i, 0) for i in range(len(DOCUMENTS))]
                print(f'  ✅ OK — model: {data.get("model","?")}, cost: {data.get("usage",{}).get("cost",0)}')
            else:
                RESULTS[model] = ['ERROR']
                print(f'  ❌ Error {r.status_code}: {r.text[:100]}')
        else:
            # Chat completion models — batch classify
            doc_list = "\n".join([f'{i+1}. "{d[1]}"' for i, d in enumerate(DOCUMENTS)])
            prompt = f'''Rate each comment 0.00-1.00 for whether it expresses a real customer pain/complaint about a product or service:

{doc_list}

Return ONLY a JSON array of numbers, like [0.95, 0.80, 0.05, ...]'''
            
            r = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'},
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.0,
                    'max_tokens': 200,
                    'response_format': {'type': 'json_object'}
                },
                timeout=30
            )
            
            if r.status_code == 200:
                content = r.json()['choices'][0]['message']['content']
                # Parse scores from JSON
                try:
                    import re
                    arr_match = re.search(r'\[.*?\]', content, re.DOTALL)
                    if arr_match:
                        scores = json.loads(arr_match.group())
                        RESULTS[model] = [float(s) for s in scores]
                        print(f'  ✅ OK')
                    else:
                        RESULTS[model] = ['PARSE_ERROR']
                        print(f'  ❌ Parse error: {content[:150]}')
                except Exception as e:
                    RESULTS[model] = ['PARSE_ERROR']
                    print(f'  ❌ Parse error: {e} — {content[:150]}')
            else:
                RESULTS[model] = ['ERROR']
                print(f'  ❌ Error {r.status_code}: {r.text[:150]}')
                
    except Exception as e:
        RESULTS[model] = ['EXCEPTION']
        print(f'  ❌ Exception: {e}')

# Print comparison table
print("\n" + "="*100)
print(f"{'':<40}", end="")
for m in MODELS:
    short = m.split('/')[-1][:15]
    print(f" {short:>16}", end="")
print()
print("="*100)

for i, (label, text) in enumerate(DOCUMENTS):
    print(f"[{label}] {text[:45]:<45}", end="")
    for m in MODELS:
        scores = RESULTS.get(m, [])
        if i < len(scores) and isinstance(scores[i], (int, float)):
            print(f" {scores[i]:>16.4f}", end="")
        else:
            print(f" {str(scores[i])[:16]:>16}", end="")
    print()

print()
# Check discrimination: do PAIN scores > NOT scores?
print("=== DISCRIMINATION CHECK ===")
for m in MODELS:
    scores = RESULTS.get(m, [])
    if not scores or scores[0] == 'ERROR' or scores[0] == 'PARSE_ERROR':
        print(f"{m}: No valid data")
        continue
    
    pain_scores = [scores[i] for i in range(len(DOCUMENTS)) if DOCUMENTS[i][0] == "PAIN" and isinstance(scores[i], (int, float))]
    not_scores = [scores[i] for i in range(len(DOCUMENTS)) if DOCUMENTS[i][0] == "NOT" and isinstance(scores[i], (int, float))]
    mid_scores = [scores[i] for i in range(len(DOCUMENTS)) if DOCUMENTS[i][0] == "MID" and isinstance(scores[i], (int, float))]
    
    if pain_scores and not_scores:
        pain_avg = sum(pain_scores) / len(pain_scores)
        not_avg = sum(not_scores) / len(not_scores)
        mid_avg = sum(mid_scores) / len(mid_scores) if mid_scores else 0
        spread = pain_avg - not_avg
        
        print(f"{m}:")
        print(f"  PAIN avg: {pain_avg:.4f} | MID avg: {mid_avg:.4f} | NOT avg: {not_avg:.4f}")
        print(f"  Spread (PAIN - NOT): {spread:.4f} {'✅ GOOD' if spread > 0.2 else '⚠️ WEAK' if spread > 0.1 else '❌ FAILED'}")
    print()