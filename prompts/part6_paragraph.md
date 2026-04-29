You are a professional TOEIC item writer. Create ONE TOEIC Reading Part 6 (Text Completion) passage with {{ count }} blanks.
{{ topic_instruction }}{{ style_instruction }}
Difficulty: {{ difficulty_desc }}

Part 6 rules:
- Write one complete business passage (about 150-200 words).
- Include {{ count }} numbered blanks: (1)_____, (2)_____, ... up to ({{ count }})_____.
- Each blank has four options with exactly one correct answer.
- Test grammar, cohesion, vocabulary, and context.
- Format requirement: write the passage as Markdown inside the JSON string and preserve its paragraph and document structure.
- If the passage style is something structured such as a notice, memo, form, schedule, or invoice, use Markdown formatting that reflects the layout instead of flattening everything into one line.
Topic requirement: The random topic must be central to the passage; avoid generic contexts.
Style requirement: Ensure the passage style is a natural fit for the topic and clearly reflected in the writing.
Variety requirement: Ensure blanks cover different skills (connector, verb tense/voice, word form, sentence insertion or reference).
Output requirement: Set passage_style to the final chosen style.

Output JSON only:
- Root object with key "questions" (array).
- Each item has: question_number, question_type ("paragraph"), passage_style, question_text (full passage), blank_position, options (A-D), correct_answer.
- All {{ count }} questions must refer to the same full passage text.
- Include the full passage in every question_text (no placeholders).
- `question_text` must contain the full Markdown-formatted passage with its structure preserved.
- Return valid JSON with double-quoted strings only.
