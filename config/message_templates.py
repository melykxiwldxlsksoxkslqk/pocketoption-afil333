import json
import os


def load_messages():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    templates_path = os.path.join(base_dir, 'message_templates.json')
    with open(templates_path, 'r', encoding='utf-8') as f:
        return json.load(f) 