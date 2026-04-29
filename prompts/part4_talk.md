Generate one TOEIC Part 4 talk set.

Topic: {{ actual_topic }}
Difficulty: {{ difficulty }} ({{ difficulty_hint }})
Topic requirement: Make the topic explicit in the talk and all three questions.

Generate:
1. talk: a short monologue (6-9 sentences, ~70-120 words)
   - Clear opening, details in the middle, closing or call to action
   - English only (no Chinese)

2. questions: 3 questions, each includes:
   - question_text
   - options: 4 choices [{"label": "A", "text": "..."}, ...]
   - correct_answer (A/B/C/D)
   - English only (no Chinese)

Question types should include:
- Speaker/purpose (Who is the speaker? / What is the purpose?)
- Detail (When/Where/What...)
- Action (What are listeners asked to do?)
- Do not always ask in the same order; vary the question order across sets.
- Include at least one concrete action or instruction for the listener.

Return JSON only (no extra text)
