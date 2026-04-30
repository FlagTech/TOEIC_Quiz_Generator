"""
TOEIC 測驗 PDF 生成模組

使用 reportlab 生成 TOEIC 測驗 PDF（題目本、答案卡）
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
    Frame,
    PageTemplate,
    Image,
    KeepTogether,
    FrameBreak,
    NextPageTemplate,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
from typing import List, Dict, Optional, Any
import os


class TOEICPDFGenerator:
    """TOEIC 測驗 PDF 生成器"""

    def __init__(self):
        try:
            font_path = "C:/Windows/Fonts/msjh.ttc"
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                self.chinese_font = 'ChineseFont'
            else:
                self.chinese_font = 'Helvetica'
        except Exception:
            self.chinese_font = 'Helvetica'

        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1E40AF'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName=self.chinese_font
        )
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1E40AF'),
            spaceAfter=12,
            spaceBefore=20,
            fontName=self.chinese_font
        )
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            fontName=self.chinese_font
        )
        self.part_title_full_style = ParagraphStyle(
            'PartTitleFull',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.black,
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        )
        self.directions_style = ParagraphStyle(
            'Directions',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=12,
            fontName=self.chinese_font
        )
        self.question_style = ParagraphStyle(
            'Question',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            fontName=self.chinese_font
        )
        self.option_style = ParagraphStyle(
            'Option',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=12,
            leftIndent=10,
            fontName=self.chinese_font
        )
        self.section_style = ParagraphStyle(
            'Section',
            parent=self.styles['Heading3'],
            fontSize=9,
            textColor=colors.HexColor("#374151"),
            spaceAfter=6,
            spaceBefore=8,
            fontName=self.chinese_font
        )
        self.passage_style = ParagraphStyle(
            'Passage',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=12,
            fontName=self.chinese_font
        )

    def _resolve_image_path(self, image_url: str) -> Optional[str]:
        if not image_url:
            return None
        if image_url.startswith("/images/part1/"):
            filename = image_url.replace("/images/part1/", "", 1)
            return os.path.join("data", "listening_images", filename)
        if os.path.exists(image_url):
            return image_url
        return None

    def _build_directions_box(self, text: str, width: float) -> Table:
        paragraph = Paragraph(text, self.directions_style)
        table = Table([[paragraph]], colWidths=[width])
        table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9CA3AF")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        table.hAlign = "LEFT"
        return table

    def _build_passage_box(self, text: str, width: float) -> Table:
        import re
        normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")

        has_markdown = bool(re.search(
            r'^#{1,6}\s|\*\*|__|\|.+\||\n\s*[-*+]\s',
            normalized, re.MULTILINE
        ))

        if not has_markdown:
            # Plain text path (original logic)
            raw_paras = [p.strip() for p in normalized.split("\n\n") if p.strip()]
            if not raw_paras:
                raw_paras = [normalized.strip() or ""]
            para_style = ParagraphStyle('PassageInner', parent=self.passage_style, spaceAfter=5)
            last_style = ParagraphStyle('PassageInnerLast', parent=self.passage_style, spaceAfter=0)
            rows = []
            for idx, p_text in enumerate(raw_paras):
                p_text = p_text.replace("\n", "<br/>")
                style = last_style if idx == len(raw_paras) - 1 else para_style
                rows.append([Paragraph(p_text, style)])
            table = Table(rows, colWidths=[width])
            n = len(rows)
            table.setStyle(TableStyle([
                ("BOX",           (0, 0),   (-1, -1),  1.4, colors.black),
                ("LEFTPADDING",   (0, 0),   (-1, -1),  10),
                ("RIGHTPADDING",  (0, 0),   (-1, -1),  10),
                ("TOPPADDING",    (0, 0),   (-1, -1),  0),
                ("BOTTOMPADDING", (0, 0),   (-1, -1),  0),
                ("TOPPADDING",    (0, 0),   (0, 0),    8),
                ("BOTTOMPADDING", (0, n-1), (0, n-1),  8),
            ]))
            return table

        # Markdown path
        inner_width = width - 20  # account for L/R padding
        lines = normalized.split('\n')
        row_items = []  # list of ReportLab flowables (one per Table row)
        i = 0

        h_size = {1: 12, 2: 11, 3: 10}

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            # Horizontal rule
            if re.match(r'^[-*_]{3,}$', stripped):
                row_items.append(
                    HRFlowable(width=inner_width, thickness=0.5,
                               color=colors.HexColor('#9CA3AF'),
                               spaceBefore=2, spaceAfter=2)
                )
                i += 1
                continue

            # Markdown table
            if stripped.startswith('|') and stripped.count('|') >= 2:
                tbl_lines = []
                while i < len(lines) and '|' in lines[i]:
                    tbl_lines.append(lines[i])
                    i += 1
                md_tbl = self._parse_md_table(tbl_lines, inner_width)
                if md_tbl:
                    row_items.append(md_tbl)
                continue

            # Heading
            m = re.match(r'^(#{1,3})\s+(.+)', stripped)
            if m:
                level = len(m.group(1))
                content = self._inline_md(m.group(2))
                fs = h_size.get(level, 10)
                h_style = ParagraphStyle(
                    f'MdH{level}_{id(self)}',
                    parent=self.passage_style,
                    fontSize=fs,
                    spaceBefore=4,
                    spaceAfter=2,
                )
                row_items.append(Paragraph(f'<b>{content}</b>', h_style))
                i += 1
                continue

            # Bullet list item (possibly nested)
            m = re.match(r'^(\s*)([-*+])\s+(.+)', line)
            if m:
                indent = len(m.group(1)) // 2
                content = self._inline_md(m.group(3))
                b_style = ParagraphStyle(
                    f'MdBullet_{indent}_{id(self)}',
                    parent=self.passage_style,
                    leftIndent=8 + indent * 12,
                    firstLineIndent=0,
                    spaceBefore=1,
                    spaceAfter=1,
                )
                row_items.append(Paragraph(f'• {content}', b_style))
                i += 1
                continue

            # Numbered list
            m = re.match(r'^(\s*)(\d+)\.\s+(.+)', line)
            if m:
                indent = len(m.group(1)) // 2
                num = m.group(2)
                content = self._inline_md(m.group(3))
                n_style = ParagraphStyle(
                    f'MdNum_{indent}_{id(self)}',
                    parent=self.passage_style,
                    leftIndent=8 + indent * 12,
                    spaceBefore=1,
                    spaceAfter=1,
                )
                row_items.append(Paragraph(f'{num}. {content}', n_style))
                i += 1
                continue

            # Regular paragraph — collect lines until a block boundary
            para_lines = []
            while i < len(lines):
                l = lines[i]
                s = l.strip()
                if not s:
                    break
                if re.match(r'^(#{1,6}\s|\s*[-*+]\s|\s*\d+\.\s)', s):
                    break
                if s.startswith('|') and s.count('|') >= 2:
                    break
                if re.match(r'^[-*_]{3,}$', s):
                    break
                para_lines.append(l.strip())
                i += 1

            if para_lines:
                para_text = ' '.join(para_lines)
                row_items.append(Paragraph(self._inline_md(para_text), self.passage_style))

        if not row_items:
            row_items.append(Paragraph('', self.passage_style))

        rows = [[item] for item in row_items]
        n = len(rows)
        table = Table(rows, colWidths=[width])
        table.setStyle(TableStyle([
            ("BOX",           (0, 0),   (-1, -1),  1.4, colors.black),
            ("LEFTPADDING",   (0, 0),   (-1, -1),  10),
            ("RIGHTPADDING",  (0, 0),   (-1, -1),  10),
            ("TOPPADDING",    (0, 0),   (-1, -1),  2),
            ("BOTTOMPADDING", (0, 0),   (-1, -1),  2),
            ("TOPPADDING",    (0, 0),   (0, 0),    8),
            ("BOTTOMPADDING", (0, n-1), (0, n-1),  8),
        ]))
        return table

    def _format_passage_text(self, text: str) -> str:
        # 保留供外部呼叫相容；_build_passage_box 已自行處理換行
        return (text or "").replace("\r\n", "\n").replace("\r", "\n")

    def _build_divider(self, width: float) -> HRFlowable:
        return HRFlowable(
            width=width,
            thickness=0.6,
            color=colors.HexColor("#9CA3AF"),
            spaceBefore=5,
            spaceAfter=5
        )

    def _inline_md(self, text: str) -> str:
        """Convert inline Markdown to ReportLab XML tags."""
        import re
        text = text.replace('&', '&amp;')
        # Bold **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # Bold __text__
        text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
        # Italic *text* (single asterisk only)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
        return text

    def _parse_md_table(self, table_lines: list, inner_width: float):
        """Convert Markdown table lines to a ReportLab Table."""
        import re
        rows_data = []
        is_header_row = True
        header_count = 0
        for line in table_lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Separator row (e.g. |---|---|)
            if re.match(r'^[\s|:=-]+$', stripped):
                is_header_row = False
                continue
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            cell_style = ParagraphStyle(
                'MdTblCell',
                parent=self.passage_style,
                fontSize=8,
                leading=11,
                spaceAfter=0,
            )
            row = [Paragraph(self._inline_md(c), cell_style) for c in cells]
            rows_data.append((row, is_header_row))
            if is_header_row:
                header_count += 1

        if not rows_data:
            return None

        n_cols = max(len(r) for r, _ in rows_data)
        col_w = inner_width / n_cols
        data = [r for r, _ in rows_data]

        tbl = Table(data, colWidths=[col_w] * n_cols)
        style_cmds = [
            ('GRID',          (0, 0), (-1, -1), 0.5,  colors.HexColor('#9CA3AF')),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]
        if header_count:
            style_cmds += [
                ('BACKGROUND', (0, 0), (-1, header_count - 1), colors.HexColor('#E5E7EB')),
                ('FONTNAME',   (0, 0), (-1, header_count - 1), 'Helvetica-Bold'),
            ]
        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    def _add_answer_table(self, story: list, answers: list) -> list:
        for i in range(0, len(answers), 10):
            chunk = answers[i:i + 10]
            row1 = [str(a[0]) for a in chunk]
            row2 = [a[1] for a in chunk]
            table = Table([row1, row2], colWidths=[50] * len(chunk))
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E5E7EB')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(table)
            story.append(Spacer(1, 10))
        return story

    def generate_questions_only_pdf(self, test_data: dict, output_path: str) -> str:
        doc = BaseDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        column_gap = 8 * mm
        col_width = (doc.width - column_gap) / 2
        left_frame = Frame(doc.leftMargin, doc.bottomMargin, col_width, doc.height, id="left")
        right_frame = Frame(doc.leftMargin + col_width + column_gap, doc.bottomMargin, col_width, doc.height, id="right")
        full_frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="full")
        doc.addPageTemplates([
            PageTemplate(id="Cover", frames=[full_frame]),
            PageTemplate(id="TwoCol", frames=[left_frame, right_frame]),
            PageTemplate(id="FullPage", frames=[full_frame]),
        ])

        def build_question_block(question_text: str, options: List[Dict[str, str]], spacer_height: float = 12) -> List[Any]:
            parts = [Paragraph(question_text, self.question_style)]
            for opt in options:
                parts.append(Paragraph(f"{opt['label']}. {opt['text']}", self.option_style))
            parts.append(Spacer(1, spacer_height))
            return [KeepTogether(parts)]

        story = []

        # 封面
        story.append(Paragraph("TOEIC Practice Test", self.title_style))
        story.append(Paragraph(f"Difficulty: {test_data.get('difficulty', 'medium').upper()}", self.normal_style))
        story.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", self.normal_style))
        story.append(Spacer(1, 30))
        story.append(Paragraph("Total Questions: 200", self.normal_style))
        story.append(Paragraph("Listening: 100 questions", self.normal_style))
        story.append(Paragraph("Reading: 100 questions", self.normal_style))
        story.append(NextPageTemplate("TwoCol"))

        directions = {
            "part1": "Directions: For each question in this part, you will hear four statements about a picture in your test book. When you hear the statements, you must select the one statement that best describes what you see in the picture. Then find the number of the question on your answer sheet and mark your answer. The statements will not be printed in your test book and will be spoken only one time.",
            "part2": "Directions: You will hear a question or statement and three responses spoken in English. They will be spoken only one time and will not be printed in your test book. Select the best response to each question or statement and mark the letter (A), (B), or (C) on your answer sheet.",
            "part3": "Directions: You will hear some conversations between two or more people. You will be asked to answer three questions about what the speakers say in each conversation. Select the best response to each question and mark the letter (A), (B), (C), or (D) on your answer sheet. The conversations will not be printed in your test book and will be spoken only one time.",
            "part4": "Directions: You will hear some short talks given by a single speaker. You will be asked to answer three questions about what the speaker says in each talk. Select the best response to each question and mark the letter (A), (B), (C), or (D) on your answer sheet. The talks will be spoken only one time and will not be printed on your test book.",
            "part5": "Directions: A word or phrase is missing in each of the sentences below. Four answer choices are given below each sentence. Select the best answer to complete the sentence. Then mark the letter (A), (B), (C), or (D) on your answer sheet.",
            "part6": "Directions: Read the texts that follow. A word, phrase, or sentence is missing in parts of each text. Four answer choices for each question are given below the text. Select the best answer to complete the text. Then mark the letter (A), (B), (C), or (D) on your answer sheet.",
            "part7": "Directions: In this part you will read a selection of texts, such as magazine and newspaper articles, e-mails, and instant messages. Each text or set of texts is followed by several questions. Select the best answer for each question and mark the letter (A), (B), (C), or (D) on your answer sheet.",
        }

        part_offsets = {
            "part1": 1, "part2": 7, "part3": 32, "part4": 71,
            "part5": 1, "part6": 31, "part7": 47,
        }

        # ── LISTENING TEST ──
        story.append(NextPageTemplate("TwoCol"))
        story.append(PageBreak())
        story.append(Paragraph("LISTENING TEST", self.heading_style))
        story.append(Spacer(1, 10))

        # Part 1
        story.append(Paragraph("<b>Part 1: Photographs<br/>(6 questions)</b>", self.part_title_full_style))
        story.append(self._build_directions_box(directions["part1"], col_width))
        story.append(Spacer(1, 16))
        part1_questions = test_data.get('part1_questions', [])
        img_width = col_width * 0.9
        images_on_page = 0
        for i, q in enumerate(part1_questions):
            q_num = part_offsets["part1"] + i
            if q_num == 3:
                story.append(Spacer(1, 227))
            image_path = self._resolve_image_path(q.get("image_url"))
            if image_path and os.path.exists(image_path):
                reader = ImageReader(image_path)
                raw_w, raw_h = reader.getSize()
                if raw_w <= 0 or raw_h <= 0:
                    raw_w, raw_h = (1, 1)
                img_h = img_width * raw_h / raw_w
                story.append(KeepTogether([
                    Paragraph(f"<font name=\"Helvetica-Bold\">{q_num}.</font>", self.question_style),
                    Spacer(1, 4),
                    Image(image_path, width=img_width, height=img_h),
                    Spacer(1, 10),
                ]))
            else:
                story.append(KeepTogether([
                    Paragraph(f"<font name=\"Helvetica-Bold\">{q_num}.</font> [Image not available]", self.question_style),
                    Spacer(1, 10),
                ]))
            images_on_page += 1
            if images_on_page == 4 and i < len(part1_questions) - 1:
                story.append(PageBreak())
                images_on_page = 0

        # Part 2
        story.append(FrameBreak())
        story.append(Paragraph("<b>Part 2: Question-Response<br/>(25 questions)</b>", self.part_title_full_style))
        story.append(self._build_directions_box(directions["part2"], col_width))
        story.append(Spacer(1, 16))
        for i in range(len(test_data.get("part2_questions", []))):
            num = part_offsets["part2"] + i
            story.append(Paragraph(f"<font name=\"Helvetica-Bold\">{num}.</font> Mark your answer on your answer sheet.", self.question_style))
            story.append(Spacer(1, 6))

        # Part 3
        story.append(PageBreak())
        story.append(Paragraph("<b>Part 3: Conversations<br/>(39 questions)</b>", self.part_title_full_style))
        story.append(self._build_directions_box(directions["part3"], col_width))
        story.append(Spacer(1, 16))
        q_num = part_offsets["part3"]
        for conv in test_data.get('part3_questions', []):
            for sub_q in conv.get('questions', []):
                story.extend(build_question_block(
                    f"<font name=\"Helvetica-Bold\">{q_num}.</font> {sub_q['question_text']}",
                    sub_q['options'], spacer_height=10
                ))
                q_num += 1
            story.append(self._build_divider(col_width))
            story.append(Spacer(1, 8))

        # Part 4
        story.append(PageBreak())
        story.append(Paragraph("<b>Part 4: Talks<br/>(30 questions)</b>", self.part_title_full_style))
        story.append(self._build_directions_box(directions["part4"], col_width))
        story.append(Spacer(1, 16))
        q_num = part_offsets["part4"]
        for talk in test_data.get('part4_questions', []):
            for sub_q in talk.get('questions', []):
                story.extend(build_question_block(
                    f"<font name=\"Helvetica-Bold\">{q_num}.</font> {sub_q['question_text']}",
                    sub_q['options'], spacer_height=10
                ))
                q_num += 1
            story.append(self._build_divider(col_width))
            story.append(Spacer(1, 8))

        # ── READING TEST ──
        story.append(NextPageTemplate("TwoCol"))
        story.append(PageBreak())
        story.append(Paragraph("READING TEST", self.heading_style))
        story.append(Spacer(1, 10))

        # Part 5
        story.append(Paragraph("<b>Part 5: Incomplete Sentences<br/>(30 questions)</b>", self.part_title_full_style))
        story.append(self._build_directions_box(directions["part5"], col_width))
        story.append(Spacer(1, 16))
        for i, q in enumerate(test_data.get('part5_questions', [])):
            q_num = part_offsets["part5"] + i
            story.extend(build_question_block(
                f"<font name=\"Helvetica-Bold\">{q_num}.</font> {q['question_text']}",
                q['options'], spacer_height=12
            ))

        # Part 6
        part6_questions = test_data.get('part6_questions', [])
        group_size = 4
        if part6_questions:
            story.append(PageBreak())
            story.append(Paragraph("<b>Part 6: Text Completion<br/>(16 questions)</b>", self.part_title_full_style))
            story.append(self._build_directions_box(directions["part6"], col_width))
            story.append(Spacer(1, 16))
        for group_index in range(0, len(part6_questions), group_size):
            group = part6_questions[group_index:group_index + group_size]
            if not group:
                continue
            start_num = part_offsets["part6"] + group_index
            end_num = start_num + len(group) - 1
            passage_text = next(
                (q.get("question_text") for q in group
                 if q.get("question_text") and q.get("question_text") not in ["[同一篇文章]", "[同組文章]"]),
                ""
            )
            passage_style_label = group[0].get("passage_style") or "text"
            header_block = [
                Paragraph(f"Questions {start_num}-{end_num} refer to the following {passage_style_label}.", self.section_style)
            ]
            if passage_text:
                header_block.append(self._build_passage_box(self._format_passage_text(passage_text), col_width))
                header_block.append(Spacer(1, 8))
            story.append(KeepTogether(header_block))
            for i, q in enumerate(group):
                q_num = start_num + i
                blank_pos = q.get("blank_position", "")
                blank_label = f" (Blank {blank_pos})" if blank_pos else ""
                story.extend(build_question_block(
                    f"<font name=\"Helvetica-Bold\">{q_num}.</font>{blank_label}",
                    q['options'], spacer_height=12
                ))

        # Part 7 — 先收集兩種資料，再決定是否印標題
        part7_single = test_data.get('part7_single_questions', [])
        part7_multiple = test_data.get('part7_multiple_questions', [])

        single_groups: List[Dict[str, Any]] = []
        for q in part7_single:
            passage = q.get("passage")
            if not single_groups or single_groups[-1]["passage"] != passage:
                single_groups.append({"passage": passage, "questions": []})
            single_groups[-1]["questions"].append(q)

        multiple_groups: List[Dict[str, Any]] = []
        for q in part7_multiple:
            passages = q.get("passages") or []
            key = tuple(passages)
            if not multiple_groups or multiple_groups[-1]["key"] != key:
                multiple_groups.append({"key": key, "passages": passages, "questions": []})
            multiple_groups[-1]["questions"].append(q)

        if single_groups or multiple_groups:
            story.append(PageBreak())
            story.append(Paragraph("<b>Part 7: Reading Comprehension<br/>(54 questions)</b>", self.part_title_full_style))
            story.append(self._build_directions_box(directions["part7"], col_width))
            story.append(Spacer(1, 16))

        q_num = part_offsets["part7"]
        for group in single_groups:
            questions = group["questions"]
            if not questions:
                continue
            start_num = q_num
            end_num = q_num + len(questions) - 1
            passage_style_label = questions[0].get("passage_style") or "text"
            header_block = [
                Paragraph(f"Questions {start_num}-{end_num} refer to the following {passage_style_label}.", self.section_style)
            ]
            if group["passage"]:
                header_block.append(self._build_passage_box(self._format_passage_text(group["passage"]), col_width))
                header_block.append(Spacer(1, 8))
            story.append(KeepTogether(header_block))
            for q in questions:
                story.extend(build_question_block(
                    f"<font name=\"Helvetica-Bold\">{q_num}.</font> {q['question_text']}",
                    q['options'], spacer_height=12
                ))
                q_num += 1

        for group in multiple_groups:
            questions = group["questions"]
            if not questions:
                continue
            start_num = q_num
            end_num = q_num + len(questions) - 1
            passage_style_label = questions[0].get("passage_style") or "text"
            header_block = [
                Paragraph(f"Questions {start_num}-{end_num} refer to the following {passage_style_label}.", self.section_style)
            ]
            for p_idx, passage in enumerate(group["passages"]):
                header_block.append(Paragraph(f"Passage {p_idx + 1}", self.question_style))
                header_block.append(self._build_passage_box(self._format_passage_text(passage), col_width))
                header_block.append(Spacer(1, 6))
            story.append(KeepTogether(header_block))
            for q in questions:
                story.extend(build_question_block(
                    f"<font name=\"Helvetica-Bold\">{q_num}.</font> {q['question_text']}",
                    q['options'], spacer_height=12
                ))
                q_num += 1

        doc.build(story)
        return output_path

    def generate_reading_only_pdf(self, test_data: dict, output_path: str) -> str:
        doc = BaseDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        column_gap = 8 * mm
        col_width = (doc.width - column_gap) / 2
        left_frame = Frame(doc.leftMargin, doc.bottomMargin, col_width, doc.height, id="left")
        right_frame = Frame(doc.leftMargin + col_width + column_gap, doc.bottomMargin, col_width, doc.height, id="right")
        full_frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="full")
        doc.addPageTemplates([
            PageTemplate(id="Cover", frames=[full_frame]),
            PageTemplate(id="TwoCol", frames=[left_frame, right_frame]),
        ])

        def build_question_block(question_text: str, options: List[Dict[str, str]], spacer_height: float = 12) -> List[Any]:
            parts = [Paragraph(question_text, self.question_style)]
            for opt in options:
                parts.append(Paragraph(f"{opt['label']}. {opt['text']}", self.option_style))
            parts.append(Spacer(1, spacer_height))
            return [KeepTogether(parts)]

        story = []

        # 封面
        story.append(Paragraph("TOEIC Reading Test", self.title_style))
        story.append(Paragraph(f"Difficulty: {test_data.get('difficulty', 'medium').upper()}", self.normal_style))
        story.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", self.normal_style))
        story.append(Spacer(1, 30))
        story.append(Paragraph("Total Questions: 100", self.normal_style))
        story.append(Paragraph("Part 5  Incomplete Sentences: Q1–Q30", self.normal_style))
        story.append(Paragraph("Part 6  Text Completion: Q31–Q46", self.normal_style))
        story.append(Paragraph("Part 7  Reading Comprehension: Q47–Q100", self.normal_style))
        story.append(NextPageTemplate("TwoCol"))
        story.append(PageBreak())

        directions = {
            "part5": "Directions: A word or phrase is missing in each of the sentences below. Four answer choices are given below each sentence. Select the best answer to complete the sentence. Then mark the letter (A), (B), (C), or (D) on your answer sheet.",
            "part6": "Directions: Read the texts that follow. A word, phrase, or sentence is missing in parts of each text. Four answer choices for each question are given below the text. Select the best answer to complete the text. Then mark the letter (A), (B), (C), or (D) on your answer sheet.",
            "part7": "Directions: In this part you will read a selection of texts, such as magazine and newspaper articles, e-mails, and instant messages. Each text or set of texts is followed by several questions. Select the best answer for each question and mark the letter (A), (B), (C), or (D) on your answer sheet.",
        }

        # 題號範圍（閱讀測驗 1–100）
        part5_start = 1
        part6_start = 31
        part7_start = 47

        # ── Part 5 ──
        story.append(Paragraph("READING TEST", self.heading_style))
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Part 5: Incomplete Sentences<br/>(30 questions)</b>", self.part_title_full_style))
        story.append(self._build_directions_box(directions["part5"], col_width))
        story.append(Spacer(1, 16))
        for i, q in enumerate(test_data.get('part5_questions', [])):
            q_num = part5_start + i
            story.extend(build_question_block(
                f"<font name=\"Helvetica-Bold\">{q_num}.</font> {q.get('question_text', '')}",
                q['options'], spacer_height=12
            ))

        # ── Part 6 ──
        part6_questions = test_data.get('part6_questions', [])
        group_size = 4
        if part6_questions:
            story.append(PageBreak())
            story.append(Paragraph("<b>Part 6: Text Completion<br/>(16 questions)</b>", self.part_title_full_style))
            story.append(self._build_directions_box(directions["part6"], col_width))
            story.append(Spacer(1, 16))
        for group_index in range(0, len(part6_questions), group_size):
            group = part6_questions[group_index:group_index + group_size]
            if not group:
                continue
            start_num = part6_start + group_index
            end_num = start_num + len(group) - 1
            # question_text 存的是完整段落（第一題），後續為 "[同一篇文章]"
            passage_text = next(
                (q.get("question_text") for q in group
                 if q.get("question_text") and q.get("question_text") not in ["[同一篇文章]", "[同組文章]"]),
                ""
            )
            # fallback：若 question_text 為空則嘗試 passage 欄位
            if not passage_text:
                passage_text = next(
                    (q.get("passage") for q in group
                     if q.get("passage") and q.get("passage") not in ["[同一篇文章]", "[同組文章]"]),
                    ""
                )
            passage_style_label = group[0].get("passage_style") or "text"
            header_block = [
                Paragraph(
                    f"Questions {start_num}–{end_num} refer to the following {passage_style_label}.",
                    self.section_style
                )
            ]
            if passage_text:
                header_block.append(self._build_passage_box(self._format_passage_text(passage_text), col_width))
                header_block.append(Spacer(1, 8))
            story.append(KeepTogether(header_block))
            for i, q in enumerate(group):
                q_num = start_num + i
                blank_pos = q.get("blank_position", i + 1)
                story.extend(build_question_block(
                    f"<font name=\"Helvetica-Bold\">{q_num}.</font> (Blank {blank_pos})",
                    q['options'], spacer_height=12
                ))
            story.append(self._build_divider(col_width))
            story.append(Spacer(1, 8))

        # ── Part 7 ──
        part7_single = test_data.get('part7_single_questions', [])
        part7_multiple = test_data.get('part7_multiple_questions', [])

        single_groups: List[Dict[str, Any]] = []
        for q in part7_single:
            passage = q.get("passage")
            if not single_groups or single_groups[-1]["passage"] != passage:
                single_groups.append({"passage": passage, "questions": []})
            single_groups[-1]["questions"].append(q)

        multiple_groups: List[Dict[str, Any]] = []
        for q in part7_multiple:
            passages = q.get("passages") or []
            key = tuple(passages)
            if not multiple_groups or multiple_groups[-1]["key"] != key:
                multiple_groups.append({"key": key, "passages": passages, "questions": []})
            multiple_groups[-1]["questions"].append(q)

        if single_groups or multiple_groups:
            story.append(PageBreak())
            story.append(Paragraph("<b>Part 7: Reading Comprehension<br/>(54 questions)</b>", self.part_title_full_style))
            story.append(self._build_directions_box(directions["part7"], col_width))
            story.append(Spacer(1, 16))

        q_num = part7_start
        for group in single_groups:
            questions = group["questions"]
            if not questions:
                continue
            start_num = q_num
            end_num = q_num + len(questions) - 1
            passage_style_label = questions[0].get("passage_style") or "text"
            header_block = [
                Paragraph(
                    f"Questions {start_num}–{end_num} refer to the following {passage_style_label}.",
                    self.section_style
                )
            ]
            if group["passage"]:
                header_block.append(self._build_passage_box(self._format_passage_text(group["passage"]), col_width))
                header_block.append(Spacer(1, 8))
            story.append(KeepTogether(header_block))
            for q in questions:
                story.extend(build_question_block(
                    f"<font name=\"Helvetica-Bold\">{q_num}.</font> {q.get('question_text', '')}",
                    q['options'], spacer_height=12
                ))
                q_num += 1

        for group in multiple_groups:
            questions = group["questions"]
            if not questions:
                continue
            start_num = q_num
            end_num = q_num + len(questions) - 1
            passage_style_label = questions[0].get("passage_style") or "text"
            header_block = [
                Paragraph(
                    f"Questions {start_num}–{end_num} refer to the following {passage_style_label}.",
                    self.section_style
                )
            ]
            for p_idx, passage in enumerate(group["passages"]):
                header_block.append(Paragraph(f"Passage {p_idx + 1}", self.question_style))
                header_block.append(self._build_passage_box(self._format_passage_text(passage), col_width))
                header_block.append(Spacer(1, 6))
            story.append(KeepTogether(header_block))
            for q in questions:
                story.extend(build_question_block(
                    f"<font name=\"Helvetica-Bold\">{q_num}.</font> {q.get('question_text', '')}",
                    q['options'], spacer_height=12
                ))
                q_num += 1

        doc.build(story)
        return output_path

    def generate_answer_key_pdf(self, test_data: dict, output_path: str) -> str:
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        story = []

        story.append(Paragraph("TOEIC Practice Test - Answer Key", self.title_style))
        story.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", self.normal_style))
        story.append(Spacer(1, 20))

        offsets = {
            "part1": 1, "part2": 7, "part3": 32, "part4": 71,
            "part5": 1, "part6": 31, "part7": 47,
        }
        answers = []

        for i, q in enumerate(test_data.get('part1_questions', [])):
            answers.append((offsets["part1"] + i, q.get('correct_answer', ''), 'Part 1'))

        for i, q in enumerate(test_data.get('part2_questions', [])):
            answers.append((offsets["part2"] + i, q.get('correct_answer', ''), 'Part 2'))

        q_num = offsets["part3"]
        for conv in test_data.get('part3_questions', []):
            for ans in conv.get('correct_answers', []):
                answers.append((q_num, ans, 'Part 3'))
                q_num += 1

        q_num = offsets["part4"]
        for talk in test_data.get('part4_questions', []):
            for ans in talk.get('correct_answers', []):
                answers.append((q_num, ans, 'Part 4'))
                q_num += 1

        for i, q in enumerate(test_data.get('part5_questions', [])):
            answers.append((offsets["part5"] + i, q.get('correct_answer', ''), 'Part 5'))

        for i, q in enumerate(test_data.get('part6_questions', [])):
            answers.append((offsets["part6"] + i, q.get('correct_answer', ''), 'Part 6'))

        q_num = offsets["part7"]
        for q in test_data.get('part7_single_questions', []):
            answers.append((q_num, q.get('correct_answer', ''), 'Part 7'))
            q_num += 1

        for q in test_data.get('part7_multiple_questions', []):
            answers.append((q_num, q.get('correct_answer', ''), 'Part 7'))
            q_num += 1

        listening_parts = {'Part 1', 'Part 2', 'Part 3', 'Part 4'}
        listening_answers = [a for a in answers if a[2] in listening_parts]
        reading_answers = [a for a in answers if a[2] not in listening_parts]

        all_answers = listening_answers + reading_answers
        story = self._add_answer_table(story, all_answers)

        doc.build(story)
        return output_path


def generate_toeic_pdf(
    test_data: dict,
    export_mode: str,
    output_dir: str = "data/pdf_exports"
) -> str:
    import zipfile
    os.makedirs(output_dir, exist_ok=True)
    generator = TOEICPDFGenerator()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    has_listening = bool(
        test_data.get('part1_questions') or test_data.get('part2_questions') or
        test_data.get('part3_questions') or test_data.get('part4_questions')
    )

    if export_mode == 'questions_only':
        output_path = os.path.join(output_dir, f"TOEIC_Questions_{timestamp}.pdf")
        if has_listening:
            return generator.generate_questions_only_pdf(test_data, output_path)
        return generator.generate_reading_only_pdf(test_data, output_path)

    elif export_mode == 'answer_key':
        output_path = os.path.join(output_dir, f"TOEIC_Answer_Key_{timestamp}.pdf")
        return generator.generate_answer_key_pdf(test_data, output_path)

    elif export_mode == 'both':
        questions_path = os.path.join(output_dir, f"TOEIC_Questions_{timestamp}.pdf")
        answer_key_path = os.path.join(output_dir, f"TOEIC_Answer_Key_{timestamp}.pdf")

        if has_listening:
            generator.generate_questions_only_pdf(test_data, questions_path)
        else:
            generator.generate_reading_only_pdf(test_data, questions_path)
        generator.generate_answer_key_pdf(test_data, answer_key_path)

        zip_path = os.path.join(output_dir, f"TOEIC_Export_{timestamp}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(questions_path, f"TOEIC_Questions_{timestamp}.pdf")
            zf.write(answer_key_path, f"TOEIC_Answer_Key_{timestamp}.pdf")

        os.remove(questions_path)
        os.remove(answer_key_path)
        return zip_path

    else:
        raise ValueError(f"不支援的匯出模式: {export_mode}")
