"""
TOEIC 測驗 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends
from backend.schemas import (
    TOEICGenerateRequest,
    TOEICQuizResponse,
    TOEICExplainRequest,
    TOEICExplanation,
    ListeningTestGenerateRequest,
    ListeningTestResponse,
    ListeningTestJobStatus,
    ReadingTestGenerateRequest,
    ReadingTestResponse,
    ReadingTestJobStatus,
    QuizJobStatus,
    QuizJobResult,
    QuizFolderCreateRequest,
    QuizFolderUpdateRequest,
    QuizFolderResponse,
    QuizLogCreateRequest,
    QuizLogUpdateRequest,
    QuizLogSummary,
    QuizLogDetail,
    PDFExportRequest,
)
from typing import List, Dict, Optional, Any
from fastapi.responses import FileResponse
from datetime import datetime
import json
import re
import asyncio
import threading
import uuid
import os
import hashlib
from backend.database import SessionLocal, get_db
from backend.models import QuizJob, QuizFolder, QuizLog
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/toeic", tags=["toeic"])

# 記憶體內任務儲存（服務重啟後會清空）
toeic_quiz_jobs: Dict[str, Dict[str, Any]] = {}
listening_test_jobs: Dict[str, Dict[str, Any]] = {}
reading_test_jobs: Dict[str, Dict[str, Any]] = {}

# 聽力測驗各 Part 預期題數
LISTENING_TEST_EXPECTED_COUNTS = {
    "part1": 6,
    "part2": 25,
    "part3": 13,
    "part4": 10,
}

# 閱讀測驗各 Part 預期題數
READING_TEST_EXPECTED_COUNTS = {
    "part5": 30,
    "part6": 16,
    "part7_single": 29,
    "part7_multiple": 25,
}


def _init_listening_test_progress() -> Dict[str, Any]:
    """初始化聽力測驗進度"""
    return {
        "part1": "pending",
        "part2": "pending",
        "part3": "pending",
        "part4": "pending",
        "part1_index": 0,
        "part2_index": 0,
        "part3_index": 0,
        "part4_index": 0,
    }


def _init_reading_test_progress() -> Dict[str, Any]:
    """初始化閱讀測驗進度"""
    return {
        "part5": "pending",
        "part6": "pending",
        "part7_single": "pending",
        "part7_multiple": "pending",
        "part5_index": 0,
        "part6_index": 0,
        "part7_single_index": 0,
        "part7_multiple_index": 0,
    }


def _ensure_listening_test_result(result: Any, difficulty: Optional[str]) -> Dict[str, Any]:
    """確保聽力測驗結果結構正確"""
    if result is None:
        result = {}
    elif hasattr(result, "model_dump"):
        result = result.model_dump()

    if not isinstance(result, dict):
        result = {}

    result.setdefault("difficulty", difficulty or "medium")
    result.setdefault("total_count", 0)
    result.setdefault("part1_questions", [])
    result.setdefault("part2_questions", [])
    result.setdefault("part3_questions", [])
    result.setdefault("part4_questions", [])
    return result


def _ensure_reading_test_result(result: Any, difficulty: Optional[str]) -> Dict[str, Any]:
    """確保閱讀測驗結果結構正確"""
    if result is None:
        result = {}
    elif hasattr(result, "model_dump"):
        result = result.model_dump()

    if not isinstance(result, dict):
        result = {}

    result.setdefault("difficulty", difficulty or "medium")
    result.setdefault("total_count", 0)
    result.setdefault("part5_questions", [])
    result.setdefault("part6_questions", [])
    result.setdefault("part7_single_questions", [])
    result.setdefault("part7_multiple_questions", [])
    return result


def _update_listening_test_total_count(result: Dict[str, Any]) -> None:
    """更新聽力測驗總題數"""
    part1 = len(result.get("part1_questions", []))
    part2 = len(result.get("part2_questions", []))
    part3 = len(result.get("part3_questions", [])) * 3
    part4 = len(result.get("part4_questions", [])) * 3
    result["total_count"] = part1 + part2 + part3 + part4


def _update_reading_test_total_count(result: Dict[str, Any]) -> None:
    """更新閱讀測驗總題數"""
    part5 = len(result.get("part5_questions", []))
    part6 = len(result.get("part6_questions", []))
    part7_single = len(result.get("part7_single_questions", []))
    part7_multiple = len(result.get("part7_multiple_questions", []))
    result["total_count"] = part5 + part6 + part7_single + part7_multiple


def _serialize_quiz_result(result: Any) -> Optional[str]:
    if result is None:
        return None
    data = result.model_dump() if hasattr(result, "model_dump") else result
    return json.dumps(data, ensure_ascii=False)


def _persist_listening_test_job(job_id: str) -> None:
    """持久化聽力測驗任務到資料庫"""
    job = listening_test_jobs.get(job_id)
    if not job:
        return
    db = SessionLocal()
    try:
        record = db.get(QuizJob, job_id)
        if not record:
            record = QuizJob(job_id=job_id)
        record.job_type = "listening"
        record.test_mode = None
        record.status = job.get("status")
        record.message = job.get("message")
        record.progress_json = json.dumps(job.get("progress") or {}, ensure_ascii=False)
        record.created_at = job.get("created_at")
        record.completed_at = job.get("completed_at")
        record.result_json = _serialize_quiz_result(job.get("result"))
        db.add(record)
        db.commit()
    finally:
        db.close()


def _persist_reading_test_job(job_id: str) -> None:
    """持久化閱讀測驗任務到資料庫"""
    job = reading_test_jobs.get(job_id)
    if not job:
        return
    db = SessionLocal()
    try:
        record = db.get(QuizJob, job_id)
        if not record:
            record = QuizJob(job_id=job_id)
        record.job_type = "reading"
        record.test_mode = None
        record.status = job.get("status")
        record.message = job.get("message")
        record.progress_json = json.dumps(job.get("progress") or {}, ensure_ascii=False)
        record.created_at = job.get("created_at")
        record.completed_at = job.get("completed_at")
        record.result_json = _serialize_quiz_result(job.get("result"))
        db.add(record)
        db.commit()
    finally:
        db.close()


def _persist_toeic_quiz_job(job_id: str) -> None:
    job = toeic_quiz_jobs.get(job_id)
    if not job:
        return
    db = SessionLocal()
    try:
        record = db.get(QuizJob, job_id)
        if not record:
            record = QuizJob(job_id=job_id)
        record.job_type = "reading"
        record.test_mode = job.get("test_mode")
        record.status = job.get("status")
        record.message = job.get("message")
        record.progress_json = json.dumps(job.get("progress") or {}, ensure_ascii=False)
        record.created_at = job.get("created_at")
        record.completed_at = job.get("completed_at")
        record.result_json = _serialize_quiz_result(job.get("result"))
        db.add(record)
        db.commit()
    finally:
        db.close()


def _load_toeic_quiz_job(job_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        record = db.get(QuizJob, job_id)
        if not record:
            return None
        progress = {}
        if record.progress_json:
            try:
                progress = json.loads(record.progress_json)
            except json.JSONDecodeError:
                progress = {}
        result = None
        if record.result_json:
            try:
                result = json.loads(record.result_json)
            except json.JSONDecodeError:
                result = None
        return {
            "status": record.status,
            "progress": progress,
            "message": record.message,
            "created_at": record.created_at,
            "completed_at": record.completed_at,
            "result": result,
            "test_mode": record.test_mode,
        }
    finally:
        db.close()


def _quiz_log_to_summary(record: QuizLog) -> QuizLogSummary:
    score = None
    if record.score_json:
        try:
            score = json.loads(record.score_json)
        except json.JSONDecodeError:
            score = None
    return QuizLogSummary(
        id=record.id,
        mode=record.mode,
        title=record.title,
        count=record.count,
        difficulty=record.difficulty,
        folder_id=record.folder_id,
        created_at=record.created_at,
        score=score,
    )


def _quiz_log_to_detail(record: QuizLog) -> QuizLogDetail:
    payload = None
    if record.payload_json:
        try:
            payload = json.loads(record.payload_json)
        except json.JSONDecodeError:
            payload = None
    summary = _quiz_log_to_summary(record)
    return QuizLogDetail(**summary.model_dump(), payload=payload)


def _load_listening_test_job(job_id: str) -> Optional[Dict[str, Any]]:
    """從資料庫載入聽力測驗任務"""
    db = SessionLocal()
    try:
        record = db.get(QuizJob, job_id)
        if not record or record.job_type != "listening":
            return None
        progress = {}
        if record.progress_json:
            try:
                progress = json.loads(record.progress_json)
            except json.JSONDecodeError:
                progress = {}
        result = None
        if record.result_json:
            try:
                result = json.loads(record.result_json)
            except json.JSONDecodeError:
                result = None
        return {
            "status": record.status,
            "progress": progress,
            "message": record.message,
            "created_at": record.created_at,
            "completed_at": record.completed_at,
            "result": result,
        }
    finally:
        db.close()


def _load_reading_test_job(job_id: str) -> Optional[Dict[str, Any]]:
    """從資料庫載入閱讀測驗任務"""
    db = SessionLocal()
    try:
        record = db.get(QuizJob, job_id)
        if not record or record.job_type != "reading":
            return None
        progress = {}
        if record.progress_json:
            try:
                progress = json.loads(record.progress_json)
            except json.JSONDecodeError:
                progress = {}
        result = None
        if record.result_json:
            try:
                result = json.loads(record.result_json)
            except json.JSONDecodeError:
                result = None
        return {
            "status": record.status,
            "progress": progress,
            "message": record.message,
            "created_at": record.created_at,
            "completed_at": record.completed_at,
            "result": result,
        }
    finally:
        db.close()


def clean_json_response(text: str) -> str:
    """
    清理 AI 回應，提取 JSON 內容

    Args:
        text: AI 回應文字

    Returns:
        清理後的 JSON 字串
    """
    # 移除 markdown code block 標記
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    # 嘗試找到 JSON 物件
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        return json_match.group(0)

    return text.strip()


def calculate_single_passage_distribution(total_count: int) -> List[int]:
    """
    計算單篇閱讀的題目分配
    每篇文章最少2題，最多4題

    Args:
        total_count: 總題數

    Returns:
        題目分配列表，例如 [3, 2] 表示第一篇3題，第二篇2題
    """
    if total_count < 2:
        return []

    # 計算需要幾篇文章（每篇最多4題）
    import math
    passage_count = math.ceil(total_count / 4)

    # 平均分配題目
    base_questions = total_count // passage_count
    remainder = total_count % passage_count

    # 前 remainder 篇多分配 1 題
    distribution = []
    for i in range(passage_count):
        questions = base_questions + (1 if i < remainder else 0)
        distribution.append(questions)

    return distribution


def calculate_multiple_passage_distribution(total_count: int) -> List[int]:
    """
    計算多篇閱讀的題目分配
    每組最少3題，最多5題（每組包含2-3篇相關文章）

    Args:
        total_count: 總題數

    Returns:
        題目分配列表，例如 [5, 4] 表示第一組5題，第二組4題
    """
    if total_count < 3:
        return []

    # 計算需要幾組文章（每組最多5題）
    import math
    group_count = math.ceil(total_count / 5)

    # 平均分配題目
    base_questions = total_count // group_count
    remainder = total_count % group_count

    # 前 remainder 組多分配 1 題
    distribution = []
    for i in range(group_count):
        questions = base_questions + (1 if i < remainder else 0)
        distribution.append(questions)

    return distribution


@router.post("/generate", response_model=TOEICQuizResponse)
async def generate_reading_questions(request: TOEICGenerateRequest):
    """
    生成 TOEIC 考題

    Args:
        request: 考題生成請求

    Returns:
        TOEICQuizResponse: 生成的考題
    """
    try:
        # 延遲導入以避免啟動時的錯誤
        from backend.ai_clients.ai_client_factory import AIClientFactory
        from backend.prompt_engine.prompt_manager import PromptManager

        # 驗證參數
        valid_types = ["sentence", "paragraph", "single_passage", "multiple_passage"]
        if request.question_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"question_type 必須是 {', '.join(valid_types)} 之一")

        if request.count < 1 or request.count > 50:
            raise HTTPException(status_code=400, detail="題數必須在 1-50 之間")

        # 建立 AI 客戶端
        client = AIClientFactory.create_client(
            provider=request.provider,
            model=request.model,
            api_key=request.api_key
        )

        # 取得 Prompt
        prompt_manager = PromptManager()
        type_names = {
            "sentence": "句子填空",
            "paragraph": "段落填空",
            "single_passage": "單篇閱讀",
            "multiple_passage": "多篇閱讀"
        }

        max_attempts = 3
        use_gemini_schema = (request.provider == "gemini")

        def request_questions(prompt: str, label: str) -> List[dict]:
            for attempt in range(1, max_attempts + 1):
                try:
                    print(f">>> 正在生成 {label}... (嘗試 {attempt}/{max_attempts})")

                    # Gemini 使用 schema-based 生成，更可靠
                    if use_gemini_schema:
                        from backend.prompt_engine.toeic_response_schemas import TOEICQuestionsResponseSchema
                        response_text = client.generate_with_schema(
                            prompt=prompt,
                            response_schema=TOEICQuestionsResponseSchema
                        )
                        result = json.loads(response_text)
                    else:
                        # Ollama / OpenAI 使用傳統方式
                        response_text = client._generate_response(prompt)
                        cleaned_json = clean_json_response(response_text)
                        result = json.loads(cleaned_json)

                    if "questions" not in result:
                        raise ValueError("AI 回應格式錯誤：缺少 questions 欄位")
                    if len(result["questions"]) == 0:
                        raise ValueError("AI 未生成任何題目")
                    return result["questions"]
                except json.JSONDecodeError as e:
                    print(f">>> JSON 解析錯誤 ({label}) (嘗試 {attempt}/{max_attempts}): {str(e)}")
                    if attempt >= max_attempts:
                        raise
                except ValueError as e:
                    print(f">>> AI 回應格式錯誤 ({label}) (嘗試 {attempt}/{max_attempts}): {str(e)}")
                    if attempt >= max_attempts:
                        raise
                except AttributeError as e:
                    # 如果 client 沒有 generate_with_schema 方法（非 Gemini），回退到傳統方式
                    if "generate_with_schema" in str(e) and attempt == 1:
                        print(f">>> 警告：{request.provider} 不支援 schema-based 生成，使用傳統方式")
                        response_text = client._generate_response(prompt)
                        cleaned_json = clean_json_response(response_text)
                        result = json.loads(cleaned_json)
                        if "questions" not in result:
                            raise ValueError("AI 回應格式錯誤：缺少 questions 欄位")
                        if len(result["questions"]) == 0:
                            raise ValueError("AI 未生成任何題目")
                        return result["questions"]
                    else:
                        raise
            raise ValueError("多次嘗試生成題目皆失敗")

        all_questions: List[dict] = []

        # 對於單篇和多篇閱讀，使用分配算法生成多篇文章/組
        if request.question_type == "single_passage":
            from backend.prompt_engine.toeic_topics import get_diverse_topics, get_diverse_passage_styles

            distribution = calculate_single_passage_distribution(request.count)
            print(f">>> 單篇閱讀分配：{distribution} (共 {sum(distribution)} 題)")
            passage_topics = get_diverse_topics(len(distribution))
            passage_styles = get_diverse_passage_styles(len(distribution))

            for passage_index, question_count in enumerate(distribution):
                # 為每篇文章使用不同的隨機主題
                topic_hint = passage_topics[passage_index]
                passage_style = passage_styles[passage_index]

                prompt = prompt_manager.get_toeic_single_passage_prompt(
                    count=question_count,
                    difficulty=request.difficulty or "medium",
                    topic_hint=topic_hint,
                    passage_style=passage_style,
                )
                questions = request_questions(prompt, f"單篇閱讀 第 {passage_index + 1} 篇 ({topic_hint})")

                # 找出這篇文章的完整內容（從第一個有效的 passage 中取得）
                article_passage = None
                for q in questions:
                    if "passage" in q and q["passage"] and q["passage"] not in ["[同一篇文章]", "[同組文章]"]:
                        article_passage = q["passage"]
                        break

                # 將完整的 passage 賦值給這篇文章的每一題
                if article_passage:
                    for q in questions:
                        q["passage"] = article_passage
                        if not q.get("passage_style"):
                            q["passage_style"] = passage_style
                    print(f">>> 第 {passage_index + 1} 篇文章長度：{len(article_passage)} 字元")

                all_questions.extend(questions)

        elif request.question_type == "multiple_passage":
            from backend.prompt_engine.toeic_topics import get_diverse_topics, get_diverse_passage_styles

            distribution = calculate_multiple_passage_distribution(request.count)
            print(f">>> 多篇閱讀分配：{distribution} (共 {sum(distribution)} 題)")
            group_topics = get_diverse_topics(len(distribution))
            group_styles = get_diverse_passage_styles(len(distribution))

            for group_index, question_count in enumerate(distribution):
                # 為每組文章使用不同的隨機主題
                topic_hint = group_topics[group_index]
                passage_style = group_styles[group_index]

                prompt = prompt_manager.get_toeic_multiple_passage_prompt(
                    count=question_count,
                    difficulty=request.difficulty or "medium",
                    topic_hint=topic_hint,
                    passage_style=passage_style,
                )
                questions = request_questions(prompt, f"多篇閱讀 第 {group_index + 1} 組 ({topic_hint})")

                # 收集所有 passages，確保每題都有完整的文章組
                group_passages = []
                for q in questions:
                    if "passages" in q and isinstance(q["passages"], list):
                        for p in q["passages"]:
                            if p and p not in ["[同組文章]", "[同一篇文章]"] and p not in group_passages:
                                group_passages.append(p)

                # 將完整的 passages 賦值給這組的每一題
                for q in questions:
                    q["passages"] = group_passages
                    if not q.get("passage_style"):
                        q["passage_style"] = passage_style

                print(f">>> 第 {group_index + 1} 組包含 {len(group_passages)} 篇文章")
                all_questions.extend(questions)

        elif request.question_type == "sentence":
            # Part 5: 每題單獨生成，使用不同主題確保多樣性
            from backend.prompt_engine.toeic_topics import get_diverse_topics

            topics = get_diverse_topics(request.count)

            for i in range(request.count):
                # 為每題使用不同的隨機主題
                topic_hint = topics[i]

                prompt = prompt_manager.get_toeic_sentence_prompt(
                    count=1,
                    difficulty=request.difficulty or "medium",
                    topic_hint=topic_hint
                )
                questions = request_questions(prompt, f"句子填空 第 {i + 1} 題 ({topic_hint})")
                all_questions.extend(questions)

        else:  # paragraph
            # Part 6: 每組文章單獨生成（通常每篇 4 題）
            # 為了確保多樣性，每組使用不同的主題提示
            from backend.prompt_engine.toeic_topics import get_diverse_topics, get_diverse_passage_styles

            group_size = 4
            remaining = request.count
            group_index = 1
            group_count = (request.count + group_size - 1) // group_size
            group_topics = get_diverse_topics(group_count)
            group_styles = get_diverse_passage_styles(group_count)

            while remaining > 0:
                count = group_size if remaining >= group_size else remaining

                # 為每組使用不同的隨機主題
                topic_hint = group_topics[group_index - 1]
                passage_style = group_styles[group_index - 1]

                prompt = prompt_manager.get_toeic_paragraph_prompt(
                    count=count,
                    difficulty=request.difficulty or "medium",
                    topic_hint=topic_hint,  # 傳遞主題提示
                    passage_style=passage_style,
                )
                questions = request_questions(prompt, f"段落填空 第 {group_index} 組 ({topic_hint})")
                for q in questions:
                    if not q.get("passage_style"):
                        q["passage_style"] = passage_style
                all_questions.extend(questions)
                remaining -= count
                group_index += 1

        # 驗證生成的題目數量
        if len(all_questions) == 0:
            raise ValueError("AI 未生成任何題目")

        # 重新編號題目
        questions = []
        for index, q in enumerate(all_questions):
            q["question_number"] = index + 1
            questions.append(q)

        print(f">>> 成功生成 {len(questions)} 題")

        return TOEICQuizResponse(
            questions=questions,
            question_type=request.question_type,
            total_count=len(questions)
        )

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI 回應格式錯誤，無法解析 JSON: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f">>> 生成失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成失敗：{str(e)}")


async def _run_toeic_quiz_job(job_id: str, request: TOEICGenerateRequest) -> None:
    job = toeic_quiz_jobs[job_id]
    job["status"] = "running"
    job["message"] = None
    job["progress"]["generated"] = 0
    _persist_toeic_quiz_job(job_id)
    try:
        response = await generate_reading_questions(request)
        job["result"] = response.model_dump()
        job["progress"]["generated"] = len(response.questions)
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow()
        _persist_toeic_quiz_job(job_id)
    except Exception as exc:  # noqa: BLE001
        job["status"] = "error"
        job["message"] = str(exc)
        job["completed_at"] = datetime.utcnow()
        _persist_toeic_quiz_job(job_id)


@router.post("/generate-job", response_model=QuizJobStatus)
async def start_toeic_quiz_job(request: TOEICGenerateRequest) -> QuizJobStatus:
    """
    啟動題型測驗（閱讀 Part 5-7）背景任務。
    """
    job_id = str(uuid.uuid4())
    toeic_quiz_jobs[job_id] = {
        "status": "pending",
        "progress": {"generated": 0, "total": request.count},
        "message": None,
        "created_at": datetime.utcnow(),
        "completed_at": None,
        "result": None,
        "test_mode": request.question_type,
    }
    _persist_toeic_quiz_job(job_id)

    def _run_in_thread() -> None:
        asyncio.run(_run_toeic_quiz_job(job_id, request))

    threading.Thread(target=_run_in_thread, daemon=True).start()

    return QuizJobStatus(
        job_id=job_id,
        status="pending",
        progress=toeic_quiz_jobs[job_id]["progress"],
        message=None,
        created_at=toeic_quiz_jobs[job_id]["created_at"],
        completed_at=None,
    )


@router.get("/generate-job/{job_id}", response_model=QuizJobStatus)
async def get_toeic_quiz_job_status(job_id: str) -> QuizJobStatus:
    """
    查詢題型測驗（閱讀 Part 5-7）背景任務狀態。
    """
    job = toeic_quiz_jobs.get(job_id)
    if not job:
        job = _load_toeic_quiz_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        toeic_quiz_jobs[job_id] = job
    return QuizJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job.get("message"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )


@router.get("/generate-job/{job_id}/result", response_model=QuizJobResult)
async def get_toeic_quiz_job_result(job_id: str) -> QuizJobResult:
    """
    取得題型測驗（閱讀 Part 5-7）背景任務結果。
    """
    job = toeic_quiz_jobs.get(job_id)
    if not job:
        job = _load_toeic_quiz_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        toeic_quiz_jobs[job_id] = job
    if job["status"] != "completed" or not job.get("result"):
        raise HTTPException(status_code=202, detail="任務尚未完成")
    return QuizJobResult(**job["result"])


@router.post("/quiz-folders", response_model=QuizFolderResponse)
def create_quiz_folder(request: QuizFolderCreateRequest, db: Session = Depends(get_db)) -> QuizFolderResponse:
    folder = QuizFolder(
        id=str(uuid.uuid4()),
        name=request.name,
        color=request.color,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return QuizFolderResponse(
        id=folder.id,
        name=folder.name,
        color=folder.color,
        created_at=folder.created_at,
    )


@router.get("/quiz-folders", response_model=List[QuizFolderResponse])
def list_quiz_folders(db: Session = Depends(get_db)) -> List[QuizFolderResponse]:
    folders = db.query(QuizFolder).order_by(QuizFolder.created_at).all()
    return [
        QuizFolderResponse(
            id=folder.id,
            name=folder.name,
            color=folder.color,
            created_at=folder.created_at,
        )
        for folder in folders
    ]


@router.put("/quiz-folders/{folder_id}", response_model=QuizFolderResponse)
def update_quiz_folder(
    folder_id: str,
    request: QuizFolderUpdateRequest,
    db: Session = Depends(get_db),
) -> QuizFolderResponse:
    folder = db.query(QuizFolder).filter(QuizFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="找不到該資料夾")
    if request.name is not None:
        folder.name = request.name
    if request.color is not None:
        folder.color = request.color
    db.commit()
    db.refresh(folder)
    return QuizFolderResponse(
        id=folder.id,
        name=folder.name,
        color=folder.color,
        created_at=folder.created_at,
    )


@router.delete("/quiz-folders/{folder_id}")
def delete_quiz_folder(folder_id: str, db: Session = Depends(get_db)) -> dict:
    folder = db.query(QuizFolder).filter(QuizFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="找不到該資料夾")
    db.query(QuizLog).filter(QuizLog.folder_id == folder_id).update({"folder_id": None})
    db.delete(folder)
    db.commit()
    return {"message": "資料夾已刪除"}


@router.post("/quiz-logs", response_model=QuizLogSummary)
def create_quiz_log(request: QuizLogCreateRequest, db: Session = Depends(get_db)) -> QuizLogSummary:
    log = QuizLog(
        id=str(uuid.uuid4()),
        mode=request.mode,
        title=request.title,
        count=request.count,
        difficulty=request.difficulty,
        folder_id=request.folder_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _quiz_log_to_summary(log)


@router.get("/quiz-logs", response_model=List[QuizLogSummary])
def list_quiz_logs(db: Session = Depends(get_db)) -> List[QuizLogSummary]:
    logs = db.query(QuizLog).order_by(QuizLog.created_at.desc()).all()
    return [_quiz_log_to_summary(log) for log in logs]


@router.get("/quiz-logs/{log_id}", response_model=QuizLogDetail)
def get_quiz_log(log_id: str, db: Session = Depends(get_db)) -> QuizLogDetail:
    log = db.query(QuizLog).filter(QuizLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="找不到該記錄")
    return _quiz_log_to_detail(log)


@router.put("/quiz-logs/{log_id}", response_model=QuizLogDetail)
def update_quiz_log(
    log_id: str,
    request: QuizLogUpdateRequest,
    db: Session = Depends(get_db),
) -> QuizLogDetail:
    log = db.query(QuizLog).filter(QuizLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="找不到該記錄")
    fields_set = getattr(request, "model_fields_set", None) or getattr(request, "__fields_set__", set())
    if request.title is not None:
        log.title = request.title
    if "folder_id" in fields_set:
        log.folder_id = request.folder_id
    if request.payload is not None:
        log.payload_json = json.dumps(request.payload, ensure_ascii=False)
    if "score" in fields_set:
        log.score_json = json.dumps(request.score, ensure_ascii=False) if request.score is not None else None
    db.commit()
    db.refresh(log)
    return _quiz_log_to_detail(log)


@router.delete("/quiz-logs/{log_id}")
def delete_quiz_log(log_id: str, db: Session = Depends(get_db)) -> dict:
    log = db.query(QuizLog).filter(QuizLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="找不到該記錄")
    db.delete(log)
    db.commit()
    return {"message": "記錄已刪除"}


@router.post("/explain", response_model=List[TOEICExplanation])
async def generate_reading_explanations(request: TOEICExplainRequest):
    """
    生成 TOEIC 閱讀測驗詳解

    Args:
        request: 詳解生成請求

    Returns:
        List[TOEICExplanation]: 詳解列表
    """
    try:
        # 延遲導入以避免啟動時的錯誤
        from backend.ai_clients.ai_client_factory import AIClientFactory
        from backend.prompt_engine.prompt_manager import PromptManager

        if not request.answers or len(request.answers) == 0:
            raise HTTPException(status_code=400, detail="答案列表不能為空")

        # 建立 AI 客戶端
        client = AIClientFactory.create_client(
            provider=request.provider,
            model=request.model,
            api_key=request.api_key
        )

        # 將 Pydantic 模型轉為字典
        answers_dict = [ans.model_dump() for ans in request.answers]

        prompt_manager = PromptManager()
        final_explanations = []
        part_label = _get_toeic_part_label(answers_dict[0] if answers_dict else None)

        print(f">>> 正在逐題生成 {len(request.answers)} 題的詳解...")

        for ans in answers_dict:
            prompt = prompt_manager.get_toeic_explanation_prompt(part_label, ans)
            response_text = client._generate_response(prompt)
            explanation_text = response_text.strip()

            final_explanations.append({
                'question_number': ans['question_number'],
                'user_answer': ans.get('user_answer', ''),
                'correct_answer': ans.get('correct_answer', ''),
                'is_correct': ans['user_answer'] == ans['correct_answer'],
                'explanation': explanation_text
            })

        return [TOEICExplanation(**exp) for exp in final_explanations]
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f">>> 生成詳解失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成詳解失敗：{str(e)}")


def _get_toeic_part_label(answer: Optional[dict]) -> str:
    if not answer:
        return "TOEIC 題目"
    question_type = answer.get("question_type")
    if question_type == "sentence":
        return "Part 5 句子填空"
    if question_type == "paragraph":
        return "Part 6 段落填空"
    if question_type == "single_passage":
        return "Part 7 單篇閱讀"
    if question_type == "multiple_passage":
        return "Part 7 多篇閱讀"
    if answer.get("passages"):
        return "Part 7 多篇閱讀"
    if answer.get("passage"):
        return "Part 7 單篇閱讀"
    return "Part 5/6 閱讀"


# ========== 聽力測驗背景任務 ==========

async def _run_listening_test_job(job_id: str, request: ListeningTestGenerateRequest) -> None:
    """
    在背景中執行聽力測驗生成（可接續已生成的題目）。
    """
    try:
        from backend.routers.listening import (
            generate_part1_question,
            generate_part2_question,
            generate_part3_question,
            generate_part4_question,
        )

        job = listening_test_jobs[job_id]
        progress = job.get("progress") or _init_listening_test_progress()
        job["progress"] = progress
        job["status"] = "running"
        job["message"] = None
        _persist_listening_test_job(job_id)

        text_provider = request.text_provider or request.provider
        text_model = request.text_model or request.model
        text_api_key = request.text_api_key or request.api_key
        media_provider = request.media_provider or "gemini"
        media_model = request.media_model or request.model
        media_api_key = request.media_api_key or request.api_key

        if media_provider != "gemini":
            raise ValueError("媒體功能僅支援 Gemini")
        if not media_api_key:
            raise ValueError("請提供媒體功能 API Key")
        if text_provider != "ollama" and not text_api_key:
            raise ValueError("請提供文字生成 API Key")

        result = _ensure_listening_test_result(job.get("result"), request.difficulty)

        def persist_partial() -> None:
            _update_listening_test_total_count(result)
            job["result"] = result
            _persist_listening_test_job(job_id)

        def start_part(part_key: str) -> None:
            progress[part_key] = "running"
            _persist_listening_test_job(job_id)

        def complete_part(part_key: str) -> None:
            progress[part_key] = "completed"
            _persist_listening_test_job(job_id)

        def fail_part(part_key: str, error: Exception) -> None:
            progress[part_key] = "error"
            job["status"] = "error"
            job["message"] = str(error)
            job["completed_at"] = datetime.utcnow()
            persist_partial()

        # Part 1 - 照片描述 (6題)
        part_key = "part1"
        expected = LISTENING_TEST_EXPECTED_COUNTS[part_key]
        if len(result[f"{part_key}_questions"]) >= expected:
            progress["part1_index"] = expected
            complete_part(part_key)
        else:
            start_part(part_key)
            start_index = len(result[f"{part_key}_questions"])
            progress["part1_index"] = start_index
            for i in range(start_index, expected):
                if job.get("status") == "cancelled":
                    return
                try:
                    q = await generate_part1_question(
                        question_number=i + 1,
                        difficulty=request.difficulty,
                        provider=media_provider,
                        model=media_model,
                        media_api_key=media_api_key,
                        text_api_key=media_api_key,
                    )
                    result[f"{part_key}_questions"].append(q.model_dump())
                    progress["part1_index"] = i + 1
                    persist_partial()
                    print(f">>> [LISTENING] Part 1 題目 {i + 1}/{expected} 已生成")
                except Exception as e:
                    print(f">>> [LISTENING] Part 1 題目 {i + 1} 生成失敗: {str(e)}")
                    fail_part(part_key, e)
                    return
            complete_part(part_key)

        # Part 2 - 應答問題 (25題)
        part_key = "part2"
        expected = LISTENING_TEST_EXPECTED_COUNTS[part_key]
        if len(result[f"{part_key}_questions"]) >= expected:
            progress["part2_index"] = expected
            complete_part(part_key)
        else:
            from backend.prompt_engine.listening_prompts import PART2_TOPICS as _P2
            import random as _random
            _p2_pool = _P2.copy(); _random.shuffle(_p2_pool)
            p2_topics = [_p2_pool[i % len(_p2_pool)] for i in range(expected)]
            start_part(part_key)
            start_index = len(result[f"{part_key}_questions"])
            progress["part2_index"] = start_index
            for i in range(start_index, expected):
                if job.get("status") == "cancelled":
                    return
                try:
                    q = await generate_part2_question(
                        question_number=i + 1,
                        difficulty=request.difficulty,
                        text_provider=text_provider,
                        text_model=text_model,
                        tts_provider=media_provider,
                        tts_api_key=media_api_key,
                        text_api_key=text_api_key,
                        topic_hint=p2_topics[i],
                    )
                    result[f"{part_key}_questions"].append(q.model_dump())
                    progress["part2_index"] = i + 1
                    persist_partial()
                    print(f">>> [LISTENING] Part 2 題目 {i + 1}/{expected} 已生成")
                except Exception as e:
                    print(f">>> [LISTENING] Part 2 題目 {i + 1} 生成失敗: {str(e)}")
                    fail_part(part_key, e)
                    return
            complete_part(part_key)

        # Part 3 - 簡短對話 (13組)
        part_key = "part3"
        expected = LISTENING_TEST_EXPECTED_COUNTS[part_key]
        if len(result[f"{part_key}_questions"]) >= expected:
            progress["part3_index"] = expected
            complete_part(part_key)
        else:
            from backend.prompt_engine.listening_prompts import PART3_TOPICS as _P3
            _p3_pool = _P3.copy(); _random.shuffle(_p3_pool)
            p3_topics = [_p3_pool[i % len(_p3_pool)] for i in range(expected)]
            start_part(part_key)
            start_index = len(result[f"{part_key}_questions"])
            progress["part3_index"] = start_index
            for i in range(start_index, expected):
                if job.get("status") == "cancelled":
                    return
                try:
                    q = await generate_part3_question(
                        question_number=i + 1,
                        difficulty=request.difficulty,
                        text_provider=text_provider,
                        text_model=text_model,
                        tts_provider=media_provider,
                        tts_api_key=media_api_key,
                        text_api_key=text_api_key,
                        topic_hint=p3_topics[i],
                    )
                    result[f"{part_key}_questions"].append(q.model_dump())
                    progress["part3_index"] = i + 1
                    persist_partial()
                    print(f">>> [LISTENING] Part 3 對話組 {i + 1}/{expected} 已生成")
                except Exception as e:
                    print(f">>> [LISTENING] Part 3 對話組 {i + 1} 生成失敗: {str(e)}")
                    fail_part(part_key, e)
                    return
            complete_part(part_key)

        # Part 4 - 簡短獨白 (10組)
        part_key = "part4"
        expected = LISTENING_TEST_EXPECTED_COUNTS[part_key]
        if len(result[f"{part_key}_questions"]) >= expected:
            progress["part4_index"] = expected
            complete_part(part_key)
        else:
            from backend.prompt_engine.listening_prompts import PART4_TOPICS as _P4
            _p4_pool = _P4.copy(); _random.shuffle(_p4_pool)
            p4_topics = [_p4_pool[i % len(_p4_pool)] for i in range(expected)]
            start_part(part_key)
            start_index = len(result[f"{part_key}_questions"])
            progress["part4_index"] = start_index
            for i in range(start_index, expected):
                if job.get("status") == "cancelled":
                    return
                try:
                    q = await generate_part4_question(
                        question_number=i + 1,
                        difficulty=request.difficulty,
                        text_provider=text_provider,
                        text_model=text_model,
                        tts_provider=media_provider,
                        tts_api_key=media_api_key,
                        text_api_key=text_api_key,
                        topic_hint=p4_topics[i],
                    )
                    result[f"{part_key}_questions"].append(q.model_dump())
                    progress["part4_index"] = i + 1
                    persist_partial()
                    print(f">>> [LISTENING] Part 4 獨白 {i + 1}/{expected} 已生成")
                except Exception as e:
                    print(f">>> [LISTENING] Part 4 獨白 {i + 1} 生成失敗: {str(e)}")
                    fail_part(part_key, e)
                    return
            complete_part(part_key)

        # 所有 Part 完成
        _update_listening_test_total_count(result)
        final_result = ListeningTestResponse(
            part1_questions=result["part1_questions"],
            part2_questions=result["part2_questions"],
            part3_questions=result["part3_questions"],
            part4_questions=result["part4_questions"],
            difficulty=request.difficulty or "medium",
            total_count=result["total_count"],
        )

        job["result"] = final_result
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow()
        _persist_listening_test_job(job_id)

    except Exception as e:
        import traceback
        traceback.print_exc()
        job = listening_test_jobs[job_id]
        job["status"] = "error"
        job["message"] = str(e)
        job["completed_at"] = datetime.utcnow()
        _persist_listening_test_job(job_id)


# ========== 閱讀測驗背景任務 ==========

async def _run_reading_test_job(job_id: str, request: ReadingTestGenerateRequest) -> None:
    """
    在背景中執行閱讀測驗生成（可接續已生成的題目）。
    """
    try:
        job = reading_test_jobs[job_id]
        progress = job.get("progress") or _init_reading_test_progress()
        job["progress"] = progress
        job["status"] = "running"
        job["message"] = None
        _persist_reading_test_job(job_id)

        text_provider = request.provider
        text_model = request.model
        text_api_key = request.api_key

        if text_provider != "ollama" and not text_api_key:
            raise ValueError("請提供文字生成 API Key")

        result = _ensure_reading_test_result(job.get("result"), request.difficulty)

        def persist_partial() -> None:
            _update_reading_test_total_count(result)
            job["result"] = result
            _persist_reading_test_job(job_id)

        def start_part(part_key: str) -> None:
            progress[part_key] = "running"
            _persist_reading_test_job(job_id)

        def complete_part(part_key: str) -> None:
            progress[part_key] = "completed"
            _persist_reading_test_job(job_id)

        def fail_part(part_key: str, error: Exception) -> None:
            progress[part_key] = "error"
            job["status"] = "error"
            job["message"] = str(error)
            job["completed_at"] = datetime.utcnow()
            persist_partial()

        # Part 5 - 句子填空 (30題)
        part_key = "part5"
        expected = READING_TEST_EXPECTED_COUNTS[part_key]
        if len(result[f"{part_key}_questions"]) >= expected:
            progress["part5_index"] = expected
            complete_part(part_key)
        else:
            start_part(part_key)
            try:
                start_index = len(result[f"{part_key}_questions"])
                progress["part5_index"] = start_index
                for i in range(start_index, expected):
                    if job.get("status") == "cancelled":
                        return
                    part5_response = await generate_reading_questions(
                        TOEICGenerateRequest(
                            question_type="sentence",
                            count=1,
                            difficulty=request.difficulty,
                            provider=text_provider,
                            model=text_model,
                            api_key=text_api_key,
                        )
                    )
                    questions = part5_response.questions
                    if not questions:
                        raise ValueError("Part 5 生成結果為空")
                    question = questions[0].model_dump() if hasattr(questions[0], "model_dump") else questions[0]
                    question["question_number"] = i + 1
                    result[f"{part_key}_questions"].append(question)
                    progress["part5_index"] = i + 1
                    persist_partial()
                    print(f">>> [READING] Part 5 題目 {i + 1}/{expected} 已生成")
                complete_part(part_key)
            except Exception as e:
                print(f">>> [READING] Part 5 生成失敗: {str(e)}")
                fail_part(part_key, e)
                return

        # Part 6 - 段落填空 (16題)
        part_key = "part6"
        expected = READING_TEST_EXPECTED_COUNTS[part_key]
        if len(result[f"{part_key}_questions"]) >= expected:
            progress["part6_index"] = expected
            complete_part(part_key)
        else:
            start_part(part_key)
            try:
                group_size = 4
                start_index = len(result[f"{part_key}_questions"])
                progress["part6_index"] = start_index
                generated = start_index
                while generated < expected:
                    if job.get("status") == "cancelled":
                        return
                    remaining = expected - generated
                    count = group_size if remaining >= group_size else remaining
                    part6_response = await generate_reading_questions(
                        TOEICGenerateRequest(
                            question_type="paragraph",
                            count=count,
                            difficulty=request.difficulty,
                            provider=text_provider,
                            model=text_model,
                            api_key=text_api_key,
                        )
                    )
                    questions = part6_response.questions
                    if not questions:
                        raise ValueError("Part 6 生成結果為空")
                    for q in questions:
                        question = q.model_dump() if hasattr(q, "model_dump") else q
                        question["question_number"] = len(result[f"{part_key}_questions"]) + 1
                        result[f"{part_key}_questions"].append(question)
                        progress["part6_index"] = len(result[f"{part_key}_questions"])
                        persist_partial()
                        print(f">>> [READING] Part 6 題目 {question['question_number']}/{expected} 已生成")
                    generated = len(result[f"{part_key}_questions"])
                complete_part(part_key)
            except Exception as e:
                print(f">>> [READING] Part 6 生成失敗: {str(e)}")
                fail_part(part_key, e)
                return

        # Part 7 單篇閱讀 (29題)
        part_key = "part7_single"
        expected = READING_TEST_EXPECTED_COUNTS[part_key]
        if len(result[f"{part_key}_questions"]) >= expected:
            progress["part7_single_index"] = expected
            complete_part(part_key)
        else:
            start_part(part_key)
            try:
                distribution = calculate_single_passage_distribution(expected)
                start_index = len(result[f"{part_key}_questions"])
                progress["part7_single_index"] = start_index
                completed_groups = 0
                total_so_far = 0
                for group_count in distribution:
                    total_so_far += group_count
                    if total_so_far <= start_index:
                        completed_groups += 1
                    else:
                        break

                for group_index in range(completed_groups, len(distribution)):
                    if job.get("status") == "cancelled":
                        return
                    count = distribution[group_index]
                    part7_single_response = await generate_reading_questions(
                        TOEICGenerateRequest(
                            question_type="single_passage",
                            count=count,
                            difficulty=request.difficulty,
                            provider=text_provider,
                            model=text_model,
                            api_key=text_api_key,
                        )
                    )
                    questions = part7_single_response.questions
                    if not questions:
                        raise ValueError("Part 7 單篇生成結果為空")
                    for q in questions:
                        question = q.model_dump() if hasattr(q, "model_dump") else q
                        question["question_number"] = len(result[f"{part_key}_questions"]) + 1
                        result[f"{part_key}_questions"].append(question)
                        progress["part7_single_index"] = len(result[f"{part_key}_questions"])
                        persist_partial()
                        print(f">>> [READING] Part 7 單篇題目 {question['question_number']}/{expected} 已生成")
                complete_part(part_key)
            except Exception as e:
                print(f">>> [READING] Part 7 單篇 生成失敗: {str(e)}")
                fail_part(part_key, e)
                return

        # Part 7 多篇閱讀 (25題)
        part_key = "part7_multiple"
        expected = READING_TEST_EXPECTED_COUNTS[part_key]
        if len(result[f"{part_key}_questions"]) >= expected:
            progress["part7_multiple_index"] = expected
            complete_part(part_key)
        else:
            start_part(part_key)
            try:
                distribution = calculate_multiple_passage_distribution(expected)
                start_index = len(result[f"{part_key}_questions"])
                progress["part7_multiple_index"] = start_index
                completed_groups = 0
                total_so_far = 0
                for group_count in distribution:
                    total_so_far += group_count
                    if total_so_far <= start_index:
                        completed_groups += 1
                    else:
                        break

                for group_index in range(completed_groups, len(distribution)):
                    if job.get("status") == "cancelled":
                        return
                    count = distribution[group_index]
                    part7_multiple_response = await generate_reading_questions(
                        TOEICGenerateRequest(
                            question_type="multiple_passage",
                            count=count,
                            difficulty=request.difficulty,
                            provider=text_provider,
                            model=text_model,
                            api_key=text_api_key,
                        )
                    )
                    questions = part7_multiple_response.questions
                    if not questions:
                        raise ValueError("Part 7 多篇生成結果為空")
                    for q in questions:
                        question = q.model_dump() if hasattr(q, "model_dump") else q
                        question["question_number"] = len(result[f"{part_key}_questions"]) + 1
                        result[f"{part_key}_questions"].append(question)
                        progress["part7_multiple_index"] = len(result[f"{part_key}_questions"])
                        persist_partial()
                        print(f">>> [READING] Part 7 多篇題目 {question['question_number']}/{expected} 已生成")
                complete_part(part_key)
            except Exception as e:
                print(f">>> [READING] Part 7 多篇 生成失敗: {str(e)}")
                fail_part(part_key, e)
                return

        # 所有 Part 完成
        _update_reading_test_total_count(result)
        final_result = ReadingTestResponse(
            part5_questions=result["part5_questions"],
            part6_questions=result["part6_questions"],
            part7_single_questions=result["part7_single_questions"],
            part7_multiple_questions=result["part7_multiple_questions"],
            difficulty=request.difficulty or "medium",
            total_count=result["total_count"],
        )

        job["result"] = final_result
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow()
        _persist_reading_test_job(job_id)

    except Exception as e:
        import traceback
        traceback.print_exc()
        job = reading_test_jobs[job_id]
        job["status"] = "error"
        job["message"] = str(e)
        job["completed_at"] = datetime.utcnow()
        _persist_reading_test_job(job_id)


# ========== 聽力測驗 API 端點 ==========

@router.post("/listening-test/job", response_model=ListeningTestJobStatus)
async def start_listening_test_job(request: ListeningTestGenerateRequest) -> ListeningTestJobStatus:
    """
    啟動聽力測驗背景任務，立即返回 job_id，由前端輪詢進度。
    """
    job_id = str(uuid.uuid4())
    progress = _init_listening_test_progress()
    listening_test_jobs[job_id] = {
        "status": "pending",
        "progress": progress,
        "message": None,
        "created_at": datetime.utcnow(),
        "completed_at": None,
        "result": _ensure_listening_test_result(None, request.difficulty),
    }
    _persist_listening_test_job(job_id)

    def _run_in_thread() -> None:
        asyncio.run(_run_listening_test_job(job_id, request))

    threading.Thread(target=_run_in_thread, daemon=True).start()

    return ListeningTestJobStatus(
        job_id=job_id,
        status="pending",
        progress=progress,
        message=None,
        created_at=listening_test_jobs[job_id]["created_at"],
        completed_at=None,
    )


@router.get("/listening-test/job/{job_id}", response_model=ListeningTestJobStatus)
async def get_listening_test_job_status(job_id: str) -> ListeningTestJobStatus:
    """
    查詢聽力測驗背景任務狀態。
    """
    job = listening_test_jobs.get(job_id)
    if not job:
        job = _load_listening_test_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        listening_test_jobs[job_id] = job

    return ListeningTestJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        created_at=job["created_at"],
        completed_at=job["completed_at"],
    )


@router.post("/listening-test/job/{job_id}/resume", response_model=ListeningTestJobStatus)
async def resume_listening_test_job(job_id: str, request: ListeningTestGenerateRequest) -> ListeningTestJobStatus:
    """
    接續聽力測驗背景任務。
    """
    job = listening_test_jobs.get(job_id)
    if not job:
        job = _load_listening_test_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        listening_test_jobs[job_id] = job

    if job.get("status") == "running":
        return ListeningTestJobStatus(
            job_id=job_id,
            status=job["status"],
            progress=job["progress"],
            message=job["message"],
            created_at=job["created_at"],
            completed_at=job["completed_at"],
        )
    if job.get("status") == "completed":
        return ListeningTestJobStatus(
            job_id=job_id,
            status=job["status"],
            progress=job.get("progress") or _init_listening_test_progress(),
            message=job.get("message"),
            created_at=job.get("created_at"),
            completed_at=job.get("completed_at"),
        )

    job["progress"] = job.get("progress") or _init_listening_test_progress()
    job["result"] = _ensure_listening_test_result(job.get("result"), request.difficulty)
    job["message"] = None
    job["completed_at"] = None
    _persist_listening_test_job(job_id)

    def _run_in_thread() -> None:
        asyncio.run(_run_listening_test_job(job_id, request))

    threading.Thread(target=_run_in_thread, daemon=True).start()

    return ListeningTestJobStatus(
        job_id=job_id,
        status=job.get("status", "pending"),
        progress=job["progress"],
        message=job.get("message"),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
    )


@router.get("/listening-test/job/{job_id}/result", response_model=ListeningTestResponse)
async def get_listening_test_result(job_id: str) -> ListeningTestResponse:
    """
    取得聽力測驗背景任務的結果。
    """
    job = listening_test_jobs.get(job_id)
    if not job:
        job = _load_listening_test_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        listening_test_jobs[job_id] = job

    if job["status"] != "completed" or not job.get("result"):
        raise HTTPException(status_code=202, detail="任務尚未完成")

    result = job["result"]
    if isinstance(result, ListeningTestResponse):
        return result
    return ListeningTestResponse(**result)


@router.delete("/listening-test/job/{job_id}")
async def cancel_listening_test_job(job_id: str) -> dict:
    job = listening_test_jobs.get(job_id)
    if not job:
        job = _load_listening_test_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        listening_test_jobs[job_id] = job
    if job["status"] in ("completed", "cancelled"):
        return {"message": "任務已結束"}
    job["status"] = "cancelled"
    job["message"] = "使用者取消"
    job["completed_at"] = datetime.utcnow()
    _persist_listening_test_job(job_id)
    return {"message": "已取消"}


# ========== 閱讀測驗 API 端點 ==========

@router.post("/reading-test/job", response_model=ReadingTestJobStatus)
async def start_reading_test_job(request: ReadingTestGenerateRequest) -> ReadingTestJobStatus:
    """
    啟動閱讀測驗背景任務，立即返回 job_id，由前端輪詢進度。
    """
    job_id = str(uuid.uuid4())
    progress = _init_reading_test_progress()
    reading_test_jobs[job_id] = {
        "status": "pending",
        "progress": progress,
        "message": None,
        "created_at": datetime.utcnow(),
        "completed_at": None,
        "result": _ensure_reading_test_result(None, request.difficulty),
    }
    _persist_reading_test_job(job_id)

    def _run_in_thread() -> None:
        asyncio.run(_run_reading_test_job(job_id, request))

    threading.Thread(target=_run_in_thread, daemon=True).start()

    return ReadingTestJobStatus(
        job_id=job_id,
        status="pending",
        progress=progress,
        message=None,
        created_at=reading_test_jobs[job_id]["created_at"],
        completed_at=None,
    )


@router.get("/reading-test/job/{job_id}", response_model=ReadingTestJobStatus)
async def get_reading_test_job_status(job_id: str) -> ReadingTestJobStatus:
    """
    查詢閱讀測驗背景任務狀態。
    """
    job = reading_test_jobs.get(job_id)
    if not job:
        job = _load_reading_test_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        reading_test_jobs[job_id] = job

    return ReadingTestJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        created_at=job["created_at"],
        completed_at=job["completed_at"],
    )


@router.post("/reading-test/job/{job_id}/resume", response_model=ReadingTestJobStatus)
async def resume_reading_test_job(job_id: str, request: ReadingTestGenerateRequest) -> ReadingTestJobStatus:
    """
    接續閱讀測驗背景任務。
    """
    job = reading_test_jobs.get(job_id)
    if not job:
        job = _load_reading_test_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        reading_test_jobs[job_id] = job

    if job.get("status") == "running":
        return ReadingTestJobStatus(
            job_id=job_id,
            status=job["status"],
            progress=job["progress"],
            message=job["message"],
            created_at=job["created_at"],
            completed_at=job["completed_at"],
        )
    if job.get("status") == "completed":
        return ReadingTestJobStatus(
            job_id=job_id,
            status=job["status"],
            progress=job.get("progress") or _init_reading_test_progress(),
            message=job.get("message"),
            created_at=job.get("created_at"),
            completed_at=job.get("completed_at"),
        )

    job["progress"] = job.get("progress") or _init_reading_test_progress()
    job["result"] = _ensure_reading_test_result(job.get("result"), request.difficulty)
    job["message"] = None
    job["completed_at"] = None
    _persist_reading_test_job(job_id)

    def _run_in_thread() -> None:
        asyncio.run(_run_reading_test_job(job_id, request))

    threading.Thread(target=_run_in_thread, daemon=True).start()

    return ReadingTestJobStatus(
        job_id=job_id,
        status=job.get("status", "pending"),
        progress=job["progress"],
        message=job.get("message"),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
    )


@router.get("/reading-test/job/{job_id}/result", response_model=ReadingTestResponse)
async def get_reading_test_result(job_id: str) -> ReadingTestResponse:
    """
    取得閱讀測驗背景任務的結果。
    """
    job = reading_test_jobs.get(job_id)
    if not job:
        job = _load_reading_test_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        reading_test_jobs[job_id] = job

    if job["status"] != "completed" or not job.get("result"):
        raise HTTPException(status_code=202, detail="任務尚未完成")

    result = job["result"]
    if isinstance(result, ReadingTestResponse):
        return result
    return ReadingTestResponse(**result)


@router.delete("/reading-test/job/{job_id}")
async def cancel_reading_test_job(job_id: str) -> dict:
    job = reading_test_jobs.get(job_id)
    if not job:
        job = _load_reading_test_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        reading_test_jobs[job_id] = job
    if job["status"] in ("completed", "cancelled"):
        return {"message": "任務已結束"}
    job["status"] = "cancelled"
    job["message"] = "使用者取消"
    job["completed_at"] = datetime.utcnow()
    _persist_reading_test_job(job_id)
    return {"message": "已取消"}


# ========== PDF 匯出 ==========

@router.post("/export-pdf")
async def export_pdf(request: PDFExportRequest):
    """
    生成 TOEIC 測驗 PDF 並以串流方式下載。

    Args:
        request: 包含測驗資料與匯出模式
    """
    from backend.utils.pdf_generator import generate_toeic_pdf
    from fastapi.responses import StreamingResponse
    import io

    valid_modes = ['questions_only', 'answer_key', 'both']
    if request.export_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"export_mode 必須是 {valid_modes} 之一")

    try:
        file_path = generate_toeic_pdf(
            test_data=request.test_data,
            export_mode=request.export_mode,
        )

        with open(file_path, "rb") as f:
            content = f.read()

        os.remove(file_path)

        filename = os.path.basename(file_path)
        if request.export_mode == 'both':
            media_type = "application/zip"
        else:
            media_type = "application/pdf"

        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f">>> PDF 生成失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF 生成失敗：{str(e)}")
