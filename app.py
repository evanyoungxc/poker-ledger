import os
import secrets
from datetime import timedelta

from flask import (
    Flask, render_template, redirect, url_for,
    flash, request, abort, session
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import select, func
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy.exc import IntegrityError

from models import db, User, PokerSession, LossLimit

app = Flask(__name__)

app.config.update(
    SECRET_KEY=os.environ.get("POKER_SECRET_KEY"),
    SQLALCHEMY_DATABASE_URI="sqlite:///poker.db",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=1024 * 1024,
)

if not app.config["SECRET_KEY"]:
    raise RuntimeError("POKER_SECRET_KEY is required")

# Trust forwarding headers from the single local Nginx proxy.
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
)

db.init_app(app)
csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["120 per minute"],
    storage_uri="memory://",
)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


@app.route("/")
@login_required
def dashboard():
    sessions = db.session.scalars(
        select(PokerSession)
        .where(PokerSession.user_id == current_user.id)
        .order_by(PokerSession.date.desc(), PokerSession.id.desc())
    ).all()

    from datetime import date

    total_profit = sum(s.profit_cents for s in sessions)

    loss_limit = db.session.scalar(
        select(LossLimit).where(LossLimit.user_id == current_user.id)
    )

    today = date.today()
    week_start = today - timedelta(days=(today.weekday() + 1) % 7)

    if loss_limit and loss_limit.enabled:
        if loss_limit.period == "daily":
            relevant = [s for s in sessions if s.date == today]
        elif loss_limit.period == "weekly":
            relevant = [s for s in sessions if week_start <= s.date <= today]
        else:
            relevant = sessions

        period_profit = sum(s.profit_cents for s in relevant)
        loss_alert = period_profit <= -loss_limit.threshold_cents
    else:
        period_profit = 0
        loss_alert = False

    from datetime import date

    leaderboard_game = request.args.get("leaderboard_game", "all")
    if leaderboard_game not in ("all", "Stake", "Home Game", "Ten Card Flip"):
        leaderboard_game = "all"

    leaderboard_period = request.args.get("leaderboard_period", "all")

    if leaderboard_period not in ("all", "month", "week"):
        leaderboard_period = "all"

    today = date.today()

    if leaderboard_period == "month":
        start_date = today.replace(day=1)
    elif leaderboard_period == "week":
        start_date = today - timedelta(days=(today.weekday() + 1) % 7)
    else:
        start_date = None

    leaderboard_query = select(
        User.username,
        func.count(PokerSession.id).label("sessions"),
        func.coalesce(
            func.sum(
                PokerSession.cash_out_cents -
                PokerSession.buy_in_cents
            ), 0
        ).label("profit_cents")
    )

    join_condition = PokerSession.user_id == User.id

    if leaderboard_game != "all":
        join_condition = (
            join_condition
            & (PokerSession.game_type == leaderboard_game)
        )

    if start_date is not None:
        join_condition = (
            join_condition
            & (PokerSession.date >= start_date)
            & (PokerSession.date <= today)
        )

    leaderboard = db.session.execute(
        leaderboard_query
        .outerjoin(PokerSession, join_condition)
        .group_by(User.id, User.username)
        .order_by(
            func.coalesce(
                func.sum(
                    PokerSession.cash_out_cents -
                    PokerSession.buy_in_cents
                ), 0
            ).desc(),
            User.username.asc()
        )
    ).all()

    # Biggest Fish: largest all-time net loss across all users.
    fish_result = db.session.execute(
        select(
            User.username,
            func.coalesce(
                func.sum(
                    PokerSession.cash_out_cents -
                    PokerSession.buy_in_cents
                ), 0
            ).label("net_cents")
        )
        .join(PokerSession, PokerSession.user_id == User.id)
        .group_by(User.id, User.username)
        .having(
            func.sum(
                PokerSession.cash_out_cents -
                PokerSession.buy_in_cents
            ) < 0
        )
        .order_by(
            func.sum(
                PokerSession.cash_out_cents -
                PokerSession.buy_in_cents
            ).asc(),
            User.username.asc()
        )
        .limit(1)
    ).first()

    fish_names = {
        "a": "Angelfish", "b": "Bass", "c": "Catfish",
        "d": "Discus", "e": "Eel", "f": "Flounder",
        "g": "Grouper", "h": "Haddock", "i": "Icefish",
        "j": "Jackfish", "k": "Koi", "l": "Lionfish",
        "m": "Mackerel", "n": "Needlefish", "o": "Oscar",
        "p": "Pufferfish", "q": "Queenfish", "r": "Rainbowfish",
        "s": "Salmon", "t": "Tilapia", "u": "Unicornfish",
        "v": "Viperfish", "w": "Walleye", "x": "X-ray Tetra",
        "y": "Yellowtail", "z": "Zebrafish"
    }

    biggest_fish = None

    if fish_result:
        username = fish_result.username
        fish_name = fish_names.get(username[0].lower(), "Goldfish")
        biggest_fish = {
            "name": f"{fish_name} {username}",
            "net_cents": fish_result.net_cents
        }

    # Fish of the Week: largest net loss since Monday.
    fish_week_start = date.today() - timedelta(days=(date.today().weekday() + 1) % 7)

    weekly_fish_result = db.session.execute(
        select(
            User.username,
            func.sum(
                PokerSession.cash_out_cents -
                PokerSession.buy_in_cents
            ).label("net_cents")
        )
        .join(PokerSession, PokerSession.user_id == User.id)
        .where(
            PokerSession.date >= fish_week_start,
            PokerSession.date <= date.today()
        )
        .group_by(User.id, User.username)
        .having(
            func.sum(
                PokerSession.cash_out_cents -
                PokerSession.buy_in_cents
            ) < 0
        )
        .order_by(
            func.sum(
                PokerSession.cash_out_cents -
                PokerSession.buy_in_cents
            ).asc(),
            User.username.asc()
        )
        .limit(1)
    ).first()

    fish_of_week = None

    if weekly_fish_result:
        username = weekly_fish_result.username
        fish_name = fish_names.get(username[0].lower(), "Goldfish")

        fish_of_week = {
            "name": f"{fish_name} {username}",
            "net_cents": weekly_fish_result.net_cents
        }

    return render_template(
        "dashboard.html",
        sessions=sessions,
        leaderboard=leaderboard,
        biggest_fish=biggest_fish,
        fish_of_week=fish_of_week,
        leaderboard_period=leaderboard_period,
        leaderboard_game=leaderboard_game,
        total_profit=total_profit,
        loss_limit=loss_limit,
        loss_alert=loss_alert,
        period_profit=period_profit,
    )


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        invite = request.form.get("invite", "")
        expected = os.environ.get("POKER_INVITE_CODE", "")

        if not expected or not secrets.compare_digest(invite, expected):
            flash("Invalid invitation code.")
            return redirect(url_for("register"))

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not 3 <= len(username) <= 50:
            flash("Username must be 3-50 characters.")
            return redirect(url_for("register"))

        if not 3 <= len(email) <= 255 or "@" not in email:
            flash("Enter a valid email.")
            return redirect(url_for("register"))

        if not 12 <= len(password) <= 128:
            flash("Password must be 12-128 characters.")
            return redirect(url_for("register"))

        user = User(username=username, email=email)
        user.set_password(password)

        db.session.add(user)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Username or email already registered.")
            return redirect(url_for("register"))

        flash("Account created. Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = db.session.scalar(
            select(User).where(User.email == email)
        )

        if user and user.check_password(password):
            login_user(user, remember=False, fresh=True)
            session.permanent = True
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/health")
def health():
    return {"status": "ok"}



