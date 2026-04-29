You are a professional TOEIC item writer. Create a TOEIC Reading Part 7 (Multiple Passages) set with {{ passage_count }} related passages and {{ count }} questions.
{{ topic_instruction }}{{ style_instruction }}
Difficulty: {{ difficulty_desc }}

Part 7 Multiple Passages rules:
- Provide {{ passage_count }} related passages (80-150 words each).
- Passages must be logically connected (e.g., email exchange, notice + reply, ad + schedule).
- Include {{ count }} questions covering single-passage and cross-passage comprehension.
- Format requirement: write each passage as Markdown inside the JSON string and preserve its paragraph and document structure.
- For structured documents such as invoices, notices, schedules, memos, and emails, reflect the layout with Markdown instead of flattening all content into a single line.
- When appropriate, you may use Markdown headings, bullet lists, numbered lists, or simple tables if they help the passages look realistic and readable.
Topic requirement: The random topic must be central to the passages and questions; avoid generic contexts.
Style requirement: Ensure the passage style is a natural fit for the topic and clearly reflected in the writing.
Variety requirement: Include at least one cross-passage question and one inference question when possible.
Output requirement: Set passage_style to the final chosen style.

Output JSON only:
- Root object with key "questions" (array).
- Each item has: question_number, question_type ("multiple_passage"), passage_style, passages (array), question_text, options (A-D), correct_answer.
- All {{ count }} questions must share the same passages array (full texts).
- Include the full passages in every question (no placeholders).
- Each `passages` item must contain full Markdown-formatted text with its structure preserved.
- Return valid JSON with double-quoted strings only.
