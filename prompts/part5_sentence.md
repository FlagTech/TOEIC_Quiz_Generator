You are a professional TOEIC item writer. Generate {{ count }} TOEIC Reading Part 5 (Incomplete Sentences) questions.
{{ topic_instruction }}
Difficulty: {{ difficulty_desc }}

Part 5 rules:
- Each question has one blank in a single sentence.
- Test grammar, vocabulary, or usage.
- Provide four options with exactly one correct answer.
- Use TOEIC-style business or daily-life contexts.
Topic requirement: The random topic must be central to each sentence; avoid generic contexts.
Variety requirement: Mix grammar points (tense, prepositions, word forms, conjunctions, pronouns) across questions.

Output JSON only (no markdown, no extra text):
- Root object with key "questions" (array).
- Each item has: question_number, question_type ("sentence"), question_text, options (A-D), correct_answer.

Requirements:
- Distractors are plausible but only one option is correct.
- Return valid JSON with double-quoted strings.
- Do not include markdown or any extra text.
