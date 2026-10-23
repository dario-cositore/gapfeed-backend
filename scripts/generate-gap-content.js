// scripts/generate-gap-content.js
import Database from 'better-sqlite3';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

const DB_PATH = 'gapfeed_unified.db'; // ← Change if your DB path is different
const db = new Database(DB_PATH);

const LLM_API_KEY = process.env.LLM_API_KEY; // Set in terminal or .env
const LLM_ENDPOINT = 'https://api.anthropic.com/v1/messages'; // Claude 4.6 Sonnet
// For Gemini fallback: change to OpenRouter or Google endpoint

async function callLLM(prompt, system) {
  const response = await fetch(LLM_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': LLM_API_KEY,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model: "claude-4-6-sonnet-2026-04", // or claude-3-5-sonnet-20241022 for cheaper
      max_tokens: 1200,
      temperature: 0.7,
      system: system,
      messages: [{ role: "user", content: prompt }]
    })
  });
  const data = await response.json();
  return data.content[0].text;
}

async function generateHighQualityGap(gap) {
  // Fetch real signals/quotes for this gap
  const signals = db.prepare(`
    SELECT content, source, url FROM signals 
    WHERE gap_id = ? AND content IS NOT NULL 
    ORDER BY RANDOM() LIMIT 12
  `).all(gap.id);

  const realQuotes = signals.map(s => s.content).join('\n\n');

  // Step 1: Draft
  const draftSystem = `You are a sharp startup founder explaining a real market opportunity to a friend over coffee. Be direct, human, and specific. Never sound like corporate AI.`;
  const draftPrompt = `Gap title so far: ${gap.title}
Real user quotes (use these verbatim where possible):\n${realQuotes}

Write:
- A sharp, natural title (max 12 words)
- A 2-4 sentence description that explains who's hurting, what they tried, what they do instead, and why it sucks
- One sentence "Why now" (timing/context)
- List of 3-6 most affected personas
- List of failed tools / substitutes mentioned in the quotes`;

  let draft = await callLLM(draftPrompt, draftSystem);

  // Step 2: Critique
  const critiquePrompt = `Critique this draft for generic AI language, weak quotes, vagueness, or corporate tone. Be brutal.\n\n${draft}`;
  const critique = await callLLM(critiquePrompt, "You are an extremely harsh editor.");

  // Step 3: Polish
  const polishPrompt = `Rewrite the following draft using the critique. Make it sharp, human, founder-to-founder tone. Use real quotes where they fit naturally.\n\nDraft:\n${draft}\n\nCritique:\n${critique}`;
  const finalContent = await callLLM(polishPrompt, draftSystem);

  return { ...gap, enriched_content: finalContent };
}

async function runEngine(mode = 'cheap') {
  console.log(`🚀 Running Gap Content Engine (${mode} mode)...`);

  const gaps = db.prepare(`SELECT * FROM gaps WHERE status = 'active' ORDER BY heat_score DESC LIMIT 100`).all();

  const enriched = [];
  for (const gap of gaps) {
    console.log(`Processing gap ${gap.id}...`);
    const result = await generateHighQualityGap(gap);
    enriched.push(result);
  }

  // Write back to data.json
  const dataDir = join(process.cwd(), 'public/data');
  if (!existsSync(dataDir)) mkdirSync(dataDir, { recursive: true });

  const output = { gaps: enriched, stats: { signals: 39509, gaps: enriched.length } };
  writeFileSync(join(dataDir, 'data.json'), JSON.stringify(output, null, 2));

  console.log(`✅ Engine finished. ${enriched.length} high-quality gaps generated.`);
  db.close();
}

runEngine('premium'); // Change to 'cheap' for normal runs
