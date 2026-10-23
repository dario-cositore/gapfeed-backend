#!/usr/bin/env python3
"""
COST DRY TEST - Compare Gemini models for pain classification
Tests 3 models on the same 20 sample signals to compare accuracy vs cost
"""
import sqlite3, requests, json, re, time

KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

# Test documents - mix of real pain and non-pain
TEST_DOCS = [
    # PAIN (should be 1.0)
    ("PAIN", "Stripe keeps freezing my account and I can't access my money. Losing customers every day."),
    ("PAIN", "Shopify checkout broke for 3 hours, I lost $500/hour in sales. Unacceptable."),
    ("PAIN", "Worst customer support. Sent 12 tickets, no response for 2 months."),
    ("PAIN", "QuickBooks destroyed my accounting data. 3 years gone. Ruined."),
    ("PAIN", "GoDaddy charged me $400 hidden fees. Absolute scam."),
    ("PAIN", "AWS support is non-existent, cluster went down at 2AM, no help available."),
    ("PAIN", "MongoDB Atlas charged $2000 surprise bill, can't reach anyone to dispute it"),
    ("PAIN", "Claude API keeps timing out on simple prompts, unreliable"),
    ("PAIN", "Notion crashed and lost 50 pages of work today, again."),
    ("PAIN", "Clerky charged me $1500 for 10 minutes of work, then ghosted me"),
    # NOT PAIN (should be 0.0)
    ("NOT", "Great tutorial! Very helpful for understanding the basics."),
    ("NOT", "I use this tool every day, saved me so much time."),
    ("NOT", "Love the new features in the latest update."),
    ("NOT", "Thanks for sharing this, really appreciate it."),
    ("NOT", "The documentation is excellent, very clear and thorough."),
    ("NOT", "Best customer support I've ever had. Fast and helpful."),
    ("NOT", "This tool is amazing, exactly what I needed."),
    ("NOT", "Setup was easy, everything just worked."),
    ("NOT", "Can you cover integrations in the next video?"),
    ("NOT", "I recommend this to all my colleagues, great product."),
]

MODELS = [
    ("google/gemini-3.1-flash-lite-preview", "3.1"),
    ("google/gemini-2.5-flash-lite-preview-09-2025", "2.5-preview"),
    ("google/gemini-2.5-flash-lite", "2.5"),
]

RESULTS = {}

for model, label in MODELS:
    print(f"\nTesting: {label} ({model})")
    
    # Build prompt with sample docs
    numbered = '\n'.join([f'{i+1}. "{text[:200]}..."' for i, (_, text) in enumerate(TEST_DOCS)])
    prompt = f'''Rate each comment 0.0 or 1.0 for whether it expresses a real customer pain/complaint about a product or service.
1.0 = real pain, complaint, or negative experience
0.0 = neutral, positive, or irrelevant

{numbered}

Return ONLY a JSON array of numbers, like [0.0, 1.0, 0.0, 0.0, 1.0, ...].'''

    try:
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
            resp = r.json()
            content = resp['choices'][0]['message']['content']
            arr = re.search(r'\[([01.,\s]+)\]', content, re.DOTALL)
            
            if arr:
                scores = [float(x.strip()) for x in arr.group(1).split(',') if x.strip()]
                
                # Calculate accuracy
                correct = 0
                for i, (expected, _) in enumerate(TEST_DOCS):
                    if i < len(scores):
                        pred = 1.0 if scores[i] >= 0.5 else 0.0
                        actual = 1.0 if expected == "PAIN" else 0.0
                        if pred == actual:
                            correct += 1
                
                accuracy = correct / len(TEST_DOCS)
                
                # Cost estimate (OpenRouter pricing)
                # 3.1 is ~$0.00002 per 1K tokens for input, $0.00004 for output
                # 2.5 is cheaper - estimates based on standard Gemini pricing
                cost_per_1K = {
                    "3.1": 0.00006,  # input+output estimate
                    "2.5-preview": 0.00004,
                    "2.5": 0.00003,
                }
                
                # Rough cost estimate for this test (each doc ~50 chars = ~50 tokens)
                estimated_cost = len(TEST_DOCS) * 50 / 1000 * cost_per_1K[label]
                
                print(f"  Accuracy: {accuracy*100:.1f}%")
                print(f"  Cost/1K: ${cost_per_1K[label]:.5f}")
                print(f"  Est. cost for this run: ${estimated_cost:.4f}")
                
                RESULTS[label] = {
                    'accuracy': accuracy,
                    'cost_per_1k': cost_per_1K[label],
                    'scores': scores
                }
            else:
                print(f"  ERROR: Could not parse scores from response")
        else:
            print(f"  ERROR: API returned {r.status_code}")

    except Exception as e:
        print(f"  ERROR: {e}")
    
    time.sleep(1)

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
for label, data in RESULTS.items():
    print(f"{label:20} | Accuracy: {data['accuracy']*100:>5.1f}% | Cost/1K: ${data['cost_per_1k']:.5f}")

print("\n" + "="*60)
print("RECOMMENDATION")
print("="*60)

if RESULTS:
    best_cost_eff = min(RESULTS.items(), key=lambda x: x[1]['cost_per_1k'] / x[1]['accuracy'])
    best_acc = max(RESULTS.items(), key=lambda x: x[1]['accuracy'])
    
    print(f"Best cost-efficiency: {best_cost_eff[0]} ({best_cost_eff[1]['accuracy']*100:.1f}% accuracy, ${best_cost_eff[1]['cost_per_1k']:.5f}/1K)")
    print(f"Best accuracy: {best_acc[0]} ({best_acc[1]['accuracy']*100:.1f}% accuracy)")
    
    # Calculate potential savings
    if '3.1' in RESULTS:
        current_cost = RESULTS['3.1']['cost_per_1k']
        cheaper_cost = best_cost_eff[1]['cost_per_1k']
        saving = ((current_cost - cheaper_cost) / current_cost) * 100
        print(f"\nSwitching to {best_cost_eff[0]} could save ~{saving:.1f}% on costs")
else:
    print("No results collected")
