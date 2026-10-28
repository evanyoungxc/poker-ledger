
import base64
import hashlib
import hmac
import io
import json
import secrets
from datetime import timedelta

import pyotp
import qrcode
from flask import (
    abort, flash, redirect, render_template_string,
    request, session, url_for
)
from flask_login import current_user, login_user, logout_user
from sqlalchemy import select

ISSUER = "Poker Ledger"

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} | Poker Ledger</title>
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
<style>
.auth-card {max-width:470px}
.security-copy {color:#c7d3c7;line-height:1.6;margin:16px 0}
.security-copy a {color:#e4c478}
.security-qr {display:block;width:min(230px,100%);margin:18px auto;
 background:white;padding:12px;border-radius:12px}
.security-code {font-size:22px;letter-spacing:5px;text-align:center}
.security-codes {padding:15px;background:#101f18;color:#f2d28b;
 border-radius:10px;overflow-wrap:anywhere;line-height:2}
.security-action {margin-top:18px}
.security-action input {width:100%}
.security-check {display:flex;align-items:center;gap:8px;margin:12px 0}
.security-check input {width:auto}

.security-copy a,
.auth-card a[href*="dashboard"] {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 11px 16px;
    margin-top: 10px;
    border: 1px solid #8c7440;
    border-radius: 9px;
    background: #17291f;
    color: #e8c77e !important;
    font-weight: 600;
    text-decoration: none !important;
    transition: background .2s ease;
}

.security-copy a:hover,
.auth-card a[href*="dashboard"]:hover {
    background: #243b2d;
    color: #f5d990 !important;
}


/* Account Security dashboard buttons */
body.auth-page .auth-card a.security-back-button,
body.auth-page .auth-card a.security-back-button:link,
body.auth-page .auth-card a.security-back-button:visited {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    padding: 12px 20px !important;
    margin-top: 16px;
    background: #203b2b !important;
    color: #e8c77e !important;
    border: 1px solid #9b8149 !important;
    border-radius: 10px !important;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
    text-decoration: none !important;
    box-shadow: none !important;
}

body.auth-page .auth-card a.security-back-button:hover,
body.auth-page .auth-card a.security-back-button:focus-visible {
    background: #2c4a35 !important;
    color: #f5d990 !important;
    text-decoration: none !important;
}

</style>
</head>
<body class="auth-page">
<main class="auth-card">
<div class="card-suits" aria-hidden="true">
<span>♠</span><span>♥</span><span>♣</span><span>♦</span>
</div>
<div class="brand"><div class="brand-icon">♠</div>
<h1>POKER LEDGER</h1></div>
<h2>{{ title }}</h2>
{% with messages = get_flashed_messages() %}
{% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}
{% endwith %}
{{ content | safe }}
</main></body></html>
"""

def page(title, content, **values):
    from flask import render_template_string
    from markupsafe import Markup
    inner = render_template_string(content, **values)
    return render_template_string(
        PAGE, title=title, content=Markup(inner)
    )

def code_valid(secret, code):
    code = "".join(str(code).split())
    return (
        len(code) == 6
        and code.isdigit()
        and pyotp.TOTP(secret).verify(code, valid_window=1)
    )

def new_recovery_codes():
    codes = [secrets.token_hex(5).upper() for _ in range(10)]
    hashes = [
        hashlib.sha256(code.encode()).hexdigest()
        for code in codes
    ]
    return codes, hashes

def use_recovery_code(user, submitted, db):
    candidate = submitted.strip().replace("-", "").upper()
    if len(candidate) != 10:
        return False
    digest = hashlib.sha256(candidate.encode()).hexdigest()
    hashes = json.loads(user.recovery_hashes or "[]")
    match = next(
        (h for h in hashes if hmac.compare_digest(h, digest)),
        None
    )
    if match is None:
        return False
    hashes.remove(match)
    user.recovery_hashes = json.dumps(hashes)
    db.session.commit()
    return True

def pending_user(db, User):
    uid = session.get("pending_2fa_user")
    if not isinstance(uid, int):
        return None
    return db.session.get(User, uid)

def complete_login(user):
    remember = bool(session.pop("pending_2fa_remember", False))
    session.pop("pending_2fa_user", None)
    session.pop("pending_2fa_attempts", None)
    session.pop("pending_2fa_started", None)
    session.clear()
    login_user(user, remember=remember, fresh=True)
    session.permanent = not remember

def begin_login(user, remember):
    import time
    session.clear()
    session["pending_2fa_user"] = user.id
    session["pending_2fa_remember"] = bool(remember)
    session["pending_2fa_attempts"] = 0
    session["pending_2fa_started"] = int(time.time())

def register_2fa(app, db, User, limiter):
    from flask_wtf.csrf import generate_csrf

    @app.before_request
    def enforce_admin_enrollment():
        if not current_user.is_authenticated:
            return
        if not current_user.is_admin:
            return
        if current_user.totp_enabled:
            return
        allowed = {
            "two_factor_setup", "two_factor_confirm",
            "logout", "static", "health"
        }
        if request.endpoint not in allowed:
            return redirect(url_for("two_factor_setup"))

    @app.route("/security/2fa")
    def two_factor_setup():
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        if current_user.email == "demo@poker-ledger.invalid":
            abort(403)

        if current_user.totp_enabled:
            return page("Two-Factor Authentication", """
            <p class="security-copy">Authenticator 2FA is enabled
            for your account.</p>
            <p class="security-copy">Keep your recovery codes in
            a secure location.</p>
            <a class="security-back-button" href="{{ url_for('dashboard') }}">Return to dashboard</a>
            """)

        if "setup_totp_secret" not in session:
            session["setup_totp_secret"] = pyotp.random_base32()

        secret = session["setup_totp_secret"]
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=current_user.email, issuer_name=ISSUER
        )
        qr = qrcode.make(uri)
        output = io.BytesIO()
        qr.save(output, format="PNG")
        encoded = base64.b64encode(output.getvalue()).decode()

        return page("Set Up Authenticator", """
        <p class="security-copy">
        Open Microsoft Authenticator, select Add account,
        then Other account, and scan this QR code.
        </p>
        <img class="security-qr"
             alt="Authenticator enrollment QR code"
             src="data:image/png;base64,{{ qr }}">
        <p class="security-copy">
        Or enter this setup key manually:
        <strong>{{ secret }}</strong>
        </p>
        <form method="POST" action="{{ url_for('two_factor_confirm') }}">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <label for="password">Confirm your password</label>
          <input id="password" type="password" name="password"
                 autocomplete="current-password" required>
          <label for="code">Six-digit authenticator code</label>
          <input id="code" class="security-code" name="code"
                 inputmode="numeric" autocomplete="one-time-code"
                 maxlength="6" required>
          <button class="primary-btn security-action" type="submit">
          ENABLE 2FA ♠</button>
        </form>
        """, qr=encoded, secret=secret)

    @app.route("/security/2fa/confirm", methods=["POST"])
    @limiter.limit("5 per minute")
    def two_factor_confirm():
        if not current_user.is_authenticated:
            abort(403)
        if current_user.email == "demo@poker-ledger.invalid":
            abort(403)
        if current_user.totp_enabled:
            abort(400)
        secret = session.get("setup_totp_secret")
        if not secret:
            return redirect(url_for("two_factor_setup"))

        password = request.form.get("password", "")
        code = request.form.get("code", "")
        if not current_user.check_password(password) or not code_valid(secret, code):
            flash("Password or authenticator code was incorrect.")
            return redirect(url_for("two_factor_setup"))

        codes, hashes = new_recovery_codes()
        current_user.totp_secret = secret
        current_user.totp_enabled = True
        current_user.recovery_hashes = json.dumps(hashes)
        db.session.commit()
        session.pop("setup_totp_secret", None)
        session["new_recovery_codes"] = codes
        return redirect(url_for("two_factor_recovery"))

    @app.route("/security/2fa/recovery")
    def two_factor_recovery():
        if not current_user.is_authenticated:
            abort(403)
        codes = session.pop("new_recovery_codes", None)
        if not codes:
            return redirect(url_for("two_factor_setup"))
        return page("Save Your Recovery Codes", """
        <p class="security-copy">
        2FA is enabled. Save these codes in your password manager.
        Each code works once. They will not be displayed again.
        </p>
        <div class="security-codes">
        {% for code in codes %}<div>{{ code }}</div>{% endfor %}
        </div>
        <p class="security-copy">
        Store these before continuing.
        </p>
        <a class="security-back-button" href="{{ url_for('dashboard') }}">Continue to dashboard</a>
        """, codes=codes)

    @app.route("/login/verify-2fa", methods=["GET", "POST"])
    @limiter.limit("10 per minute")
    def verify_two_factor():
        import time
        user = pending_user(db, User)
        started = session.get("pending_2fa_started", 0)
        if (
            user is None or not user.totp_enabled
            or time.time() - started > 300
        ):
            session.clear()
            return redirect(url_for("login"))

        if request.method == "POST":
            attempts = session.get("pending_2fa_attempts", 0) + 1
            session["pending_2fa_attempts"] = attempts
            if attempts > 5:
                session.clear()
                flash("Too many attempts. Please sign in again.")
                return redirect(url_for("login"))

            submitted = request.form.get("code", "")
            if code_valid(user.totp_secret, submitted) or use_recovery_code(
                user, submitted, db
            ):
                complete_login(user)
                return redirect(url_for("dashboard"))

            flash("Invalid verification or recovery code.")

        return page("Verify Your Identity", """
        <p class="security-copy">
        Enter the six-digit code from your authenticator app,
        or one of your unused recovery codes.
        </p>
        <form method="POST">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <label for="code">Authenticator or recovery code</label>
          <input id="code" class="security-code" name="code"
                 autocomplete="one-time-code" required autofocus>
          <button class="primary-btn security-action" type="submit">
          VERIFY ♠</button>
        </form>
        <p class="auth-footer">
          <a href="{{ url_for('login') }}">Return to login</a>
        </p>
        """)
