from flask_restful import Resource, reqparse
from flask import request, jsonify, make_response
from .. import db
from main.models.Cliente import Cliente as ClienteModel
from main.models import UsuarioModel
import datetime as dt
import requests
import json
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import time
from datetime import datetime, date, time
from sqlalchemy import Table, MetaData, extract, cast, Date
import locale


# Configuración de locales para fechas en español
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.utf8')
except locale.Error:
    locale.setlocale(locale.LC_TIME, 'C')  # Usa el locale predeterminado si falla

# Definir el request parser para los datos de cliente
cliente_parser = reqparse.RequestParser()
cliente_parser.add_argument('cellphone', type=str, required=True, help="Cellphone is required")
cliente_parser.add_argument('name', type=str, required=True, help="Name is required")
cliente_parser.add_argument('date', type=str, required=True, help="Date is required")
cliente_parser.add_argument('time', type=str, required=True, help="Time is required")
cliente_parser.add_argument('services', type=str, required=True, help="Services is required")

# Decorador para reintentar en caso de errores operacionales
def retry(func):
    def wrapper(*args, **kwargs):
        retries = 3
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except OperationalError:
                db.session.rollback()
                time.sleep(2 ** attempt)  # Exponential backoff
        return jsonify({"error": "Database connection lost. Please try again later."}), 500
    return wrapper

# Función para obtener la tabla de clientes dinámica basada en el username
def get_cliente_table(username):
    """Devuelve la tabla de clientes para el usuario específico."""
    table_name = f"{username}"
    metadata = MetaData(bind=db.engine)
    cliente_table = Table(table_name, metadata, autoload=True)
    return cliente_table

# Recurso para manejar operaciones sobre un solo cliente (GET, PUT, DELETE)
class Cliente(Resource):
    @retry
    def get(self, username, id):
        cliente_table = get_cliente_table(username)
        cliente = db.session.query(cliente_table).filter_by(id=id).first()
        if cliente:
            return dict(cliente), 200
        else:
            return {"message": "Cliente no encontrado"}, 404
    
    @retry
    def delete(self, username, id):
        cliente_table = get_cliente_table(username)
        cliente = db.session.query(cliente_table).filter_by(id=id).first()
        if cliente:
            db.session.delete(cliente)
            db.session.commit()
            return '', 204
        else:
            return {"message": "Cliente no encontrado"}, 404
    
    @retry
    def put(self, username, id):
        cliente_table = get_cliente_table(username)
        cliente = db.session.query(cliente_table).filter_by(id=id).first()
        if not cliente:
            return {"message": "Cliente no encontrado"}, 404

        args = cliente_parser.parse_args()
        try:
            date = dt.datetime.fromisoformat(args['date'])
            time = dt.datetime.strptime(args['time'], "%H:%M:%S").time()
            cliente.name = args['name']
            cliente.cellphone = args['cellphone']
            cliente.date = date
            cliente.time = time
            cliente.days_for_appointment = (date.date() - cliente.register_date.date()).days
            db.session.commit()
            return dict(cliente), 201
        except (ValueError, TypeError) as e:
            return {'error': str(e)}, 400

