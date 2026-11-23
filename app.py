"""QR TRAP — plataforma de simulación y análisis (UNAH, IS811 Seguridad Informática).

Componentes (según el informe):
  * Generador de códigos QR        -> /admin/qr
  * Página de destino + formulario -> /q/<estrategia>
  * Servicio de registro anónimo   -> /api/e y /api/r
  * Base de datos                  -> SQLite por defecto, PostgreSQL con DATABASE_URL
  * Panel de resultados            -> /admin

Privacidad: NO se guarda IP, user-agent, cookies, ubicación ni texto libre.
Solo: variante, tipo de evento, fecha/hora, id aleatorio de visita y respuestas de selección.
"""
import csv
import hmac
import io
import os
import random
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import segno
from flask import (Flask, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from werkzeug.middleware.proxy_fix import ProxyFix

from content import EVENT_TYPES, QUESTIONS, VARIANTS

BASE_DIR = Path(__file__).resolve().parent
IS_PROD = os.environ.get("APP_ENV", "development").lower() == "production"
HN_OFFSET = timedelta(hours=-6)  # Honduras no usa horario de verano

# ----------------------------------------------------------------- configuración
admin_password = os.environ.get("ADMIN_PASSWORD")
secret_key = os.environ.get("SECRET_KEY")
if IS_PROD and not (admin_password and secret_key):
    raise RuntimeError("En producción define las variables ADMIN_PASSWORD y SECRET_KEY.")
admin_password = admin_password or "qrtrap-dev"
secret_key = secret_key or "dev-solo-para-pruebas-locales"

db_url = os.environ.get("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    data_dir = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{data_dir / 'qrtrap.db'}"

app = Flask(__name__)
app.config.update(
    SECRET_KEY=secret_key,
    SQLALCHEMY_DATABASE_URI=db_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
    MAX_CONTENT_LENGTH=8 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PROD,
    SESSION_COOKIE_NAME="qrtrap_admin",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    JSON_AS_ASCII=False,
)
if IS_PROD:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db = SQLAlchemy(app)
signer = URLSafeTimedSerializer(secret_key, salt="qrtrap-visit")


# ---------------------------------------------------------------------- modelos
class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    variant = db.Column(db.String(20), nullable=False, index=True)
    event_type = db.Column(db.String(10), nullable=False)
    visit_id = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (db.UniqueConstraint("visit_id", "event_type", name="uq_visit_event"),)


class Response_(db.Model):
    __tablename__ = "responses"
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.String(16), nullable=False, unique=True)
    variant = db.Column(db.String(20), nullable=False, index=True)
    q1 = db.Column(db.String(20), nullable=False)
    q2 = db.Column(db.String(20), nullable=False)
    q3 = db.Column(db.String(20), nullable=False)
    q4 = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)


with app.app_context():
    try:
        db.create_all()
    except Exception:  # carrera entre procesos al crear tablas: es seguro ignorarla
        db.session.rollback()


# ---------------------------------------------------------------- seguridad HTTP
@app.after_request
def security_headers(resp):
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    if IS_PROD:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.path.startswith(("/admin", "/api", "/q/")):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


def check_csrf():
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
    if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(400)


def admin_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapper


_fails = {}  # throttling de intentos de login en memoria (no se persiste)


def _throttled(key):
    n, ts = _fails.get(key, (0, 0))
    if time.time() - ts > 600:
        return False
    return n >= 5


def _register_fail(key):
    n, ts = _fails.get(key, (0, 0))
    _fails[key] = (1 if time.time() - ts > 600 else n + 1, time.time())


# -------------------------------------------------------------------- utilidades
def to_local(dt):
    return dt + HN_OFFSET


def fmt_local(dt):
    return to_local(dt).strftime("%d/%m/%Y %H:%M")


def new_visit_id():
    return secrets.token_hex(8)


