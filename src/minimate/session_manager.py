from datetime import datetime, timedelta
import math


class SessionManager:
    def __init__(self, storage):
        self.storage = storage

    def expire(self, now):
        session = self.storage.session()
        if session['state'] == 'active' and datetime.fromisoformat(session['ends_at']) <= now:
            self.storage.set_session('idle')
            return True
        return False

    def start(self, seconds, now):
        self.storage.set_session('active', seconds, now.isoformat(), (now + timedelta(seconds=seconds)).isoformat())

    def remaining(self, now):
        session = self.storage.session()
        if session['state'] != 'active':
            return None
        return max(0, math.ceil((datetime.fromisoformat(session['ends_at']) - now).total_seconds()))
