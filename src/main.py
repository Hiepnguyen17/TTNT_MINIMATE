"""Run with: python src/main.py"""
import argparse
import json
from pathlib import Path
from queue import Queue, Empty
import sqlite3
import threading
from minimate.storage import Storage
from minimate.task_manager import TaskManager
from minimate.esp32_client import ESP32Client


def read_input(queue):
    try:
        while True:
            queue.put(input())
    except EOFError:
        queue.put(None)


def main():
    parser = argparse.ArgumentParser(description='MINIMATE tuần 9')
    parser.add_argument('--db', default=str(Path(__file__).resolve().parents[1] / 'data' / 'minimate.db'))
    args = parser.parse_args()
    try:
        storage = Storage(args.db)
    except (sqlite3.Error, OSError) as error:
        print(f'Không mở được SQLite: {error}')
        return 1
    manager, device = TaskManager(storage), ESP32Client()
    queue = Queue()
    threading.Thread(target=read_input, args=(queue,), daemon=True).start()
    print('MINIMATE — nhập câu tiếng Việt; /quit để thoát. Chỉ mô phỏng thiết bị.')
    count = 1
    request_id = f'r-{count:03d}'
    device.set_state('listening', request_id)
    try:
        while True:
            try:
                if manager.tick():
                    print('Phiên học đã hoàn thành.')
                    device.send({'type': 'speak', 'request_id': 'timer', 'text': 'Phiên học đã hoàn thành.'})
                try:
                    line = queue.get(timeout=0.25)
                except Empty:
                    continue
                if line is None or line.strip() == '/quit':
                    break
                device.set_state('processing', request_id)
                response = manager.process(line)
                print(json.dumps(response, ensure_ascii=False))
                device.respond(response, request_id)
                count += 1
                request_id = f'r-{count:03d}'
                device.set_state('listening', request_id)
            except sqlite3.Error as error:
                device.send({'type': 'error', 'request_id': request_id, 'message': f'Lỗi SQLite: {error}'})
                return 1
    except KeyboardInterrupt:
        print('\nĐã thoát MINIMATE.')
    finally:
        storage.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