def log_event(variant, etype, visit_id, demo=False, when=None):
    try:
        db.session.add(Event(variant=variant, event_type=etype, visit_id=visit_id,
                             is_demo=demo, created_at=when or datetime.utcnow()))
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False


# ------------------------------------------------------------------------ público
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")


@app.route("/healthz")
def healthz():
    return "ok"


@app.route("/q/<slug>")
def landing(slug):
    variant = VARIANTS.get(slug)
    if not variant:
        abort(404)
    visit = new_visit_id()
    preview = bool(session.get("admin") and request.args.get("preview"))
    if not preview:
        log_event(slug, "scan", visit)
    token = signer.dumps({"v": slug, "i": visit, "p": preview})
    return render_template("landing.html", variant=variant, token=token, questions=QUESTIONS)


def _read_token(data):
    try:
        info = signer.loads(data.get("token", ""), max_age=60 * 60 * 24)
        if info["v"] not in VARIANTS:
            raise BadSignature("variante")
        return info
    except (BadSignature, KeyError, TypeError, AttributeError):
        abort(400)


@app.post("/api/e")
def api_event():
    data = request.get_json(silent=True) or {}
    info = _read_token(data)
    if data.get("type") != "read":
        abort(400)
    if not info.get("p"):
        log_event(info["v"], "read", info["i"])
    return jsonify(ok=True)


@app.post("/api/r")
def api_response():
    data = request.get_json(silent=True) or {}
    info = _read_token(data)
    answers = {}
    for q in QUESTIONS:
        val = data.get(q["id"])
        if val not in q["opciones"]:
            abort(400)
        answers[q["id"]] = val
    if not info.get("p"):
        try:
            db.session.add(Response_(visit_id=info["i"], variant=info["v"], **answers))
            db.session.commit()
            log_event(info["v"], "response", info["i"])
        except IntegrityError:
            db.session.rollback()
    return jsonify(ok=True)


# ------------------------------------------------------------------------- admin
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        check_csrf()
        key = request.remote_addr or "?"
        if _throttled(key):
            error = "Demasiados intentos. Espera unos minutos."
        elif hmac.compare_digest(request.form.get("password", "").encode(), admin_password.encode()):
            session.clear()
            session["admin"] = True
            session.permanent = True
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/admin") else url_for("dashboard"))
        else:
            _register_fail(key)
            error = "Clave incorrecta."
    return render_template("login.html", error=error)


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@admin_required
def dashboard():
    return render_template("dashboard.html", variants=VARIANTS.values(), questions=QUESTIONS,
                           active="panel")


