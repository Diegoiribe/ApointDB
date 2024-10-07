import boto3
from flask_restful import Resource
from flask import request, jsonify
from .. import db
from main.models import UsuarioModel
from datetime import datetime  # Importar datetime para la generación del timestamp
import os
from .db_utils import create_client_table_for_user

# Configuración de S3
S3_BUCKET = "botkevin"
S3_REGION = "us-east-2"
S3_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
S3_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Crear el cliente de S3
s3_client = boto3.client(
    "s3",
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION
)

def generate_filename():
    """Genera un nombre de archivo con el formato 'img_<timestamp>.jpg'."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Formato: AAAAMMDD_HHMMSS
    return f"img_{timestamp}.jpg"

def upload_image_to_s3(image_data):
    """Sube la imagen a S3 y devuelve la URL pública."""
    try:
        filename = generate_filename()  # Generar el nombre de archivo con la fecha y hora
        s3_client.put_object(Bucket=S3_BUCKET, Key=filename, Body=image_data)
        return f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{filename}"
    except Exception as e:
        raise ValueError(f"Error al subir la imagen a S3: {e}")

class Usuario(Resource):
    
    def get(self, id):
        usuario = db.session.query(UsuarioModel).get_or_404(id)
        return usuario.to_json()
    
    def delete(self, id):
        usuario = db.session.query(UsuarioModel).get_or_404(id)
        db.session.delete(usuario)
        db.session.commit()
        return '', 204
    
    def put(self, id):
        usuario = db.session.query(UsuarioModel).get_or_404(id)
        
        # Manejar el envío de archivos (imagen)
        if 'imagen' in request.files:
            imagen_file = request.files['imagen']
            # Subir la imagen a S3 y obtener la URL
            usuario.imagen = upload_image_to_s3(imagen_file.read())  # Subir la imagen con un nombre generado automáticamente
        
        # Obtener datos del cuerpo de la solicitud (JSON o formulario)
        data = request.form or request.get_json()
        usuario.username = data.get("username", usuario.username)
        usuario.email = data.get("email", usuario.email)
        usuario.password = data.get("password", usuario.password)
        usuario.active = data.get("active", usuario.active)
        usuario.workdays = data.get("workdays", usuario.workdays)
        usuario.workingHours = data.get("workingHours", usuario.workingHours)
        
        db.session.commit()
        return usuario.to_json(), 201

class Usuarios(Resource):
    
    def get(self):
        usuarios = db.session.query(UsuarioModel).all()
        return jsonify([usuario.to_json() for usuario in usuarios])
    
    def post(self):
        # Manejar imagen
        imagen_file = request.files.get('imagen')
        imagen_url = None
        
        if imagen_file:
            # Subir la imagen a S3 y obtener la URL
            imagen_url = upload_image_to_s3(imagen_file.read())  # Subir la imagen con un nombre generado automáticamente
        
        # Manejar otros datos del formulario o JSON
        data = request.form or request.get_json()

        # Crear instancia del usuario sin la contraseña primero
        usuario = UsuarioModel(
            username=data.get("username"),
            email=data.get("email"),
            active=data.get("active", True),  # Valor por defecto a True
            imagen=imagen_url,  # Almacenar la URL de la imagen si existe
            workdays=data.get("workdays"),
            workingHours=data.get("workingHours")
        )
        
        # Asignar la contraseña (esto debería activar el setter y generar el hash)
        usuario.plain_password = data.get("password")  # Aquí debería activarse el setter

        # Verificar que el hash se está generando
        print(f"Hash generado para la contraseña: {usuario.password}")  # Aquí deberías ver el hash

        # Guardar el usuario en la base de datos
        db.session.add(usuario)
        db.session.commit()

        create_client_table_for_user(usuario.username)

        return usuario.to_json(), 201