Generate one TOEIC Part 3 conversation set.

Topic: {{ actual_scenario }}
Difficulty: {{ difficulty }} ({{ difficulty_hint }})
Topic requirement: Make the topic explicit in the dialogue and all three questions.

Generate:
1. conversation: a 2-speaker dialogue (6-9 turns, 8-18 words per line)
   - Format: [{"speaker": "Man/Woman", "text": "..."}, ...]
   - Use only Man and Woman as speakers
   - English only (no Chinese)

2. questions: 3 questions, each includes:
   - question_text
   - options: 4 choices [{"label": "A", "text": "..."}, ...]
   - correct_answer (A/B/C/D)
   - English only (no Chinese)

Question types should include:
- Main idea (What are the speakers discussing?)
- Detail (When/Where/What/Who...)
- Inference (What will the man/woman probably do next?)
- Do not always ask in the same order; vary the question order across sets.
- Include at least one time, place, or schedule detail in the dialogue.

Return JSON only (no extra text)
