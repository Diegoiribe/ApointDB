from flask import current_app
from main import db
from main.models.Usuario import Usuario as UsuarioModel  # Importación del modelo
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, date
import requests
import json
from sqlalchemy import inspect
import logging

def update_days_for_appointment():
    logging.info("Iniciando el proceso de actualización de días para citas...")
    
    # Obtenemos todos los usuarios
    usuarios = UsuarioModel.query.all()
    inspector = inspect(db.engine)  # Creamos el inspector para interactuar con las tablas

    for usuario in usuarios:
        user_name = usuario.username  # Nombre del usuario (username, no name)
        table_name = f"{user_name}"  # Nombre de la tabla dinámica de clientes

        try:
            # Verificamos si la tabla existe usando inspect
            if inspector.has_table(table_name):
                logging.info(f"La tabla {table_name} existe. Procesando...")

                # Obtenemos los clientes
                query = f"SELECT * FROM {table_name}"
                clientes = db.session.execute(query).fetchall()

                for cliente in clientes:
                    try:
                        # Si `cliente.date` es una cadena de texto, la convertimos a un objeto datetime.date
                        if isinstance(cliente.date, str):
                            # Asegúrate de que el formato aquí coincide con el formato de las fechas en tu base de datos
                            cliente_date = datetime.strptime(cliente.date, "%Y-%m-%d").date()
                        else:
                            cliente_date = cliente.date

                        # Calculamos los días para la cita
                        days_for_appointment = (cliente_date - datetime.utcnow().date()).days
                        logging.info(f"Cliente {cliente.id}: Días para la cita = {days_for_appointment}")

                        # Actualizamos el campo `days_for_appointment`
                        update_query = f"UPDATE {table_name} SET days_for_appointment = :days WHERE id = :id"
                        db.session.execute(update_query, {'days': days_for_appointment, 'id': cliente.id})

                        # Si el número de días para la cita es 0, enviamos el mensaje de WhatsApp
                        if days_for_appointment == 0:
                            send_whatsapp_message(cliente.cellphone, f"Hola {cliente.name}, tu cita es mañana.")
                    except Exception as e:
                        logging.error(f"Error al procesar el cliente {cliente.id}: {str(e)}")

                db.session.commit()
                logging.info(f"Cambios guardados para la tabla {table_name}.")
            else:
                logging.warning(f"La tabla {table_name} no existe.")
        except Exception as e:
            logging.error(f"Error al acceder a la tabla {table_name}: {str(e)}")
            db.session.rollback()


def send_whatsapp_message(to_number, message_body):
    print(f"Preparando para enviar mensaje a {to_number}...")  # Depurador 12

    url = "https://api.gupshup.io/wa/api/v1/msg"

    # Asegúrate de agregar el prefijo del país '52' si no está presente
    if not to_number.startswith("521"):
        to_number = "521" + to_number

    payload = {
        "channel": "whatsapp",
        "source": 5216675014303,  # Verifica que este número esté correctamente registrado en Gupshup
        "destination": 5216674507062,   # Aquí el número ya incluirá el código de país
        "message": json.dumps({
            "type": "text",
            "text": message_body
        }),
        "src.name": "myapp",
        "disablePreview": False,
        "encode": False
    }
    
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "apikey": "o6botgtule9omsamb70z42udlyzp3cql"  # Asegúrate de que esta API key sea la correcta
    }

    # Enviar el mensaje POST
    response = requests.post(url, data=payload, headers=headers)

    # Comprobar si la solicitud fue exitosa
    if response.status_code == 200:
        print(f"Mensaje enviado exitosamente a {to_number}: {response.text}")  # Depurador 13
    else:
        print(f"Error al enviar mensaje a {to_number}: {response.status_code} - {response.text}")  # Depurador 14
