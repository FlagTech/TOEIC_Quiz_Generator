Generate one TOEIC Part 2 Q&A item.

Difficulty: {{ difficulty }} ({{ difficulty_hint }})
{{ topic_instruction }}
Topic requirement: The random topic must be the core of the Q&A; avoid generic scenarios.
Generate:
1. question: a single question or statement (WH / Yes-No / suggestion, etc.)
2. options: 3 response options (A, B, C), each with label and text
   - Randomly order one correct response and two distractors
   - Mark which is correct via correct_answer
3. correct_answer: the label (A, B, or C) of the correct option

Requirements:
- Use TOEIC business/daily contexts{{ topic_context }}
- Responses must be natural and context-appropriate
- Distractors should be misleading (keyword overlap, similar sound, irrelevant reply, etc.)
- Keep each response within 8-16 words
- Output must be English only (no Chinese)
- Randomly order the options (correct answer can be A, B, or C)

Return JSON only (no extra text)
