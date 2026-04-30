"""
TOEIC 聽力測驗 API 路由
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pathlib import Path
import shutil
from pydantic import BaseModel
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime
import asyncio
import threading
import uuid
import json
import hashlib
import os
import random
import re
import base64
import time
import subprocess
import math
import wave
from backend.prompt_engine.listening_prompts import ListeningPrompts
from backend.prompt_engine.toeic_response_schemas import (
    TOEICOptionSchema,
    Part1GeneratedResponse,
    Part2GeneratedResponse,
    ListeningQuestionSchema,
)
from backend.ai_clients.ai_client_factory import AIClientFactory
from backend.ai_clients.gemini_tts_client import AVAILABLE_VOICES, MALE_VOICES, FEMALE_VOICES
from backend.database import SessionLocal
from backend.models import QuizJob

router = APIRouter(prefix="/api/listening", tags=["listening"])
listening_prompts = ListeningPrompts()
listening_jobs: Dict[str, Dict[str, Any]] = {}

# TOEIC 考題四種口音（美式、英式、加拿大、澳洲）
TOEIC_ACCENTS = [
    "American English accent",
    "British English accent",
    "Canadian English accent",
    "Australian English accent"
]

# TOEIC 語速選項
TOEIC_PACES = [
    "very slow",
    "slow",
    "moderate",
    "fast",
    "very fast"
]


def get_random_toeic_accent() -> str:
    """隨機選擇一個 TOEIC 口音"""
    return random.choice(TOEIC_ACCENTS)


class ListeningJobStatus(BaseModel):
    job_id: str
    status: str  # pending / running / completed / error
    progress: Dict[str, int]  # generated / total
    message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ListeningJobResult(BaseModel):
    questions: List[dict]


def _serialize_quiz_result(result: Any) -> Optional[str]:
    if result is None:
        return None
    data = result.model_dump() if hasattr(result, "model_dump") else result
    return json.dumps(data, ensure_ascii=False)


def _persist_listening_job(job_id: str) -> None:
    job = listening_jobs.get(job_id)
    if not job:
        return
    db = SessionLocal()
    try:
        record = db.get(QuizJob, job_id)
        if not record:
            record = QuizJob(job_id=job_id)
        record.job_type = "listening"
        record.test_mode = job.get("part")
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


def _load_listening_job(job_id: str) -> Optional[Dict[str, Any]]:
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
            "part": record.test_mode,
        }
    finally:
        db.close()


class Part2Question(BaseModel):
    question_number: int
    question_audio_url: str
    option_audio_urls: List[str]  # [A, B, C] 三個選項音檔
    correct_answer: str  # A, B, C
    question_text: Optional[str] = None
    option_texts: Optional[List[str]] = None


class Part2Request(BaseModel):
    count: int = 25  # Part 2 通常是 25 題
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    provider: str = "openai"  # 舊欄位：文字生成 provider
    model: str = "gpt-4o-mini"  # 舊欄位：文字生成模型
    api_key: str  # 舊欄位：TTS API key
    text_api_key: Optional[str] = None  # 文字生成 API key
    text_provider: Optional[str] = None
    text_model: Optional[str] = None
    tts_provider: Optional[str] = None
    tts_api_key: Optional[str] = None
    accent: Optional[str] = None  # 口音（American/British/Canadian/Australian English accent），None 表示隨機
    pace: Optional[str] = "moderate"  # 語速（very slow/slow/moderate/fast/very fast）


class Part2Response(BaseModel):
    questions: List[Part2Question]


class Part3QuestionSet(BaseModel):
    question_text: str
    options: List[dict]  # [{"label": "A", "text": "..."}, ...]


class Part3Question(BaseModel):
    question_number: int
    conversation_audio_url: str
    scenario: str
    questions: List[Part3QuestionSet]  # 3 個問題
    correct_answers: List[str]  # [A/B/C/D, A/B/C/D, A/B/C/D]
    transcript: Optional[str] = None


class Part3GeneratedConversationLine(BaseModel):
    speaker: Literal["Man", "Woman"]
    text: str


class Part3GeneratedResponse(BaseModel):
    conversation: List[Part3GeneratedConversationLine]
    questions: List[ListeningQuestionSchema]


class Part3Request(BaseModel):
    count: int = 13  # Part 3 通常是 13 組對話
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    provider: str = "openai"  # 舊欄位：文字生成 provider
    model: str = "gpt-4o"  # 舊欄位：文字生成模型
    api_key: str  # 舊欄位：TTS API key
    text_api_key: Optional[str] = None  # 文字生成 API key
    text_provider: Optional[str] = None
    text_model: Optional[str] = None
    tts_provider: Optional[str] = None
    tts_api_key: Optional[str] = None
    accent: Optional[str] = None  # 口音（American/British/Canadian/Australian English accent），None 表示隨機
    pace: Optional[str] = "moderate"  # 語速（very slow/slow/moderate/fast/very fast）


class Part3Response(BaseModel):
    questions: List[Part3Question]


class Part4QuestionSet(BaseModel):
    question_text: str
    options: List[dict]  # [{"label": "A", "text": "..."}, ...]


class Part4Question(BaseModel):
    question_number: int
    talk_audio_url: str
    questions: List[Part4QuestionSet]  # 3 個問題
    correct_answers: List[str]  # [A/B/C/D, A/B/C/D, A/B/C/D]
    transcript: Optional[str] = None


class Part4Request(BaseModel):
    count: int = 10  # Part 4 通常是 10 段獨白
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    provider: str = "openai"  # 舊欄位：文字生成 provider
    model: str = "gpt-4o"  # 舊欄位：文字生成模型
    api_key: str  # 舊欄位：TTS API key
    text_api_key: Optional[str] = None  # 文字生成 API key
    text_provider: Optional[str] = None
    text_model: Optional[str] = None
    tts_provider: Optional[str] = None
    tts_api_key: Optional[str] = None
    accent: Optional[str] = None  # 口音（American/British/Canadian/Australian English accent），None 表示隨機
    pace: Optional[str] = "moderate"  # 語速（very slow/slow/moderate/fast/very fast）


class Part4Response(BaseModel):
    questions: List[Part4Question]


class Part4GeneratedResponse(BaseModel):
    talk: str
    questions: List[ListeningQuestionSchema]


class ListeningExplanationRequest(BaseModel):
    """聽力測驗詳解生成請求"""
    test_mode: str  # part1, part2, part3, part4
    answers: List[dict]  # 答案資料（包含題號、用戶答案、正確答案等）
    provider: str
    model: str
    api_key: Optional[str] = None


class ListeningExplanation(BaseModel):
    """聽力測驗詳解"""
    question_number: int
    sub_question_index: Optional[int] = None  # Part 3/4 用（0, 1, 2）
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str


class Part1Request(BaseModel):
    count: int = 6  # Part 1 通常是 6 題
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    provider: str = "gemini"  # 舊欄位：媒體生成 provider（僅支援 Gemini）
    model: str = "gemini-2.5-flash"  # 舊欄位：媒體生成模型
    api_key: str  # 舊欄位：媒體 API key（Gemini）
    text_api_key: Optional[str] = None  # 文字生成 API key（Gemini Vision 用）
    text_provider: Optional[str] = None
    text_model: Optional[str] = None
    tts_provider: Optional[str] = None
    tts_api_key: Optional[str] = None
    accent: Optional[str] = None  # 口音（American/British/Canadian/Australian English accent），None 表示隨機
    pace: Optional[str] = "moderate"  # 語速（very slow/slow/moderate/fast/very fast）


class Part1Question(BaseModel):
    question_number: int
    image_url: str
    audio_urls: List[str]  # [A, B, C, D] 四個音檔 URL
    option_texts: List[str]  # [A, B, C, D] 四個選項的文字
    correct_answer: str  # A, B, C, D


class Part1Response(BaseModel):
    questions: List[Part1Question]


async def _run_listening_job(job_id: str, part: str, request: BaseModel) -> None:
    job = listening_jobs[job_id]
    job["status"] = "running"
    job["message"] = None
    job["progress"]["generated"] = 0
    _persist_listening_job(job_id)
    try:
        if part == "part1":
            response = await generate_part1_questions(request)
        elif part == "part2":
            response = await generate_part2_questions(request)
        elif part == "part3":
            response = await generate_part3_questions(request)
        elif part == "part4":
            response = await generate_part4_questions(request)
        else:
            raise ValueError("不支援的題型")

        job["result"] = response.model_dump()
        job["progress"]["generated"] = len(response.questions)
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow()
        _persist_listening_job(job_id)
    except Exception as exc:  # noqa: BLE001
        job["status"] = "error"
        job["message"] = str(exc)
        job["completed_at"] = datetime.utcnow()
        _persist_listening_job(job_id)


def _create_listening_job(part: str, request: BaseModel) -> ListeningJobStatus:
    job_id = str(uuid.uuid4())
    total = int(getattr(request, "count", 0) or 0)
    listening_jobs[job_id] = {
        "status": "pending",
        "progress": {"generated": 0, "total": total},
        "message": None,
        "created_at": datetime.utcnow(),
        "completed_at": None,
        "result": None,
        "part": part,
    }
    _persist_listening_job(job_id)

    def _run_in_thread() -> None:
        asyncio.run(_run_listening_job(job_id, part, request))

    threading.Thread(target=_run_in_thread, daemon=True).start()

    return ListeningJobStatus(
        job_id=job_id,
        status="pending",
        progress=listening_jobs[job_id]["progress"],
        message=None,
        created_at=listening_jobs[job_id]["created_at"],
        completed_at=None,
    )


def clean_json_response(text: str) -> str:
    """清理 AI 回應，提取 JSON 內容"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        return json_match.group(0)
    return text.strip()


