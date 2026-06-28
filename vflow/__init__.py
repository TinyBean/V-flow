"""V-flow 应用工厂。"""
from pathlib import Path
from flask import Flask


def create_app() -> Flask:
    # 模板 / 静态资源在工程根(与 vflow/ 平级),需显式指定
    root = Path(__file__).resolve().parent.parent
    app = Flask(__name__, template_folder=str(root / 'templates'),
                static_folder=str(root / 'static'))
    from . import meta
    meta.init_db()
    from .routes import bp
    app.register_blueprint(bp)
    return app
