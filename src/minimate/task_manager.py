import re
from datetime import datetime, timedelta
from .intent_baseline import classify, normalize, duration_seconds, Prediction
from .session_manager import SessionManager


class TaskManager:
    def __init__(self, storage, clock=None):
        self.storage = storage
        self.clock = clock or (lambda: datetime.now().astimezone())
        self.sessions = SessionManager(storage)

    def tick(self):
        with self.storage.connection:
            return self.sessions.expire(self.clock())

    def process(self, raw):
        now = self.clock()
        text = normalize(raw)
        prediction = classify(text)
        with self.storage.connection:
            self.sessions.expire(now)
            state = self.storage.session()['state']
            if state == 'awaiting_duration' and re.fullmatch(r"-?\d+\s*(?:phút|giờ)?[.!]?", text):
                prediction = Prediction('focus_session_control', 'start_session')
            action, message, device = self._execute(prediction.action, text, now)
            response = {
                'intent': prediction.intent, 'confidence': prediction.confidence,
                'action': action, 'text': message, 'device_state': device,
                'session_state': self.storage.session()['state']}
            self.storage.add_command(raw, response, now.isoformat())
        return response

    def _execute(self, action, text, now):
        state = self.storage.session()['state']
        device = 'speaking'
        if action == 'greet':
            message = 'Chào bạn! Bạn muốn học trong bao nhiêu phút?'
        elif action == 'start_session':
            if state == 'active':
                return 'no_op', 'Đang có phiên học. Hãy hủy phiên hiện tại trước.', device
            value = re.sub(r'^.*?(?:bắt đầu (?:phiên )?học|học trong)\s*', '', text)
            seconds = duration_seconds(value)
            if seconds is None:
                self.storage.set_session('awaiting_duration')
                return 'ask_duration', 'Bạn muốn học bao nhiêu phút? Nhập số dương kèm phút/giờ, tối đa 24 giờ.', 'clarification'
            self.sessions.start(seconds, now)
            message = f'Đã bắt đầu phiên học {seconds // 60} phút.'
        elif action == 'cancel_session':
            if state in ('active', 'awaiting_duration'):
                self.storage.set_session('cancelled')
                message = 'Đã hủy phiên học.'
            else:
                action, message = 'no_op', 'Không có phiên học đang chạy để hủy.'
        elif action == 'report_remaining_time':
            seconds = self.sessions.remaining(now)
            message = 'Không có phiên học đang chạy.' if seconds is None else f'Bạn còn {seconds // 60} phút {seconds % 60} giây học.'
        elif action == 'report_status':
            labels = {'idle': 'Chưa có phiên học đang chạy.', 'active': 'Phiên học đang chạy.',
                      'awaiting_duration': 'Đang chờ bạn cung cấp thời lượng học.', 'cancelled': 'Phiên học đã bị hủy.'}
            message = labels[state]
        elif action == 'repeat_response':
            message = self.storage.last_response() or 'Chưa có phản hồi nào để nhắc lại.'
        elif action == 'conversation_placeholder':
            message = 'Module hội thoại sẽ được tích hợp sau. Tuần 9 mình hỗ trợ phiên học và lưu lời nhắc.'
        elif action == 'list_reminders':
            rows = self.storage.reminders()
            message = '\n'.join(f"{r['id']}. {r['content']} — {datetime.fromisoformat(r['due_at']).strftime('%d/%m/%Y %H:%M')} ({r['status']})" for r in rows) or 'Chưa có lời nhắc đã lưu.'
        elif action == 'create_reminder':
            match = re.fullmatch(r'nhắc (?:tôi|mình) (.+?) sau (\d{1,4}) ngày lúc (\d{1,2}) giờ(?: (\d{1,2})(?: phút)?)?[.!]?', text)
            if not match:
                return 'ask_reminder_details', 'Hãy nhập đủ nội dung và thời gian, ví dụ: Nhắc tôi đi thi sau 2 ngày lúc 8 giờ.', 'clarification'
            content, days, hour, minute = match.groups()
            hour, minute = int(hour), int(minute or 0)
            if hour > 23 or minute > 59:
                return 'ask_reminder_details', 'Giờ phải từ 0 đến 23, phút từ 0 đến 59. Hãy nhập lại đầy đủ lời nhắc.', 'clarification'
            due = (now + timedelta(days=int(days))).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if due <= now:
                return 'ask_reminder_details', 'Thời điểm phải ở tương lai. Hãy nhập lại đầy đủ lời nhắc.', 'clarification'
            self.storage.add_reminder(content, due.isoformat())
            message = f"Đã lưu lời nhắc: {content}, lúc {due.strftime('%H:%M ngày %d/%m/%Y')}."
        else:
            message, device = 'Mình chưa hiểu. Bạn hãy nói rõ yêu cầu học, xem lịch hoặc tạo lời nhắc.', 'clarification'
        return action, message, device