def parse_json_response(text: str) -> dict:
    """Parse JSON with a light cleanup fallback for model responses."""
    cleaned = clean_json_response(text).replace("\ufeff", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        normalized = (
            cleaned
            .replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
        normalized = re.sub(r",(\s*[}\]])", r"\1", normalized)
        return json.loads(normalized)


def pick_random_gemini_voice(exclude: Optional[set[str]] = None) -> str:
    """Pick a random Gemini TTS voice, optionally excluding some voices."""
    exclude = exclude or set()
    candidates = [voice for voice in AVAILABLE_VOICES if voice not in exclude]
    if not candidates:
        candidates = AVAILABLE_VOICES
    return random.choice(candidates)


def _get_wav_duration_seconds(path: str) -> float:
    try:
        with wave.open(path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if rate == 0:
                return 0.0
            return frames / float(rate)
    except Exception as exc:
        print(f">>> wav duration read failed: {exc}")
        return 0.0


def _split_audio_by_silence(input_path: str, output_paths: List[str]) -> bool:
    """
    Use ffmpeg silencedetect to split a single WAV into multiple segments.
    Dynamically handles different number of outputs (e.g., 3 for Part 2, 4 for Part 1).
    """
    num_outputs = len(output_paths)
    num_silences_needed = num_outputs - 1  # 3 個輸出需要 2 個靜音，4 個輸出需要 3 個靜音

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                input_path,
                "-af",
                "silencedetect=noise=-35dB:d=0.4",
                "-f",
                "null",
                "-"
            ],
            capture_output=True,
            text=True,
            check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        stderr = exc.stderr if hasattr(exc, "stderr") else str(exc)
        print(f">>> ffmpeg silencedetect failed: {stderr}")
        return False

    silence_starts: List[float] = []
    silence_ends: List[float] = []
    for line in result.stderr.splitlines():
        if "silence_start" in line:
            try:
                silence_starts.append(float(line.split("silence_start:")[1].strip()))
            except ValueError:
                continue
        if "silence_end" in line:
            try:
                silence_ends.append(float(line.split("silence_end:")[1].split("|")[0].strip()))
            except ValueError:
                continue

    if len(silence_starts) < num_silences_needed or len(silence_ends) < num_silences_needed:
        print(
            f">>> silencedetect insufficient: starts={len(silence_starts)} ends={len(silence_ends)}, needed={num_silences_needed}"
        )
        return False

    duration = _get_wav_duration_seconds(input_path)
    if duration <= 0:
        print(">>> silencedetect failed: invalid duration")
        return False

    silence_pairs_with_len: List[tuple[float, float, float]] = []
    for start, end in zip(silence_starts, silence_ends):
        if end <= start:
            continue
        gap = end - start
        if gap < 0.4:
            continue
        silence_pairs_with_len.append((start, end, gap))

    if len(silence_pairs_with_len) < num_silences_needed:
        print(f">>> silencedetect insufficient after filter: {silence_pairs_with_len}, needed={num_silences_needed}")
        return False

    silence_pairs_with_len.sort(key=lambda item: item[2], reverse=True)
    top_pairs = silence_pairs_with_len[:num_silences_needed]
    top_pairs.sort(key=lambda item: item[0])
    silence_pairs = [(start, end) for start, end, _ in top_pairs]
    print(f">>> silencedetect pairs (longest): {silence_pairs}")

    # 動態生成邊界
    boundaries = [(0.0, silence_pairs[0][0])]  # 第一個片段
    for i in range(num_silences_needed - 1):
        boundaries.append((silence_pairs[i][1], silence_pairs[i + 1][0]))
    boundaries.append((silence_pairs[-1][1], duration))  # 最後一個片段

    for idx in range(num_outputs):
        start = max(0.0, boundaries[idx][0])
        end = max(start, boundaries[idx][1])
        print(f">>> split segment {idx + 1}: {start:.3f}s -> {end:.3f}s")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-y",
                    "-i",
                    input_path,
                    "-ss",
                    f"{start:.3f}",
                    "-to",
                    f"{end:.3f}",
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    output_paths[idx],
                ],
                capture_output=True,
                text=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            stderr = exc.stderr if hasattr(exc, "stderr") else str(exc)
            print(f">>> ffmpeg split failed: {stderr}")
            return False

    return True


async def generate_tts_audio(
    text: str,
    provider: str,
    api_key: str,
    voice: str = "alloy",
    speed: float = 1.0,
    accent: Optional[str] = None,
    pace: Optional[str] = "moderate"
) -> str:
    """
    生成 TTS 音訊檔案（僅支援 Gemini）

    Args:
        text: 要轉換的文字
        provider: AI provider ("gemini")
        api_key: API 金鑰
        voice: 聲音名稱
        speed: 語速（已棄用，請使用 pace）
        accent: TOEIC 口音（可選）
        pace: 語速（very slow/slow/moderate/fast/very fast）

    Returns:
        音訊 URL（/audio/xxx.wav）
    """
    if provider.lower() != "gemini":
        raise HTTPException(status_code=400, detail="TTS 僅支援 Gemini")

    voice_to_use = voice if voice and voice != "alloy" else pick_random_gemini_voice()

    # 計算音訊檔案名稱（基於文字 + 聲音 + 口音 + 語速 hash）
    hash_input = f"{text}|{voice_to_use}|{accent}|{pace}"
    audio_hash = hashlib.md5(hash_input.encode()).hexdigest()

    audio_filename = f"{audio_hash}.wav"  # Gemini TTS 輸出 WAV

    audio_path = f"data/audio_cache/{audio_filename}"
    os.makedirs("data/audio_cache", exist_ok=True)

    # 如果音檔已存在，直接返回
    if os.path.exists(audio_path):
        return f"/audio/{audio_filename}"

    # 生成音檔
    try:
        from backend.ai_clients.gemini_tts_client import GeminiTTSClient

        tts_client = GeminiTTSClient(api_key=api_key, model="gemini-2.5-flash-preview-tts", voice=voice_to_use)
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(2 ** attempt)

                tts_client.generate_speech_file(
                    text=text,
                    output_path=audio_path,
                    voice=voice_to_use,
                    accent=accent,
                    pace=pace
                )
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error:
            raise last_error

        return f"/audio/{audio_filename}"

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS 音檔生成失敗: {str(e)}")


async def generate_part2_question(
    question_number: int,
    difficulty: str,
    text_provider: str,
    text_model: str,
    tts_provider: str,
    tts_api_key: str,
    text_api_key: Optional[str] = None,
    accent: Optional[str] = None,
    pace: Optional[str] = "moderate",
    topic_hint: Optional[str] = None,
) -> Part2Question:
    """
    生成單個 Part 2 題目（問答題）

    Args:
        question_number: 題號
        difficulty: 難度 (easy/medium/hard)
        text_provider: AI provider for text generation
        text_model: AI model for text generation
        tts_provider: TTS provider ("gemini")
        tts_api_key: TTS API key
        text_api_key: Text generation API key
        accent: 口音（None 表示隨機）
        pace: 語速

    Returns:
        Part2Question: 生成的題目
    """
    from backend.ai_clients.ai_client_factory import AIClientFactory
    from backend.prompt_engine.listening_prompts import PART2_TOPICS

    # AI client for text generation
    text_client = AIClientFactory.create_client(
        provider=text_provider,
        model=text_model,
        api_key=text_api_key
    )

    # 1. 從 TOEIC 13 大主題中選擇一個情境（優先使用外部傳入的 topic_hint）
    if topic_hint is None:
        topic_hint = random.choice(PART2_TOPICS)

    # 2. 使用 AI 生成問題和回應
    try:
        print(f">>> 開始生成 Part 2 題目 #{question_number} (Provider: {text_provider}, Model: {text_model})")
        prompt = listening_prompts.get_part2_generation_prompt(difficulty, topic_hint=topic_hint)

        if text_provider == "gemini" and hasattr(text_client, "generate_with_schema"):
            print(f">>> 使用 Gemini Schema 模式生成...")
            response_text = text_client.generate_with_schema(
                prompt=prompt,
                response_schema=Part2GeneratedResponse
            )
            qa_data = json.loads(response_text)
        else:
            print(f">>> 使用標準模式生成...")
            response_text = text_client._generate_response(prompt)
            cleaned_text = clean_json_response(response_text)
            qa_data = json.loads(cleaned_text)

        print(f">>> AI 文字生成完成")

    except Exception as e:
        print(f"❌ AI 生成題目失敗: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI 生成題目失敗: {type(e).__name__}: {str(e)}")

    # 2. 從 AI 生成的結果中提取選項和正確答案
    # AI 已經按照 schema 生成了隨機排列的選項和正確答案標籤
    options = [opt["text"] for opt in qa_data["options"]]
    correct_answer = qa_data["correct_answer"]

    # 3. 生成音檔（改為單人 TTS，避免 Multi-Speaker Bug）
    if tts_provider.lower() != "gemini":
        raise HTTPException(status_code=400, detail="Part 2 TTS 僅支援 Gemini")

    from backend.ai_clients.gemini_tts_client import GeminiTTSClient

    question_text = qa_data["question"]
    labeled_options = [f"{chr(65 + idx)}. {opt}" for idx, opt in enumerate(options)]
    woman_voice = random.choice(FEMALE_VOICES) if FEMALE_VOICES else AVAILABLE_VOICES[0]
    man_voice = random.choice(MALE_VOICES) if MALE_VOICES else AVAILABLE_VOICES[0]

    os.makedirs("data/audio_cache", exist_ok=True)

    # 選擇口音（使用用戶指定或隨機選擇）
    question_accent = accent or get_random_toeic_accent()
    options_accent = accent or get_random_toeic_accent()

    # ========== 第一次 TTS：生成問題音檔（Woman 聲音） ==========
    question_hash = hashlib.md5(f"{question_text}|{woman_voice}|{question_accent}|{pace}".encode()).hexdigest()
    question_filename = f"part2_q_{question_hash}.wav"
    question_path = f"data/audio_cache/{question_filename}"

    if not os.path.exists(question_path):
        print(f">>> 正在生成 Part 2 問題音檔（聲音: {woman_voice}）...")
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    print(f">>> 問題音檔重試 {attempt}/2...")
                    time.sleep(2 ** attempt)
                tts_client = GeminiTTSClient(
                    api_key=tts_api_key,
                    model="gemini-2.5-flash-preview-tts",
                    voice=woman_voice
                )
                tts_client.generate_speech_file(
                    text=question_text,
                    output_path=question_path,
                    voice=woman_voice,
                    accent=question_accent,
                    pace=pace
                )
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error:
            raise HTTPException(status_code=500, detail=f"問題 TTS 生成失敗: {str(last_error)}")
        print(f">>> 問題音檔生成成功: {question_filename}")

    # ========== 第二次 TTS：生成選項合併音檔（Man 聲音）+ 切割 ==========
    # 使用 Gemini TTS 官方 wait 語法（避免 [long pause] bug）
    parts = [f'Say "{labeled_options[0]}"']
    for opt in labeled_options[1:]:
        parts.append(f'wait 1 second then say "{opt}"')
    combined_options_text = ", ".join(parts) + "."
    options_hash = hashlib.md5(f"{combined_options_text}|{man_voice}|{options_accent}|{pace}".encode()).hexdigest()
    combined_options_filename = f"part2_opts_{options_hash}.wav"
    combined_options_path = f"data/audio_cache/{combined_options_filename}"
    option_filenames = [f"part2_opts_{options_hash}_{idx + 1}.wav" for idx in range(3)]
    option_paths = [f"data/audio_cache/{name}" for name in option_filenames]

    if not os.path.exists(combined_options_path):
        print(f">>> 正在生成 Part 2 選項合併音檔（聲音: {man_voice}）...")
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    print(f">>> 選項音檔重試 {attempt}/2...")
                    time.sleep(2 ** attempt)
                tts_client = GeminiTTSClient(
                    api_key=tts_api_key,
                    model="gemini-2.5-flash-preview-tts",
                    voice=man_voice
                )
                tts_client.generate_speech_file(
                    text=combined_options_text,
                    output_path=combined_options_path,
                    voice=man_voice,
                    accent=options_accent,
                    pace=pace
                )
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error:
            raise HTTPException(status_code=500, detail=f"選項 TTS 生成失敗: {str(last_error)}")
        print(f">>> 選項合併音檔生成成功: {combined_options_filename}")

    # 切割選項音檔為 A, B, C
    if not all(os.path.exists(path) for path in option_paths):
        print(f">>> 正在切割選項音檔...")
        if not _split_audio_by_silence(combined_options_path, option_paths):
            print(f">>> ⚠️ 切割失敗，改用逐個生成 Fallback...")
            # Fallback: 切割失敗則逐個生成
            for idx, opt_text in enumerate(labeled_options):
                audio_hash = hashlib.md5(f"{opt_text}|{man_voice}|{options_accent}".encode()).hexdigest()
                audio_filename = f"{audio_hash}.wav"
                audio_path = f"data/audio_cache/{audio_filename}"

                if not os.path.exists(audio_path):
                    last_error: Optional[Exception] = None
                    for attempt in range(3):
                        try:
                            if attempt > 0:
                                time.sleep(2 ** attempt)
                            tts_client = GeminiTTSClient(
                                api_key=tts_api_key,
                                model="gemini-2.5-flash-preview-tts",
                                voice=man_voice
                            )
                            tts_client.generate_speech_file(
                                text=opt_text,
                                output_path=audio_path,
                                voice=man_voice,
                                style_prompt=f"Style: clear and natural. Accent: {options_accent}."
                            )
                            last_error = None
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_error = exc

                    if last_error:
                        raise HTTPException(status_code=500, detail=f"選項 {chr(65 + idx)} TTS 生成失敗: {str(last_error)}")
                    print(f">>> Gemini TTS 音檔生成: {audio_filename}")

                option_paths[idx] = audio_path
        else:
            print(f">>> 選項音檔切割成功")

    # 組裝最終音檔列表
    question_audio_url = f"/audio/{os.path.basename(question_path)}"
    option_audio_urls = [f"/audio/{os.path.basename(path)}" for path in option_paths]

    return Part2Question(
        question_number=question_number,
        question_audio_url=question_audio_url,
        option_audio_urls=option_audio_urls,
        correct_answer=correct_answer,
        question_text=question_text,
        option_texts=options
    )


async def generate_part3_question(
    question_number: int,
    difficulty: str,
    text_provider: str,
    text_model: str,
    tts_provider: str,
    tts_api_key: str,
    text_api_key: Optional[str] = None,
    accent: Optional[str] = None,
    pace: Optional[str] = "moderate",
    topic_hint: Optional[str] = None,
) -> Part3Question:
    """
    生成單個 Part 3 題目（對話題）

    Args:
        question_number: 題號
        difficulty: 難度 (easy/medium/hard)
        text_provider: AI provider for text generation
        text_model: AI model for text generation
        tts_provider: TTS provider ("gemini")
        tts_api_key: TTS API key
        text_api_key: Text generation API key
        accent: 口音（None 表示隨機）
        pace: 語速

    Returns:
        Part3Question: 生成的題目
    """
    from backend.ai_clients.ai_client_factory import AIClientFactory
    from backend.prompt_engine.listening_prompts import PART3_TOPICS

    # AI client for text generation
    text_client = AIClientFactory.create_client(
        provider=text_provider,
        model=text_model,
        api_key=text_api_key
    )

    # 1. 從 TOEIC 13 大主題中選擇一個對話情境（優先使用外部傳入的 topic_hint）
    try:
        if topic_hint is None:
            topic_hint = random.choice(PART3_TOPICS)
        scenario = topic_hint

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"選擇對話場景失敗: {str(e)}")

    # 2. 使用 AI 生成對話和問題
    try:
        prompt = listening_prompts.get_part3_generation_prompt(scenario, difficulty, topic_hint=topic_hint)

        if text_provider == "gemini" and hasattr(text_client, "generate_with_schema"):
            response_text = text_client.generate_with_schema(
                prompt=prompt,
                response_schema=Part3GeneratedResponse
            )
            conv_data = json.loads(response_text)
        else:
            response_text = text_client._generate_response(prompt)
            cleaned_text = clean_json_response(response_text)
            conv_data = json.loads(cleaned_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 生成對話失敗: {str(e)}")

    # 3. 生成對話音檔（為每個說話者使用不同聲音）
    try:
        if tts_provider.lower() != "gemini":
            raise HTTPException(status_code=400, detail="Part 3 TTS 僅支援 Gemini")

        normalized_conversation = []
        allowed_speakers = {"Man", "Woman"}
        for idx, line in enumerate(conv_data["conversation"]):
            speaker = line.get("speaker", "Man")
            if speaker not in allowed_speakers:
                speaker = "Man" if idx % 2 == 0 else "Woman"
            normalized_conversation.append({
                "speaker": speaker,
                "text": line["text"]
            })

        conv_data["conversation"] = normalized_conversation

        man_voice = random.choice(MALE_VOICES) if MALE_VOICES else AVAILABLE_VOICES[0]
        woman_voice = random.choice(FEMALE_VOICES) if FEMALE_VOICES else AVAILABLE_VOICES[0]

        # 選擇口音（使用指定或隨機選擇，男女聲各自獨立）
        man_accent = accent or get_random_toeic_accent()
        woman_accent = accent or get_random_toeic_accent()

        gemini_voice_mapping = {
            "Man": man_voice,
            "Woman": woman_voice,
        }

        # 組合對話文字（用於生成檔案名稱）
        conversation_text = " ".join([line['text'] for line in normalized_conversation])
        voice_signature = f"Man:{man_voice}|Woman:{woman_voice}|ManAccent:{man_accent}|WomanAccent:{woman_accent}|Pace:{pace}"
        conv_hash = hashlib.md5(f"{conversation_text}|{voice_signature}".encode()).hexdigest()

        # Gemini TTS 輸出 WAV
        audio_ext = "wav"
        conv_filename = f"part3_{conv_hash}.{audio_ext}"
        conv_path = f"data/audio_cache/{conv_filename}"

        os.makedirs("data/audio_cache", exist_ok=True)

        if not os.path.exists(conv_path):
            # ===== Gemini: 使用 Multi-Speaker TTS =====
            print(
                ">>> 正在使用 Gemini Multi-Speaker TTS 生成對話音檔"
                f"（Man: {man_voice}, Woman: {woman_voice}）..."
            )

            from backend.ai_clients.gemini_tts_client import GeminiTTSClient

            tts_client = GeminiTTSClient(
                api_key=tts_api_key,
                model="gemini-2.5-flash-preview-tts",
                voice=man_voice
            )

            last_error: Optional[Exception] = None
            for attempt in range(3):
                try:
                    if attempt > 0:
                        time.sleep(2 ** attempt)
                    # 注意：Director's Notes 的 accent 和 pace 是全局的，會影響所有 speaker
                    # 如果指定了 accent，則兩個 speaker 都使用相同口音
                    tts_client.generate_multi_speaker_speech_file(
                        conversation=normalized_conversation,
                        output_path=conv_path,
                        voice_mapping=gemini_voice_mapping,
                        accent=man_accent if accent else None,  # 只有用戶指定時才使用
                        pace=pace
                    )
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc

            if last_error:
                raise last_error

            print(">>> Gemini Multi-Speaker TTS 生成成功")

        conversation_audio_url = f"/audio/{conv_filename}"

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TTS 對話音檔生成失敗: {str(e)}")

    # 4. 組織問題和答案
    questions = []
    correct_answers = []

    for q in conv_data["questions"]:
        questions.append(Part3QuestionSet(
            question_text=q["question_text"],
            options=q["options"]
        ))
        correct_answers.append(q["correct_answer"])

    # 5. 生成逐字稿
    transcript_lines = []
    for line in conv_data["conversation"]:
        transcript_lines.append(f"{line['speaker']}: {line['text']}")
    transcript = "\n".join(transcript_lines)

    return Part3Question(
        question_number=question_number,
        conversation_audio_url=conversation_audio_url,
        scenario=scenario,
        questions=questions,
        correct_answers=correct_answers,
        transcript=transcript
    )


async def generate_part4_question(
    question_number: int,
    difficulty: str,
    text_provider: str,
    text_model: str,
    tts_provider: str,
    tts_api_key: str,
    text_api_key: Optional[str] = None,
    accent: Optional[str] = None,
    pace: Optional[str] = "moderate",
    topic_hint: Optional[str] = None,
) -> Part4Question:
    """
    生成單個 Part 4 題目（獨白題）

    Args:
        question_number: 題號
        difficulty: 難度 (easy/medium/hard)
        text_provider: 文字生成 provider (ollama/openai/gemini)
        text_model: 文字生成模型
        tts_provider: TTS provider ("gemini")
        tts_api_key: TTS API key
        text_api_key: 文字生成 API key (可選)
        accent: 口音（None 表示隨機）
        pace: 語速

    Returns:
        Part4Question: 生成的題目
    """
    # AI client (文字生成)
    from backend.prompt_engine.listening_prompts import PART4_TOPICS

    text_client = AIClientFactory.create_client(
        provider=text_provider,
        model=text_model,
        api_key=text_api_key
    )

    # 1. 從 TOEIC 13 大主題中選擇一個獨白情境（優先使用外部傳入的 topic_hint）
    try:
        if topic_hint is None:
            topic_hint = random.choice(PART4_TOPICS)
        talk_topic = topic_hint
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"選擇獨白主題失敗: {str(e)}")

    # 2. 使用 AI 生成獨白和問題
    try:
        prompt = listening_prompts.get_part4_generation_prompt(talk_topic, difficulty, topic_hint=topic_hint)

        if text_provider == "gemini" and hasattr(text_client, "generate_with_schema"):
            response_text = text_client.generate_with_schema(
                prompt=prompt,
                response_schema=Part4GeneratedResponse
            )
            talk_data = json.loads(response_text)
        else:
            response_text = text_client._generate_response(prompt)
            cleaned_text = clean_json_response(response_text)
            talk_data = json.loads(cleaned_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 生成獨白失敗: {str(e)}")

    # 3. 生成獨白音檔
    try:
        talk_text = talk_data["talk"]
        # 選擇口音（使用指定或隨機選擇）
        talk_accent = accent or get_random_toeic_accent()
        # 使用統一的 TTS 函數生成音檔
        talk_audio_url = await generate_tts_audio(
            text=talk_text,
            provider=tts_provider,
            api_key=tts_api_key,
            voice=None,
            speed=0.95,
            accent=talk_accent,
            pace=pace
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS 獨白音檔生成失敗: {str(e)}")

    # 4. 組織問題和答案
    questions = []
    correct_answers = []

    for q in talk_data["questions"]:
        questions.append(Part4QuestionSet(
            question_text=q["question_text"],
            options=q["options"]
        ))
        correct_answers.append(q["correct_answer"])

    return Part4Question(
        question_number=question_number,
        talk_audio_url=talk_audio_url,
        questions=questions,
        correct_answers=correct_answers,
        transcript=talk_text
    )


async def generate_part1_question(
    question_number: int,
    difficulty: str,
    provider: str,
    model: str,
    media_api_key: str,
    text_api_key: Optional[str] = None,
    max_retries: int = 3,
    accent: Optional[str] = None,
    pace: Optional[str] = "moderate"
) -> Part1Question:
    """
    反向生成 Part 1 題目：COCO 描述 → 圖片 → Vision AI 生成選項 → TTS
    使用 Gemini (Imagen 4 + Gemini Vision + Gemini TTS)

    Args:
        question_number: 題號
        difficulty: 難度 (easy/medium/hard)
        provider: AI provider ("gemini")
        model: Vision model name (Gemini)
        media_api_key: Gemini API key
        text_api_key: Text generation API key (Gemini 使用)
        max_retries: 最大重試次數（遇到 safety violation 時重新選擇 COCO 描述）
        accent: 口音（None 表示隨機）
        pace: 語速

    Returns:
        Part1Question: 生成的題目
    """
    from backend.utils.coco_caption_loader import get_coco_caption_loader

    if provider.lower() != "gemini":
        raise HTTPException(status_code=400, detail="Part 1 媒體生成僅支援 Gemini")

    api_key = text_api_key or media_api_key

    from backend.ai_clients.gemini_imagen_client import GeminiImagenClient
    from backend.ai_clients.gemini_tts_client import GeminiTTSClient
    from google import genai
    from google.genai import types as genai_types

    imagen_client = GeminiImagenClient(api_key=api_key)
    tts_client = GeminiTTSClient(api_key=api_key, model="gemini-2.5-flash-preview-tts", voice="Puck")
    vision_client = genai.Client(api_key=api_key)
    print(">>> 使用 Gemini (gemini-2.5-flash-image + Gemini Vision + Gemini TTS)")

    # 重試邏輯：如果遇到 safety violation 或其他圖片生成錯誤，重新選擇 COCO 描述
    last_error = None
    img_path = None

    for attempt in range(max_retries):
        # 1. 從 COCO captions 中隨機選擇一個描述
        try:
            coco_loader = get_coco_caption_loader()
            image_prompt = coco_loader.get_random_captions(1)[0]

            if attempt > 0:
                print(f">>> [重試 {attempt}/{max_retries}] 重新選中 COCO 描述: {image_prompt}")
            else:
                print(f">>> 選中 COCO 描述: {image_prompt}")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"載入 COCO caption 失敗: {str(e)}")

        # 2. 生成圖片
        try:
            img_hash = hashlib.md5(image_prompt.encode()).hexdigest()
            img_filename = f"{img_hash}.png"
            img_path = f"data/listening_images/{img_filename}"
            os.makedirs("data/listening_images", exist_ok=True)

            # 使用 Gemini Imagen 4
            images = imagen_client.generate_image(
                prompt=image_prompt,
                number_of_images=1,
                aspect_ratio="1:1"
            )
            img_data = images[0]

            with open(img_path, 'wb') as f:
                f.write(img_data)

            print(f">>> Imagen 4 圖片生成成功: {img_path}")

            # 圖片生成成功，跳出重試循環
            break

        except Exception as e:
            error_msg = str(e)
            last_error = e

            # 檢查是否為 safety violation
            is_safety_violation = any(
                keyword in error_msg.lower()
                for keyword in ['safety', 'blocked', 'policy', 'prohibited', 'inappropriate', 'offensive', 'moderation']
            )

            if is_safety_violation:
                print(f">>> ⚠️ 圖片因安全檢查被拒絕，正在重試... (嘗試 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue  # 重新選擇 COCO 描述並重試
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"圖片生成失敗（已重試 {max_retries} 次）: {error_msg}"
                    )
            else:
                # 非安全問題的錯誤，直接拋出
                raise HTTPException(status_code=500, detail=f"圖片生成失敗: {error_msg}")

    # 如果所有重試都失敗
    if not img_path or not os.path.exists(img_path):
        raise HTTPException(
            status_code=500,
            detail=f"圖片生成失敗（已重試 {max_retries} 次）: {str(last_error)}"
        )

    # 3. 使用 Vision AI 分析圖片並生成描述（失敗時重試）
    try:
        with open(img_path, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')

        vision_prompt = listening_prompts.get_part1_vision_prompt(difficulty)
        descriptions_data = None
        last_error = None

        for attempt in range(3):
            prompt = vision_prompt
            if attempt > 0:
                prompt += "\n\nOnly return valid JSON. Use double quotes and no trailing commas."
                print(f">>> Vision JSON 解析失敗，重試 {attempt}/2")

            try:
                response_text = ""
                for overload_attempt in range(3):
                    try:
                        response = vision_client.models.generate_content(
                            model=model or "gemini-2.5-flash-lite",
                            contents=[
                                genai_types.Part.from_bytes(
                                    data=base64.b64decode(img_base64),
                                    mime_type="image/png",
                                ),
                                prompt,
                            ],
                            config=genai_types.GenerateContentConfig(
                                temperature=0.3,
                                response_mime_type="application/json",
                                response_json_schema=Part1GeneratedResponse.model_json_schema()
                            )
                        )
                        response_text = response.text or ""
                        descriptions_data = parse_json_response(response_text)
                        print(">>> Gemini Vision 分析成功")
                        break
                    except Exception as e:
                        msg = str(e)
                        is_overloaded = any(k in msg for k in ["503", "UNAVAILABLE", "overloaded"])
                        if is_overloaded and overload_attempt < 2:
                            time.sleep(1.5 * (2 ** overload_attempt))
                            continue
                        raise

                if descriptions_data:
                    break
            except Exception as e:
                last_error = e
                descriptions_data = None

        if not descriptions_data:
            raise HTTPException(status_code=500, detail=f"Vision AI 分析失敗: {str(last_error)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision AI 分析失敗: {str(e)}")

    # 4. 生成音檔
    descriptions = [
        descriptions_data["correct_description"],
        descriptions_data["distractor_1"],
        descriptions_data["distractor_2"],
        descriptions_data["distractor_3"]
    ]

    # 隨機排列選項
    random.shuffle(descriptions)
    correct_index = descriptions.index(descriptions_data["correct_description"])
    correct_answer = chr(65 + correct_index)  # A, B, C, D

    audio_urls = []
    os.makedirs("data/audio_cache", exist_ok=True)

    voice_to_use = pick_random_gemini_voice()
    selected_accent = accent or get_random_toeic_accent()  # 使用指定或隨機選擇 TOEIC 口音
    labeled_descriptions = [f"{chr(65 + idx)}. {desc}" for idx, desc in enumerate(descriptions)]
    # 使用 Gemini TTS 官方 wait 語法（避免 [long pause] bug）
    parts = [f'Say "{labeled_descriptions[0]}"']
    for desc in labeled_descriptions[1:]:
        parts.append(f'wait 1 second then say "{desc}"')
    combined_text = ", ".join(parts) + "."
    combined_hash = hashlib.md5(f"{combined_text}|{voice_to_use}|{selected_accent}|{pace}".encode()).hexdigest()
    combined_filename = f"part1_{combined_hash}.wav"
    combined_path = f"data/audio_cache/{combined_filename}"
    option_filenames = [f"part1_{combined_hash}_{idx + 1}.wav" for idx in range(4)]
    option_paths = [f"data/audio_cache/{name}" for name in option_filenames]

    if not os.path.exists(combined_path):
        try:
            last_error: Optional[Exception] = None
            for attempt in range(3):
                try:
                    if attempt > 0:
                        time.sleep(2 ** attempt)
                    tts_client.generate_speech_file(
                        text=combined_text,
                        output_path=combined_path,
                        voice=voice_to_use,
                        accent=selected_accent,
                        pace=pace
                    )
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc

            if last_error:
                raise last_error
            print(f">>> Gemini TTS 合成音檔生成: {combined_filename}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS 音檔生成失敗: {str(e)}")

    if not all(os.path.exists(path) for path in option_paths):
        if not _split_audio_by_silence(combined_path, option_paths):
            # fallback: individual generation if split fails
            for idx, desc in enumerate(labeled_descriptions):
                audio_hash = hashlib.md5(f"{desc}|{voice_to_use}|{accent}".encode()).hexdigest()
                audio_filename = f"{audio_hash}.wav"
                audio_path = f"data/audio_cache/{audio_filename}"
                if not os.path.exists(audio_path):
                    try:
                        last_error: Optional[Exception] = None
                        for attempt in range(3):
                            try:
                                if attempt > 0:
                                    time.sleep(2 ** attempt)
                                tts_client.generate_speech_file(
                                    text=desc,
                                    output_path=audio_path,
                                    voice=voice_to_use,
                                    style_prompt=f"Style: clear and natural. Accent: {accent}."
                                )
                                last_error = None
                                break
                            except Exception as exc:  # noqa: BLE001
                                last_error = exc

                        if last_error:
                            raise last_error
                        print(f">>> Gemini TTS 音檔生成: {audio_filename}")
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=f"TTS 音檔生成失敗: {str(e)}")
                option_paths[idx] = audio_path

    for path in option_paths:
        audio_urls.append(f"/audio/{os.path.basename(path)}")

    return Part1Question(
        question_number=question_number,
        image_url=f"/images/part1/{img_filename}",
        audio_urls=audio_urls,
        option_texts=descriptions,
        correct_answer=correct_answer
    )


@router.post("/generate-part1", response_model=Part1Response)
async def generate_part1_questions(request: Part1Request):
    """
    生成 TOEIC Part 1 照片描述題

    Args:
        request: Part 1 生成請求

    Returns:
        Part1Response: 生成的題目列表
    """
    # 驗證參數
    if request.count < 1 or request.count > 10:
        raise HTTPException(status_code=400, detail="題數必須在 1-10 之間")

    media_provider = request.tts_provider or request.provider
    media_api_key = request.tts_api_key or request.api_key
    text_api_key = request.text_api_key or media_api_key
    vision_model = request.text_model or request.model or "gemini-2.5-flash"

    if media_provider.lower() != "gemini":
        raise HTTPException(status_code=400, detail="Part 1 媒體生成僅支援 Gemini")
    if not media_api_key:
        raise HTTPException(status_code=400, detail="請提供有效的 Gemini API Key")

    # 生成題目
    questions = []
    for i in range(request.count):
        try:
            question = await generate_part1_question(
                question_number=i + 1,
                difficulty=request.difficulty,
                provider=media_provider,
                model=vision_model,
                media_api_key=media_api_key,
                text_api_key=text_api_key,
                accent=request.accent,
                pace=request.pace
            )
            questions.append(question)
        except Exception as e:
            # 如果某題生成失敗，記錄錯誤但繼續生成其他題目
            print(f"題目 {i + 1} 生成失敗: {str(e)}")
            if len(questions) == 0 and i == request.count - 1:
                # 如果所有題目都失敗了，拋出錯誤
                raise HTTPException(status_code=500, detail=f"題目生成失敗: {str(e)}")

    if len(questions) == 0:
        raise HTTPException(status_code=500, detail="無法生成任何題目")

    return Part1Response(questions=questions)


@router.post("/generate-part2", response_model=Part2Response)
async def generate_part2_questions(request: Part2Request):
    """
    生成 TOEIC Part 2 應答問題

    Args:
        request: Part 2 生成請求

    Returns:
        Part2Response: 生成的題目列表
    """
    # 驗證參數
    if request.count < 1 or request.count > 25:
        raise HTTPException(status_code=400, detail="題數必須在 1-25 之間")

    text_provider = request.text_provider or request.provider
    text_model = request.text_model or request.model
    tts_provider = request.tts_provider or "gemini"
    tts_api_key = request.tts_api_key or request.api_key
    text_api_key = request.text_api_key or (tts_api_key if text_provider in {"openai", "gemini"} else None)

    if tts_provider.lower() != "gemini":
        raise HTTPException(status_code=400, detail="Part 2 TTS 僅支援 Gemini")
    if not tts_api_key:
        raise HTTPException(status_code=400, detail="請提供有效的 Gemini API Key")
    if text_provider in {"openai", "gemini"} and not text_api_key:
        raise HTTPException(status_code=400, detail="請提供有效的文字生成 API Key")

    # 預建不重複主題清單（shuffle 後依序取用，確保同批無重複）
    from backend.prompt_engine.listening_prompts import PART2_TOPICS as _P2
    _pool = _P2.copy()
    random.shuffle(_pool)
    topic_list = [_pool[i % len(_pool)] for i in range(request.count)]

    # 生成題目
    questions = []
    for i in range(request.count):
        try:
            question = await generate_part2_question(
                question_number=i + 1,
                difficulty=request.difficulty,
                text_provider=text_provider,
                text_model=text_model,
                tts_provider=tts_provider,
                tts_api_key=tts_api_key,
                text_api_key=text_api_key,
                accent=request.accent,
                pace=request.pace,
                topic_hint=topic_list[i],
            )
            questions.append(question)
        except Exception as e:
            print(f"題目 {i + 1} 生成失敗: {str(e)}")
            if len(questions) == 0 and i == request.count - 1:
                raise HTTPException(status_code=500, detail=f"題目生成失敗: {str(e)}")

    if len(questions) == 0:
        raise HTTPException(status_code=500, detail="無法生成任何題目")

    return Part2Response(questions=questions)


@router.post("/generate-part3", response_model=Part3Response)
async def generate_part3_questions(request: Part3Request):
    """
    生成 TOEIC Part 3 簡短對話題

    Args:
        request: Part 3 生成請求

    Returns:
        Part3Response: 生成的題目列表
    """
    # 驗證參數
    if request.count < 1 or request.count > 13:
        raise HTTPException(status_code=400, detail="對話組數必須在 1-13 之間")

    text_provider = request.text_provider or request.provider
    text_model = request.text_model or request.model
    tts_provider = request.tts_provider or "gemini"
    tts_api_key = request.tts_api_key or request.api_key
    text_api_key = request.text_api_key or (tts_api_key if text_provider in {"openai", "gemini"} else None)

    if tts_provider.lower() != "gemini":
        raise HTTPException(status_code=400, detail="Part 3 TTS 僅支援 Gemini")
    if not tts_api_key:
        raise HTTPException(status_code=400, detail="請提供有效的 Gemini API Key")
    if text_provider in {"openai", "gemini"} and not text_api_key:
        raise HTTPException(status_code=400, detail="請提供有效的文字生成 API Key")

    # 預建不重複主題清單
    from backend.prompt_engine.listening_prompts import PART3_TOPICS as _P3
    _pool = _P3.copy()
    random.shuffle(_pool)
    topic_list = [_pool[i % len(_pool)] for i in range(request.count)]

    # 生成題目
    questions = []
    for i in range(request.count):
        try:
            question = await generate_part3_question(
                question_number=i + 1,
                difficulty=request.difficulty,
                text_provider=text_provider,
                text_model=text_model,
                tts_provider=tts_provider,
                tts_api_key=tts_api_key,
                text_api_key=text_api_key,
                accent=request.accent,
                pace=request.pace,
                topic_hint=topic_list[i],
            )
            questions.append(question)
        except Exception as e:
            print(f"對話組 {i + 1} 生成失敗: {str(e)}")
            if len(questions) == 0 and i == request.count - 1:
                raise HTTPException(status_code=500, detail=f"題目生成失敗: {str(e)}")

    if len(questions) == 0:
        raise HTTPException(status_code=500, detail="無法生成任何題目")

    return Part3Response(questions=questions)


@router.post("/generate-part4", response_model=Part4Response)
async def generate_part4_questions(request: Part4Request):
    """
    生成 TOEIC Part 4 簡短獨白題

    Args:
        request: Part 4 生成請求

    Returns:
        Part4Response: 生成的題目列表
    """
    # 驗證參數
    if request.count < 1 or request.count > 10:
        raise HTTPException(status_code=400, detail="獨白數量必須在 1-10 之間")

    text_provider = request.text_provider or request.provider
    text_model = request.text_model or request.model
    tts_provider = request.tts_provider or "gemini"
    tts_api_key = request.tts_api_key or request.api_key
    text_api_key = request.text_api_key or (tts_api_key if text_provider in {"openai", "gemini"} else None)

    if tts_provider.lower() != "gemini":
        raise HTTPException(status_code=400, detail="Part 4 TTS 僅支援 Gemini")
    if not tts_api_key:
        raise HTTPException(status_code=400, detail="請提供有效的 Gemini API Key")
    if text_provider in {"openai", "gemini"} and not text_api_key:
        raise HTTPException(status_code=400, detail="請提供有效的文字生成 API Key")

    # 預建不重複主題清單
    from backend.prompt_engine.listening_prompts import PART4_TOPICS as _P4
    _pool = _P4.copy()
    random.shuffle(_pool)
    topic_list = [_pool[i % len(_pool)] for i in range(request.count)]

    # 生成題目
    questions = []
    for i in range(request.count):
        try:
            question = await generate_part4_question(
                question_number=i + 1,
                difficulty=request.difficulty,
                text_provider=text_provider,
                text_model=text_model,
                tts_provider=tts_provider,
                tts_api_key=tts_api_key,
                text_api_key=text_api_key,
                accent=request.accent,
                pace=request.pace,
                topic_hint=topic_list[i],
            )
            questions.append(question)
        except Exception as e:
            print(f"獨白 {i + 1} 生成失敗: {str(e)}")
            if len(questions) == 0 and i == request.count - 1:
                raise HTTPException(status_code=500, detail=f"題目生成失敗: {str(e)}")

    if len(questions) == 0:
        raise HTTPException(status_code=500, detail="無法生成任何題目")

    return Part4Response(questions=questions)


@router.post("/generate-part1-job", response_model=ListeningJobStatus)
async def start_part1_job(request: Part1Request) -> ListeningJobStatus:
    """
    背景生成 Part 1 題目。
    """
    return _create_listening_job("part1", request)


@router.post("/generate-part2-job", response_model=ListeningJobStatus)
async def start_part2_job(request: Part2Request) -> ListeningJobStatus:
    """
    背景生成 Part 2 題目。
    """
    return _create_listening_job("part2", request)


@router.post("/generate-part3-job", response_model=ListeningJobStatus)
async def start_part3_job(request: Part3Request) -> ListeningJobStatus:
    """
    背景生成 Part 3 題目。
    """
    return _create_listening_job("part3", request)


@router.post("/generate-part4-job", response_model=ListeningJobStatus)
async def start_part4_job(request: Part4Request) -> ListeningJobStatus:
    """
    背景生成 Part 4 題目。
    """
    return _create_listening_job("part4", request)


@router.get("/generate-job/{job_id}", response_model=ListeningJobStatus)
async def get_listening_job_status(job_id: str) -> ListeningJobStatus:
    """
    查詢聽力題型測驗背景任務狀態。
    """
    job = listening_jobs.get(job_id)
    if not job:
        job = _load_listening_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        listening_jobs[job_id] = job
    return ListeningJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job.get("message"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )


@router.get("/generate-job/{job_id}/result", response_model=ListeningJobResult)
async def get_listening_job_result(job_id: str) -> ListeningJobResult:
    """
    取得聽力題型測驗背景任務結果。
    """
    job = listening_jobs.get(job_id)
    if not job:
        job = _load_listening_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到該任務")
        listening_jobs[job_id] = job
    if job["status"] != "completed" or not job.get("result"):
        raise HTTPException(status_code=202, detail="任務尚未完成")
    return ListeningJobResult(**job["result"])


@router.post("/explain", response_model=List[ListeningExplanation])
async def generate_listening_explanations(request: ListeningExplanationRequest):
    """
    生成聽力測驗詳解

    Args:
        request: 詳解生成請求

    Returns:
        List[ListeningExplanation]: 詳解列表
    """
    try:
        from backend.ai_clients.ai_client_factory import AIClientFactory
        from backend.prompt_engine.prompt_manager import PromptManager

        # 建立 AI 客戶端
        client = AIClientFactory.create_client(
            provider=request.provider,
            model=request.model,
            api_key=request.api_key
        )

        explanations = []

        # Part 1: 圖片描述題（不生成詳解，只返回基本資訊）
        if request.test_mode == "part1":
            for ans in request.answers:
                explanations.append({
                    'question_number': ans['question_number'],
                    'user_answer': ans['user_answer'],
                    'correct_answer': ans['correct_answer'],
                    'is_correct': ans['user_answer'] == ans['correct_answer'],
                    'explanation': '此題為照片描述題，請重新播放音檔並觀察圖片細節，注意人物動作、物品位置和場景特徵。'
                })

        # Part 2: 應答問題
        elif request.test_mode == "part2":
            prompt_manager = PromptManager()
            for ans in request.answers:
                option_texts = ans.get("option_texts") or ["", "", ""]
                prompt = prompt_manager.get_toeic_explanation_prompt(
                    "Part 2 應答問題",
                    {
                        "question_text": ans.get("question_text", ""),
                        "options": [
                            {"label": "A", "text": option_texts[0] if len(option_texts) > 0 else ""},
                            {"label": "B", "text": option_texts[1] if len(option_texts) > 1 else ""},
                            {"label": "C", "text": option_texts[2] if len(option_texts) > 2 else ""},
                        ],
                        "correct_answer": ans["correct_answer"],
                        "user_answer": ans["user_answer"],
                    }
                )

                response_text = client._generate_response(prompt)
                explanations.append({
                    'question_number': ans['question_number'],
                    'user_answer': ans['user_answer'],
                    'correct_answer': ans['correct_answer'],
                    'is_correct': ans['user_answer'] == ans['correct_answer'],
                    'explanation': response_text.strip()
                })

        # Part 3: 簡短對話
        elif request.test_mode == "part3":
            prompt_manager = PromptManager()
            for ans in request.answers:
                # Part 3 每個對話有 3 個子問題
                sub_questions = ans.get('questions', [])
                transcript = ans.get('transcript', '')

                for idx, sub_q in enumerate(sub_questions):
                    user_ans = ans.get('user_answers', [])[idx] if idx < len(ans.get('user_answers', [])) else ''
                    correct_ans = ans.get('correct_answers', [])[idx] if idx < len(ans.get('correct_answers', [])) else ''

                    prompt = prompt_manager.get_toeic_explanation_prompt(
                        "Part 3 簡短對話",
                        {
                            "question_text": sub_q.get("question_text", ""),
                            "options": sub_q.get("options", []),
                            "correct_answer": correct_ans,
                            "user_answer": user_ans,
                            "transcript": transcript,
                        }
                    )

                    response_text = client._generate_response(prompt)
                    explanations.append({
                        'question_number': ans['question_number'],
                        'sub_question_index': idx,
                        'user_answer': user_ans,
                        'correct_answer': correct_ans,
                        'is_correct': user_ans == correct_ans,
                        'explanation': response_text.strip()
                    })

        # Part 4: 簡短獨白
        elif request.test_mode == "part4":
            prompt_manager = PromptManager()
            for ans in request.answers:
                # Part 4 每個獨白有 3 個子問題
                sub_questions = ans.get('questions', [])
                transcript = ans.get('transcript', '')

                for idx, sub_q in enumerate(sub_questions):
                    user_ans = ans.get('user_answers', [])[idx] if idx < len(ans.get('user_answers', [])) else ''
                    correct_ans = ans.get('correct_answers', [])[idx] if idx < len(ans.get('correct_answers', [])) else ''

                    prompt = prompt_manager.get_toeic_explanation_prompt(
                        "Part 4 簡短獨白",
                        {
                            "question_text": sub_q.get("question_text", ""),
                            "options": sub_q.get("options", []),
                            "correct_answer": correct_ans,
                            "user_answer": user_ans,
                            "transcript": transcript,
                        }
                    )

                    response_text = client._generate_response(prompt)
                    explanations.append({
                        'question_number': ans['question_number'],
                        'sub_question_index': idx,
                        'user_answer': user_ans,
                        'correct_answer': correct_ans,
                        'is_correct': user_ans == correct_ans,
                        'explanation': response_text.strip()
                    })

        return [ListeningExplanation(**exp) for exp in explanations]

    except Exception as e:
        print(f">>> 生成聽力測驗詳解失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成詳解失敗：{str(e)}")


@router.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="Only .wav files accepted")
    dest = Path("data/audio_cache") / file.filename
    if not dest.exists():
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
    return {"url": f"/audio/{file.filename}"}


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(status_code=400, detail="Only image files accepted")
    dest = Path("data/listening_images") / file.filename
    if not dest.exists():
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
    return {"url": f"/images/part1/{file.filename}"}
