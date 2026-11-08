"""JSON terminal simulation only; never controls hardware."""
import json


class ESP32Client:
    def send(self, message):
        print('ESP32 <- ' + json.dumps(message, ensure_ascii=False, separators=(',', ':')))

    def set_state(self, state, request_id):
        self.send({'type': 'set_state', 'request_id': request_id, 'state': state})

    def receive(self, line):
        event = json.loads(line)
        if not isinstance(event, dict) or event.get('type') not in ('button_pressed', 'audio_ready', 'device_error') or not isinstance(event.get('request_id'), str):
            raise ValueError('Event ESP32 không hợp lệ')
        print('ESP32 -> ' + json.dumps(event, ensure_ascii=False))
        return event

    def respond(self, response, request_id):
        self.set_state(response['device_state'], request_id)
        self.send({'type': 'speak', 'request_id': request_id, 'text': response['text']})
        if response['device_state'] == 'speaking':
            self.set_state('idle', request_id)