@app.route("/sessions/add", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def add_session():
    from datetime import date
    from decimal import Decimal, InvalidOperation

    game_type = request.form.get("game_type", "")
    session_date = request.form.get("date", "")
    entry_mode = request.form.get("entry_mode", "buyin")

    if game_type not in ("Stake", "Home Game", "Ten Card Flip"):
        abort(400)

    try:
        played_on = date.fromisoformat(session_date)
    except ValueError:
        abort(400)

    if played_on > date.today():
        abort(400)

    def parse_cents(value, allow_negative=False):
        try:
            amount = Decimal(value)
            cents = amount * 100
            if (
                not amount.is_finite()
                or cents != cents.to_integral_value()
                or abs(cents) > 100_000_000
                or (amount < 0 and not allow_negative)
            ):
                raise ValueError
            return int(cents)
        except (InvalidOperation, ValueError, TypeError):
            abort(400)

    if entry_mode == "net":
        profit = parse_cents(
            request.form.get("net_profit", ""),
            allow_negative=True
        )
        buy_in = max(-profit, 0)
        cash_out = max(profit, 0)
    elif entry_mode == "buyin":
        buy_in = parse_cents(request.form.get("buy_in", ""))
        cash_out = parse_cents(request.form.get("cash_out", ""))
    else:
        abort(400)

    notes = request.form.get("notes", "").strip()

    if len(notes) > 500:
        abort(400)

    poker_session = PokerSession(
        user_id=current_user.id,
        date=played_on,
        game_type=game_type,
        buy_in_cents=buy_in,
        cash_out_cents=cash_out,
        notes=notes
    )

    poker_session.entry_mode = entry_mode
    db.session.add(poker_session)
    db.session.commit()

    flash("Poker session saved successfully.")
    return redirect(url_for("dashboard"))


@app.route("/sessions/<int:session_id>/edit", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per minute")
def edit_session(session_id):
    from datetime import date
    from decimal import Decimal, InvalidOperation

    poker_session = PokerSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == "GET":
        return render_template(
            "edit_session.html",
            session=poker_session
        )

    game_type = request.form.get("game_type", "")
    session_date = request.form.get("date", "")
    entry_mode = request.form.get("entry_mode", "net")

    if game_type not in ("Stake", "Home Game", "Ten Card Flip"):
        abort(400)

    try:
        played_on = date.fromisoformat(session_date)
    except ValueError:
        abort(400)

    if played_on > date.today():
        abort(400)

    def parse_cents(value, allow_negative=False):
        try:
            amount = Decimal(value)
            cents = amount * 100

            if (
                not amount.is_finite()
                or cents != cents.to_integral_value()
                or abs(cents) > 100_000_000
                or (amount < 0 and not allow_negative)
            ):
                raise ValueError

            return int(cents)
        except (InvalidOperation, ValueError, TypeError):
            abort(400)

    if entry_mode == "net":
        profit = parse_cents(
            request.form.get("net_profit", ""),
            allow_negative=True
        )
        buy_in = max(-profit, 0)
        cash_out = max(profit, 0)

    elif entry_mode == "buyin":
        buy_in = parse_cents(request.form.get("buy_in", ""))
        cash_out = parse_cents(request.form.get("cash_out", ""))

    else:
        abort(400)

    notes = request.form.get("notes", "").strip()

    if len(notes) > 500:
        abort(400)

    poker_session.date = played_on
    poker_session.game_type = game_type
    poker_session.entry_mode = entry_mode
    poker_session.buy_in_cents = buy_in
    poker_session.cash_out_cents = cash_out
    poker_session.notes = notes

    db.session.commit()

    flash("Poker session updated successfully.")
    return redirect(url_for("dashboard"))


@app.route("/sessions/<int:session_id>/delete", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def delete_session(session_id):
    poker_session = PokerSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(poker_session)
    db.session.commit()

    flash("Poker session deleted successfully.")
    return redirect(url_for("dashboard"))


@app.route("/settings/loss-limit", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def update_loss_limit():
    from decimal import Decimal, InvalidOperation

    enabled = request.form.get("enabled") == "on"
    period = request.form.get("period", "daily")

    if period not in ("daily", "weekly", "overall"):
        abort(400)

    try:
        amount = Decimal(request.form.get("threshold", ""))
        cents = amount * 100

        if (
            not amount.is_finite()
            or cents != cents.to_integral_value()
            or cents < 1
            or cents > 100_000_000
        ):
            abort(400)

        threshold_cents = int(cents)
    except (InvalidOperation, ValueError, TypeError):
        abort(400)

    loss_limit = db.session.scalar(
        select(LossLimit).where(LossLimit.user_id == current_user.id)
    )

    if loss_limit is None:
        loss_limit = LossLimit(user_id=current_user.id)
        db.session.add(loss_limit)

    loss_limit.enabled = enabled
    loss_limit.period = period
    loss_limit.threshold_cents = threshold_cents

    db.session.commit()

    flash("Loss limit settings updated.")
    return redirect(url_for("dashboard"))



@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    return response


# --- Admin management ---

from datetime import date as admin_date
from decimal import Decimal as AdminDecimal, InvalidOperation as AdminInvalidOperation


def require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


@app.route("/admin")
@login_required
def admin_dashboard():
    require_admin()

    users = db.session.execute(
        select(
            User,
            func.count(PokerSession.id),
            func.coalesce(
                func.sum(
                    PokerSession.cash_out_cents - PokerSession.buy_in_cents
                ), 0
            )
        )
        .outerjoin(PokerSession, PokerSession.user_id == User.id)
        .group_by(User.id)
        .order_by(User.id)
    ).all()

    selected_user = None
    sessions = []

    user_id = request.args.get("user_id", type=int)

    if user_id is not None:
        selected_user = db.get_or_404(User, user_id)
        sessions = db.session.scalars(
            select(PokerSession)
            .where(PokerSession.user_id == user_id)
            .order_by(PokerSession.date.desc(), PokerSession.id.desc())
        ).all()

    return render_template(
        "admin.html",
        users=users,
        selected_user=selected_user,
        sessions=sessions
    )


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def admin_delete_user(user_id):
    require_admin()

    user = db.get_or_404(User, user_id)

    if user.id == current_user.id or user.is_admin:
        abort(403)

    PokerSession.query.filter_by(user_id=user.id).delete()
    LossLimit.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()

    flash("Account and associated data deleted.")
    return redirect(url_for("admin_dashboard"))


def admin_parse_cents(value):
    try:
        amount = AdminDecimal(value)
        cents = amount * 100
        if (
            not amount.is_finite()
            or cents != cents.to_integral_value()
            or amount < 0
            or cents > 100_000_000
        ):
            abort(400)
        return int(cents)
    except (AdminInvalidOperation, ValueError, TypeError):
        abort(400)


@app.route("/admin/sessions/<int:session_id>/edit", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def admin_edit_session(session_id):
    require_admin()

    poker_session = db.get_or_404(PokerSession, session_id)

    try:
        played_on = admin_date.fromisoformat(request.form.get("date", ""))
    except ValueError:
        abort(400)

    if played_on > admin_date.today():
        abort(400)

    game_type = request.form.get("game_type", "")
    if game_type not in ("Stake", "Home Game", "Ten Card Flip"):
        abort(400)

    notes = request.form.get("notes", "").strip()
    if len(notes) > 500:
        abort(400)

    poker_session.date = played_on
    poker_session.game_type = game_type
    poker_session.buy_in_cents = admin_parse_cents(request.form.get("buy_in", ""))
    poker_session.cash_out_cents = admin_parse_cents(request.form.get("cash_out", ""))
    poker_session.entry_mode = "buyin"
    poker_session.notes = notes

    db.session.commit()

    flash("Session updated.")
    return redirect(url_for("admin_dashboard", user_id=poker_session.user_id))


@app.route("/admin/sessions/<int:session_id>/delete", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def admin_delete_session(session_id):
    require_admin()

    poker_session = db.get_or_404(PokerSession, session_id)
    user_id = poker_session.user_id

    db.session.delete(poker_session)
    db.session.commit()

    flash("Session deleted.")
    return redirect(url_for("admin_dashboard", user_id=user_id))
