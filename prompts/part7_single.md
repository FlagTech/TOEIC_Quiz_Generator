You are a professional TOEIC item writer. Create ONE TOEIC Reading Part 7 (Single Passage) set with {{ count }} questions.
{{ topic_instruction }}{{ style_instruction }}
Difficulty: {{ difficulty_desc }}

Part 7 Single Passage rules:
- Provide one complete passage (100-200 words).
- Use realistic formats: email, advertisement, notice, memo, article, schedule, or invoice.
- Include {{ count }} questions covering detail, main idea, inference, vocabulary, or negative fact.
- Format requirement: write the passage as Markdown inside the JSON string and preserve its paragraph and document structure.
- For structured documents such as invoices, notices, schedules, memos, and emails, reflect the layout with Markdown instead of flattening all content into a single line.
- When appropriate, you may use Markdown headings, bullet lists, numbered lists, or simple tables if they help the passage look realistic and readable.
Topic requirement: The random topic must be central to the passage and questions; avoid generic contexts.
Style requirement: Ensure the passage style is a natural fit for the topic and clearly reflected in the writing.
Variety requirement: Include at least one main-idea or purpose question and one inference question when possible.
Output requirement: Set passage_style to the final chosen style.

Output JSON only:
- Root object with key "questions" (array).
- Each item has: question_number, question_type ("single_passage"), passage_style, passage, question_text, options (A-D), correct_answer.
- All {{ count }} questions share the same full passage.
- Include the full passage in every question's passage field (no placeholders).
- `passage` must contain the full Markdown-formatted document with its structure preserved.
- Return valid JSON with double-quoted strings only.