def compute_stats():
    events = Event.query.order_by(Event.created_at).all()
    responses = Response_.query.all()
    now_local = datetime.utcnow() + HN_OFFSET

    per = {s: {"scan": 0, "read": 0, "response": 0} for s in VARIANTS}
    for e in events:
        per[e.variant][e.event_type] += 1

    variants = []
    for slug, v in VARIANTS.items():
        c = per[slug]
        variants.append({
            "slug": slug, "nombre": v["nombre"], "color": v["color"], **c,
            "read_rate": round(100 * c["read"] / c["scan"], 1) if c["scan"] else 0,
            "resp_rate": round(100 * c["response"] / c["scan"], 1) if c["scan"] else 0,
        })

    tot = {k: sum(v[k] for v in variants) for k in ("scan", "read", "response")}

    # Línea de tiempo: últimas 24 h por hora y últimos 14 días por día (hora de Honduras)
    h0 = now_local.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
    hours = [h0 + timedelta(hours=i) for i in range(24)]
    d0 = now_local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=13)
    days = [d0 + timedelta(days=i) for i in range(14)]
    th = {s: [0] * 24 for s in VARIANTS}
    td = {s: [0] * 14 for s in VARIANTS}
    for e in events:
        if e.event_type != "scan":
            continue
        loc = to_local(e.created_at)
        hi = int((loc.replace(minute=0, second=0, microsecond=0) - h0).total_seconds() // 3600)
        if 0 <= hi < 24:
            th[e.variant][hi] += 1
        di = (loc.replace(hour=0, minute=0, second=0, microsecond=0) - d0).days
        if 0 <= di < 14:
            td[e.variant][di] += 1

    questions = []
    for q in QUESTIONS:
        por = {s: {k: 0 for k in q["opciones"]} for s in VARIANTS}
        for r in responses:
            por[r.variant][getattr(r, q["id"])] += 1
        total = {k: sum(por[s][k] for s in VARIANTS) for k in q["opciones"]}
        questions.append({
            "id": q["id"], "texto": q["texto"], "corto": q["corto"],
            "opciones": [{"key": k, "label": lbl} for k, lbl in q["opciones"].items()],
            "por_variante": por, "total": total,
        })

    recent = [{
        "variant": e.variant, "nombre": VARIANTS[e.variant]["nombre"],
        "type": e.event_type, "tipo": EVENT_TYPES[e.event_type],
        "fecha": fmt_local(e.created_at), "visit": e.visit_id[:6].upper(),
    } for e in sorted(events, key=lambda x: x.created_at, reverse=True)[:30]]

    verified = sum(1 for r in responses if r.q2 == "ambas")
    changed = sum(1 for r in responses if r.q4 == "si")
    n_resp = len(responses)

    return {
        "variants": variants, "totals": tot,
        "read_rate": round(100 * tot["read"] / tot["scan"], 1) if tot["scan"] else 0,
        "resp_rate": round(100 * tot["response"] / tot["scan"], 1) if tot["scan"] else 0,
        "verified_pct": round(100 * verified / n_resp, 1) if n_resp else 0,
        "changed_pct": round(100 * changed / n_resp, 1) if n_resp else 0,
        "timeline": {
            "hour": {"labels": [h.strftime("%H:00") for h in hours], "series": th},
            "day": {"labels": [d.strftime("%d/%m") for d in days], "series": td},
        },
        "questions": questions, "recent": recent,
        "demo_count": Event.query.filter_by(is_demo=True).count(),
        "updated": now_local.strftime("%H:%M:%S"),
    }


@app.route("/admin/api/stats")
@admin_required
def api_stats():
    return jsonify(compute_stats())


@app.post("/admin/demo/<action>")
@admin_required
def demo(action):
    check_csrf()
    if action == "clear":
        Response_.query.filter_by(is_demo=True).delete()
        Event.query.filter_by(is_demo=True).delete()
        db.session.commit()
    elif action == "seed":
        seed_demo()
    else:
        abort(404)
    return jsonify(ok=True)


def seed_demo():
    """Datos ficticios para ensayar la presentación. Quedan marcados y se pueden borrar."""
    rnd = random.Random()
    plan = {"curiosidad": 64, "utilidad": 88, "urgencia": 41, "informativa": 57}
    read_p = {"curiosidad": .72, "utilidad": .81, "urgencia": .58, "informativa": .69}
    resp_p = {"curiosidad": .45, "utilidad": .55, "urgencia": .38, "informativa": .50}
    q1w = {
        "curiosidad": (68, 10, 6, 16), "utilidad": (8, 74, 6, 12),
        "urgencia": (30, 20, 12, 38), "informativa": (10, 18, 58, 14),
    }
    q2w = {
        "curiosidad": (4, 22, 74), "utilidad": (6, 24, 70),
        "urgencia": (2, 14, 84), "informativa": (14, 34, 52),
    }
    q3w = {"curiosidad": (12, 58, 30), "utilidad": (10, 62, 28), "urgencia": (22, 48, 30), "informativa": (8, 66, 26)}
    q4w = (62, 30, 8)
    now = datetime.utcnow()
    k1, k2, k3, k4 = (list(q["opciones"]) for q in QUESTIONS)
    for slug, n in plan.items():
        for _ in range(n):
            vid = new_visit_id()
            # horario escolar (8:00-17:59 hora local) en los últimos 3 días
            day = rnd.randint(0, 2)
            local = (now + HN_OFFSET).replace(hour=rnd.randint(8, 17), minute=rnd.randint(0, 59),
                                              second=rnd.randint(0, 59), microsecond=0) - timedelta(days=day)
            t = local - HN_OFFSET
            if t > now:
                t -= timedelta(days=1)
            db.session.add(Event(variant=slug, event_type="scan", visit_id=vid, created_at=t, is_demo=True))
            if rnd.random() < read_p[slug]:
                t2 = t + timedelta(seconds=rnd.randint(8, 60))
                db.session.add(Event(variant=slug, event_type="read", visit_id=vid, created_at=t2, is_demo=True))
                if rnd.random() < resp_p[slug] / read_p[slug]:
                    t3 = t2 + timedelta(seconds=rnd.randint(15, 90))
                    db.session.add(Event(variant=slug, event_type="response", visit_id=vid, created_at=t3, is_demo=True))
                    db.session.add(Response_(
                        visit_id=vid, variant=slug, created_at=t3, is_demo=True,
                        q1=rnd.choices(k1, q1w[slug])[0], q2=rnd.choices(k2, q2w[slug])[0],
                        q3=rnd.choices(k3, q3w[slug])[0], q4=rnd.choices(k4, q4w)[0]))
    db.session.commit()


@app.route("/admin/export/<which>.csv")
@admin_required
def export(which):
    out = io.StringIO()
    w = csv.writer(out)
    if which == "eventos":
        w.writerow(["estrategia", "evento", "fecha_hora_honduras", "id_visita", "demo"])
        for e in Event.query.order_by(Event.created_at):
            w.writerow([e.variant, e.event_type, to_local(e.created_at).isoformat(sep=" "), e.visit_id, int(e.is_demo)])
    elif which == "respuestas":
        w.writerow(["estrategia", "fecha_hora_honduras", "id_visita", "q1", "q2", "q3", "q4", "demo"])
        for r in Response_.query.order_by(Response_.created_at):
            w.writerow([r.variant, to_local(r.created_at).isoformat(sep=" "), r.visit_id,
                        r.q1, r.q2, r.q3, r.q4, int(r.is_demo)])
    else:
        abort(404)
    return Response(out.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=qrtrap_{which}.csv"})


# --------------------------------------------------------------------- generador QR
def _clean_base(raw):
    raw = (raw or request.url_root).strip().rstrip("/")
    if not raw.startswith(("http://", "https://")) or len(raw) > 200 or any(c in raw for c in " \"'<>"):
        abort(400)
    return raw


@app.route("/admin/qr")
@admin_required
def qr_page():
    return render_template("qr.html", variants=VARIANTS.values(), base=request.url_root.rstrip("/"),
                           active="qr")


@app.route("/admin/qr/<slug>.<fmt>")
@admin_required
def qr_image(slug, fmt):
    if slug not in VARIANTS or fmt not in ("svg", "png"):
        abort(404)
    target = f"{_clean_base(request.args.get('base'))}/q/{slug}"
    qr = segno.make(target, error="m")
    buf = io.BytesIO()
    if fmt == "svg":
        qr.save(buf, kind="svg", scale=10, border=2, dark="#0f172a", xmldecl=False)
        mime = "image/svg+xml"
    else:
        qr.save(buf, kind="png", scale=14, border=3, dark="#000000")
        mime = "image/png"
    headers = {}
    if request.args.get("dl"):
        headers["Content-Disposition"] = f"attachment; filename=qrtrap_{slug}.{fmt}"
    return Response(buf.getvalue(), mimetype=mime, headers=headers)


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, msg="Página no encontrada"), 404


@app.errorhandler(400)
def bad_request(_):
    return render_template("error.html", code=400, msg="Solicitud no válida"), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=not IS_PROD)
