from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

db = SQLAlchemy()
password_hasher = PasswordHasher()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def set_password(self, password):
        self.password_hash = password_hasher.hash(password)

    def check_password(self, password):
        try:
            return password_hasher.verify(self.password_hash, password)
        except VerificationError:
            return False


class PokerSession(db.Model):
    __tablename__ = "poker_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    date = db.Column(db.Date, nullable=False)
    game_type = db.Column(db.String(20), nullable=False)
    buy_in_cents = db.Column(db.Integer, nullable=False)
    cash_out_cents = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    entry_mode = db.Column(db.String(10), nullable=False, default="buyin")

    user = db.relationship(
        "User",
        backref=db.backref("poker_sessions", lazy=True)
    )

    @property
    def profit_cents(self):
        return self.cash_out_cents - self.buy_in_cents


class LossLimit(db.Model):
    __tablename__ = "loss_limits"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True
    )

    enabled = db.Column(db.Boolean, nullable=False, default=False)
    threshold_cents = db.Column(db.Integer, nullable=False, default=5000)
    period = db.Column(db.String(10), nullable=False, default="daily")
