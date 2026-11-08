"""Vietnamese keyword baseline; no external models."""
import re
import unicodedata
from dataclasses import dataclass


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).lower().split())


def duration_seconds(text):
    match = re.fullmatch(r"\s*(\d+)\s*(phút|giờ)\s*[.!]?", text)
    if not match:
        return None
    value = int(match[1]) * (60 if match[2] == "phút" else 3600)
    return value if 0 < value <= 86400 else None


@dataclass(frozen=True)
class Prediction:
    intent: str
    action: str
    confidence: float = 0.9


def classify(text):
    text = normalize(text)
    unknown = Prediction("out_of_scope", "request_clarification", 0.2)
    if not text or re.search(r"\b(đừng|không muốn|không được)\b", text):
        return unknown
    start = bool(re.search(r"\b(bắt đầu (?:phiên )?học|học trong)\b", text))
    cancel = bool(re.search(r"\b(dừng học|hủy (?:phiên(?: học)?)?|huỷ phiên học)\b", text))
    if start and cancel:
        return unknown
    # Reminder content can contain study-related words: handle its prefix first.
    if re.match(r"^(nhắc tôi|nhắc mình)\b", text):
        return Prediction("schedule_reminder", "create_reminder")
    if re.search(r"\b(xem lịch|lịch đã lưu|danh sách lời nhắc)\b", text):
        return Prediction("schedule_reminder", "list_reminders")
    if re.search(r"\b(nhắc lại|nói lại|lặp lại)\b", text):
        return Prediction("repeat_response", "repeat_response")
    if cancel:
        return Prediction("focus_session_control", "cancel_session")
    if start:
        return Prediction("focus_session_control", "start_session")
    if re.search(r"\b(còn bao lâu|còn bao nhiêu|thời gian còn lại)\b", text):
        return Prediction("check_focus_session", "report_remaining_time")
    if re.search(r"\b(trạng thái phiên|phiên học đang|đang học không)\b", text):
        return Prediction("check_focus_session", "report_status")
    if re.search(r"\b(xin chào|chào(?: bạn| minimate)?)\b", text):
        return Prediction("greeting", "greet")
    if re.search(r"\b(là gì|tại sao|vì sao|như thế nào|làm sao|thế nào|giải thích)\b", text):
        return Prediction("open_question", "conversation_placeholder", 0.8)
    return unknown
