import os
from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_apscheduler import APScheduler
from datetime import datetime
from sqlalchemy.exc import OperationalError  # Importar error de SQLAlchemy
import logging


# Instanciar las extensiones
api = Api()
db = SQLAlchemy()
jwt = JWTManager()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    load_dotenv()
    CORS(app)

    # Configurar la base de datos
    PATH = os.getenv("DATABASE_PATH")
    DB_NAME = os.getenv("DATABASE_NAME")
    if not os.path.exists(f"{PATH}{DB_NAME}"):
        os.chdir(f"{PATH}")
        file = os.open(f"{DB_NAME}", os.O_CREAT)

    # Configuración de SQLite con timeout
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{PATH}{DB_NAME}?timeout=30"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Scheduler configuration
    app.config['SCHEDULER_API_ENABLED'] = True

    db.init_app(app)
    scheduler.init_app(app)
    scheduler.start()

    # Configurar la base de datos antes de la primera solicitud
    @app.before_first_request
    def setup_database():
        db.session.remove()  # Cerrar cualquier sesión activa
        with db.engine.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL;')

    # Registrar recursos de Flask-RESTful
    import main.resources as resources
    api.add_resource(resources.ClienteResource, '/<username>/cliente/<int:id>')
    api.add_resource(resources.ClientesResource, '/<username>/clientes')
    api.add_resource(resources.UsuarioResource, '/usuario/<int:id>')
    api.add_resource(resources.UsuariosResource, '/usuarios')
    api.init_app(app)

    from main.tasks import update_days_for_appointment  # Nombre correcto de la función
    logging.basicConfig(level=logging.INFO)
    # Función de actualización de citas envuelta en el contexto de la aplicación
    def wrapped_update_days_for_appointment():
        logging.info("Iniciando wrapped_update_dias_para_cita...")  # Depurador 1
        with app.app_context():
            try:
                logging.info("Llamando a update_dias_para_cita...")  # Depurador 2
                update_days_for_appointment()
                logging.info("Función update_dias_para_cita ejecutada correctamente.")  # Depurador 3
            except OperationalError as e:
                logging.error(f"OperationalError durante la ejecución: {str(e)}")  # Depurador 4
                db.session.rollback()
            except Exception as e:
                logging.error(f"Error inesperado en wrapped_update_dias_para_cita: {str(e)}")  # Depurador 5
            finally:
                logging.info("Cerrando la sesión de la base de datos.")  # Depurador 6
                db.session.close()

    # Agregar la tarea al scheduler
    scheduler.add_job(
            id='update_days_for_appointment',
            func=wrapped_update_days_for_appointment,
            trigger='interval',
            days=1,
            next_run_time=datetime.now()  # Ejecuta inmediatamente al iniciar
    )

    # Configurar JWT
    app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES"))
    jwt.init_app(app)

    # Registrar blueprint de autenticación
    from main.auth import routes as auth_routes
    app.register_blueprint(auth_routes.auth)
    

    return app