# Recurso para manejar operaciones sobre la lista de clientes (GET, POST)
class Clientes(Resource):
    
    @retry
    def get(self, username):
        try:
            # Obtener los parámetros de fecha de la URL, si es que existen
            fecha = request.args.get('fecha')
            nextdays = request.args.get('nextdays')

            # Si se proveen los parámetros 'fecha' o 'nextdays', ejecutar lógica para slots
            if fecha or nextdays:
                return self.get_available_slots(username)

            # Si no se provee fecha, devolvemos todos los clientes
            cliente_table = get_cliente_table(username)
            clientes = db.session.query(cliente_table).all()

            # Convertir cada cliente en un diccionario y asegurarse de que todos los valores sean serializables
            clientes_list = []
            for cliente in clientes:
                cliente_dict = dict(cliente)

                # Convertir fechas, horas y otros objetos no serializables a cadenas
                for key, value in cliente_dict.items():
                    if isinstance(value, (date, datetime)):
                        cliente_dict[key] = value.isoformat()  # Convertir a formato ISO
                    elif isinstance(value, time):
                        cliente_dict[key] = value.strftime("%H:%M:%S")  # Convertir a formato HH:MM:SS

                clientes_list.append(cliente_dict)

            # Devolver la lista de clientes en formato JSON
            return make_response(jsonify(clientes_list), 200)

        except SQLAlchemyError as e:
            return make_response(jsonify({'error': 'Error de base de datos: ' + str(e)}), 500)

        except Exception as e:
            return make_response(jsonify({'error': str(e)}), 400)
    
    @retry
    def post(self, username):
        args = cliente_parser.parse_args()
        cliente_table = get_cliente_table(username)

        try:
            # Validar la entrada y convertir timestamp a fecha
            if 'date' not in args or not args['date']:
                return make_response(jsonify({"error": "El campo 'date' es requerido"}), 400)

            if 'time' not in args or not args['time']:
                return make_response(jsonify({"error": "El campo 'time' es requerido"}), 400)

            # Validar otros campos opcionales como 'cellphone' o 'services'
            if 'cellphone' not in args or not args['cellphone']:
                return make_response(jsonify({"error": "El campo 'cellphone' es requerido"}), 400)

            if 'name' not in args or not args['name']:
                return make_response(jsonify({"error": "El campo 'name' es requerido"}), 400)

            if 'services' not in args or not args['services']:
                return make_response(jsonify({"error": "El campo 'services' es requerido"}), 400)

            # Convertir el timestamp a una fecha
            try:
                timestamp = int(args['date']) / 1000
                date_formateada = datetime.fromtimestamp(timestamp).date()
            except ValueError:
                return make_response(jsonify({"error": "Formato de 'date' no válido"}), 400)

            # Convertir la hora
            try:
                time_formateada = datetime.strptime(args['time'], "%H:%M:%S").time()
            except ValueError:
                return make_response(jsonify({"error": "Formato de 'time' no válido. Debe ser HH:MM:SS"}), 400)

            # Crear un nuevo cliente en la tabla personalizada
            insert_query = cliente_table.insert().values(
                cellphone=args['cellphone'],
                name=args['name'],
                date=date_formateada,
                time=time_formateada,
                services=args['services'],
                register_date=datetime.now(),
                days_for_appointment=0
            )
            db.session.execute(insert_query)
            db.session.commit()

            # Formatear la respuesta
            response_data = {
                "cellphone": args['cellphone'],
                "name": args['name'],
                "date": date_formateada.isoformat(),
                "time": args['time'],
                "services": args['services'],
                "register_date": datetime.now().isoformat(),
            }

            return make_response(jsonify(response_data), 201)

        except SQLAlchemyError as e:
            db.session.rollback()  # Deshacer en caso de error de base de datos
            return make_response(jsonify({'error': 'Error de base de datos: ' + str(e)}), 500)

        except Exception as e:
            db.session.rollback()  # Deshacer en caso de otros errores
            return make_response(jsonify({'error': str(e)}), 400)


    @retry
    def get_available_slots(self, username):
        # Obtener el parámetro de fecha de la URL
        nextdays = request.args.get('nextdays')
        fecha = request.args.get('fecha')

        # Obtener los días laborales y horas laborales del usuario desde la base de datos
        usuario = db.session.query(UsuarioModel).filter_by(username=username).first()
        if not usuario:
            return {"message": "Usuario no encontrado"}, 404
        
        workdays = usuario.workdays.split(',')  # Lista de días laborales del usuario
        working_hours = usuario.workingHours.split(',')  # Lista de horas laborales del usuario

        # Convertir los días laborales a un formato que se pueda comparar (ej. 'monday', 'tuesday')
        dias_disponibles = [dia.lower().strip() for dia in workdays]
        
        print(f"Días laborales disponibles: {dias_disponibles}")

        import locale

        if fecha:
            try:
                # Convertir el timestamp de milisegundos a segundos
                timestamp = int(fecha) / 1000
                fecha_formateada = dt.datetime.fromtimestamp(timestamp).date()

                # Forzar el locale a inglés para obtener el día de la semana en inglés
                locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
                dia_semana = fecha_formateada.strftime('%A').lower()  # Obtener el día de la semana en inglés (e.g., 'monday')
                print(f"Fecha formateada: {fecha_formateada} (Día de la semana: {dia_semana})")

            except ValueError:
                return {"message": "El formato de la fecha no es válido. Usa un timestamp válido"}, 400

            # Obtener las horas laborales y días laborales del usuario
            usuario = db.session.query(UsuarioModel).filter_by(username=username).first()
            if not usuario:
                return {"message": "Usuario no encontrado"}, 404

            # Días laborales en formato ["monday", "tuesday", etc.]
            workdays = usuario.workdays.split(',')
            workdays = [day.strip().lower() for day in workdays]  # Asegurarse de que todos los días estén en minúsculas
            print(f"Días laborales del usuario: {workdays}")  # Depuración

            # Verificar si el día de la semana está dentro de los días laborales
            if dia_semana not in workdays:
                # Si el día no está dentro de los días laborales, devolver 1 en lugar de la fecha
                print(f"El día {dia_semana} no está dentro de los días laborales.")
                return {"fecha": 1, "slots": []}, 200

            # Si el día sí está dentro de los días laborales, continuar con el flujo normal
            print(f"El día {dia_semana} está dentro de los días laborales.")

            # Asumiendo que las horas laborales están guardadas en formato HH:MM
            working_hours = usuario.workingHours.split(',')
            print(f"Horas laborales del usuario: {working_hours}")  # Depuración

            # Asegurarse de que las horas están en formato de 24 horas con segundos (HH:MM:SS)
            working_hours_24 = [f"{hora.strip()}:00" for hora in working_hours]

            # Consulta para buscar citas que coincidan con la fecha proporcionada
            cliente_table = get_cliente_table(username)  # Obtener la tabla del cliente
            clientes = db.session.query(cliente_table).filter(
                cliente_table.c.date == fecha_formateada  # Comparación directa con la fecha
            ).all()

            if not clientes:
                # Si no hay citas registradas, todas las horas del usuario están disponibles
                slots_disponibles = [
                    {
                        "id": hora,  # El ID ya está en formato de 24 horas con segundos
                        "title": dt.datetime.strptime(hora, "%H:%M:%S").strftime("%I:%M %p")  # Convertir a formato 12 horas
                    } for hora in working_hours_24
                ]
                print(f"Slots disponibles (sin citas registradas): {slots_disponibles}")  # Depuración
                return {"fecha": fecha_formateada.strftime("%d-%m-%Y"), "slots": slots_disponibles}, 200

            # Extraer las horas ocupadas de los clientes encontrados y formatearlas en formato de 24 horas con segundos
            horas_ocupadas = [cliente.time.strftime("%H:%M:%S") for cliente in clientes]
            print(f"Horas ocupadas: {horas_ocupadas}")  # Depuración

            # Comparar y determinar las horas disponibles restando las horas ocupadas de las horas laborales del usuario
            horas_disponibles = [hora for hora in working_hours_24 if hora not in horas_ocupadas]
            print(f"Horas disponibles: {horas_disponibles}")  # Depuración

            # Crear la estructura de 'slots' con id en formato de 24 horas con segundos y title en formato AM/PM
            slots_disponibles = []
            
            # Forzar el locale a inglés para asegurar el formato AM/PM
            locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
            
            for hora in horas_disponibles:
                try:
                    hora_ampm = dt.datetime.strptime(hora, "%H:%M:%S").strftime("%I:%M %p").strip()
                    print(f"Hora convertida a AM/PM: {hora} -> {hora_ampm}")  # Depuración
                    slots_disponibles.append({
                        "id": hora,  # Mantener el ID en formato de 24 horas con segundos
                        "title": hora_ampm  # Formato 12 horas (AM/PM)
                    })
                except ValueError as e:
                    print(f"Error al convertir la hora {hora}: {e}")
                    return {"message": f"Error al convertir la hora {hora}: {str(e)}"}, 400

            # Restaurar el locale por si acaso
            locale.setlocale(locale.LC_TIME, '')

            # Retornar las horas disponibles
            return {"fecha": fecha_formateada.strftime("%d-%m-%Y"), "slots": slots_disponibles}, 200
        elif nextdays:
            try:
                # Obtener la fecha actual
                timestamp = int(nextdays) / 1000
                fecha_actual = dt.datetime.fromtimestamp(timestamp).date()

                # Consulta para obtener las fechas con citas a partir del día de hoy
                cliente_table = get_cliente_table(username)
                citas_proximas = db.session.query(cast(cliente_table.c.date, Date)).filter(
                    cast(cliente_table.c.date, Date) >= fecha_actual
                ).group_by(cast(cliente_table.c.date, Date)).order_by(cast(cliente_table.c.date, Date)).all()

                dias_disponibles_list = []
                count_dias_disponibles = 0

                # Revisar las fechas encontradas
                for cita in citas_proximas:
                    dia_semana = cita[0].strftime('%A').lower()

                    # Verificar si el día es un día laboral
                    if dia_semana not in dias_disponibles:
                        continue

                    # Obtener las horas ocupadas para este día
                    horas_ocupadas = db.session.query(cliente_table.c.time).filter(
                        cast(cliente_table.c.date, Date) == cita[0]
                    ).all()

                    # Convertir las horas ocupadas a un formato legible (ejemplo: "09:00 AM")
                    horas_ocupadas_formato = [hora[0].strftime("%I:%M %p") for hora in horas_ocupadas]

                    # Determinar las horas disponibles
                    horas_disponibles = [hora for hora in working_hours if hora not in horas_ocupadas_formato]

                    if horas_disponibles:
                        cita_datetime = dt.datetime.combine(cita[0], dt.datetime.min.time())
                        fecha_formateada = cita[0].strftime("%a %d de %b").capitalize()

                        dias_disponibles_list.append({
                            "id": int(cita_datetime.timestamp() * 1000),
                            "fecha": fecha_formateada,
                            "horas_disponibles": horas_disponibles
                        })
                        count_dias_disponibles += 1

                    if count_dias_disponibles >= 3:
                        break

                while count_dias_disponibles < 3:
                    fecha_proxima = fecha_actual + dt.timedelta(days=count_dias_disponibles)
                    fecha_proxima_datetime = dt.datetime.combine(fecha_proxima, dt.datetime.min.time())
                    fecha_formateada = fecha_proxima.strftime("%a %d de %b").capitalize()

                    dias_disponibles_list.append({
                        "id": int(fecha_proxima_datetime.timestamp() * 1000),
                        "fecha": fecha_formateada,
                        "horas_disponibles": working_hours
                    })
                    count_dias_disponibles += 1

                return {"message": "Días con citas disponibles", "dias_disponibles": dias_disponibles_list[:3]}
            except Exception as e:
                return {"message": f"Error al procesar la solicitud: {str(e)}"}, 500
        else:
            # Si no se pasa la fecha, devolver todos los clientes
            cliente_table = get_cliente_table(username)
            clientes = db.session.query(cliente_table).all()
            return [dict(cliente) for cliente in clientes]
