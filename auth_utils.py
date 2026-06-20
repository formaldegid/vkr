import os
import json
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, role, depts):
        self.id = id
        self.role = role
        self.depts = depts

def load_users_db():
    path = os.path.join('data', 'users.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}
