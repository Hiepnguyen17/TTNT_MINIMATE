import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from minimate.intent_baseline import classify
from minimate.storage import Storage
from minimate.task_manager import TaskManager
from minimate.esp32_client import ESP32Client


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(':memory:')
        self.now = datetime(2026, 11, 8, 10, tzinfo=timezone(timedelta(hours=7)))
        self.manager = TaskManager(self.storage, lambda: self.now)

    def tearDown(self):
        self.storage.close()

    def test_seven_intents(self):
        cases = {'  XIN CHÀO  ': 'greeting', 'Bắt đầu học 25 phút': 'focus_session_control',
                 'Còn bao lâu?': 'check_focus_session', 'Nhắc tôi đi thi sau 2 ngày lúc 8 giờ': 'schedule_reminder',
                 'Nhắc lại': 'repeat_response', 'Tại sao trời xanh?': 'open_question', 'Ngày mai 8 giờ': 'out_of_scope'}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(classify(text).intent, expected)

    def test_start_remaining_cancel(self):
        self.assertEqual(self.manager.process('Bắt đầu học 25 phút')['session_state'], 'active')
        self.now += timedelta(minutes=5)
        result = self.manager.process('Còn bao lâu?')
        self.assertIn('20 phút 0 giây', result['text'])
        self.assertEqual(result['action'], 'report_remaining_time')
        self.assertEqual(self.manager.process('Trạng thái phiên học?')['session_state'], 'active')
        self.assertEqual(self.manager.process('Dừng học')['session_state'], 'cancelled')
        self.assertIn('Không có', self.manager.process('Còn bao lâu?')['text'])

    def test_missing_duration_and_expiry(self):
        self.assertEqual(self.manager.process('Bắt đầu học')['session_state'], 'awaiting_duration')
        self.assertEqual(self.manager.process('0 phút')['device_state'], 'clarification')
        self.assertEqual(self.manager.process('25')['device_state'], 'clarification')
        self.assertEqual(self.manager.process('1 phút')['session_state'], 'active')
        self.now += timedelta(minutes=1)
        self.assertTrue(self.manager.tick())
        self.assertFalse(self.manager.tick())
        self.assertEqual(self.storage.session()['state'], 'idle')

    def test_repeat_does_not_restart_and_duplicate_start(self):
        first = self.manager.process('Bắt đầu học 25 phút')
        end = self.storage.session()['ends_at']
        self.now += timedelta(minutes=2)
        self.assertEqual(self.manager.process('Nhắc lại')['text'], first['text'])
        self.manager.process('Bắt đầu học 10 phút')
        self.assertEqual(self.storage.session()['ends_at'], end)

    def test_reminder_and_listing(self):
        self.manager.process('Nhắc tôi đi thi sau 2 ngày lúc 8 giờ')
        row = self.storage.reminders()[0]
        self.assertEqual(row['content'], 'đi thi')
        self.assertEqual(row['due_at'], '2026-11-10T08:00:00+07:00')
        self.assertIn('đi thi', self.manager.process('Xem lịch đã lưu')['text'])

    def test_invalid_reminder_and_negation(self):
        for text in ('Nhắc tôi đi thi', 'Nhắc tôi đi thi sau 2 ngày lúc 25 giờ', 'Nhắc tôi đi thi sau 0 ngày lúc 8 giờ'):
            self.assertEqual(self.manager.process(text)['device_state'], 'clarification')
        self.assertEqual(self.storage.reminders(), [])
        for text in ('Đừng bắt đầu học 25 phút', 'Bắt đầu học rồi dừng học', ''):
            self.assertEqual(self.manager.process(text)['intent'], 'out_of_scope')
        self.assertEqual(self.storage.session()['state'], 'idle')

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.db'
            store = Storage(path)
            manager = TaskManager(store, lambda: self.now)
            manager.process('Bắt đầu học 25 phút')
            response = manager.process('Nhắc tôi đi thi sau 2 ngày lúc 8 giờ')
            store.close()
            reopened = Storage(path)
            try:
                self.assertEqual(reopened.session()['state'], 'active')
                self.assertEqual(len(reopened.reminders()), 1)
                self.assertEqual(reopened.last_response(), response['text'])
                self.assertEqual(reopened.connection.execute('SELECT count(*) FROM commands').fetchone()[0], 2)
            finally:
                reopened.close()

    def test_transaction_rollback(self):
        self.storage.connection.execute("CREATE TRIGGER reject_command BEFORE INSERT ON commands BEGIN SELECT RAISE(ABORT, 'test'); END")
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.manager.process('Bắt đầu học 25 phút')
        self.assertEqual(self.storage.session()['state'], 'idle')

    def test_device_json(self):
        output = io.StringIO()
        device = ESP32Client()
        with contextlib.redirect_stdout(output):
            device.receive('{"type":"button_pressed","request_id":"r-001"}')
            device.set_state('listening', 'r-001')
            device.respond(self.manager.process('Xin chào'), 'r-001')
        messages = [json.loads(line.split(' ', 2)[2]) for line in output.getvalue().splitlines()]
        self.assertEqual(messages[1]['state'], 'listening')
        self.assertEqual(messages[2]['state'], 'speaking')
        self.assertEqual(messages[3]['type'], 'speak')


if __name__ == '__main__':
    unittest.main()
