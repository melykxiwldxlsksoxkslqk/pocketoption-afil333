import json

def load_messages():
    with open('message_templates.json', 'r', encoding='utf-8') as f:
        return json.load(f) 