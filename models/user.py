"""User account for signing in.

Passwords are never stored — only a scrypt hash produced by Werkzeug,
which ships with Flask, so this needs no extra dependency.
"""

from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

# After this many wrong passwords the account pauses for a while, so a
# tracker left on a public URL cannot simply be guessed at all day.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 5
MIN_PASSWORD_LENGTH = 8


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > datetime.utcnow())

    @property
    def lock_minutes_left(self):
        if not self.is_locked:
            return 0
        seconds = (self.locked_until - datetime.utcnow()).total_seconds()
        return max(1, int(seconds // 60) + 1)

    def register_failure(self):
        self.failed_attempts = (self.failed_attempts or 0) + 1
        if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
            self.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            self.failed_attempts = 0

    def register_success(self):
        self.failed_attempts = 0
        self.locked_until = None
        self.last_login_at = datetime.utcnow()

    def __repr__(self):
        return f"<User {self.username}>"
