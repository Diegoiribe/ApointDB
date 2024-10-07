from flask import request, Blueprint
from .. import db
from main.models import UsuarioModel
from flask_jwt_extended import create_access_token

auth = Blueprint('auth', __name__, url_prefix='/auth')

@auth.route('/login', methods=['POST'])
def login():
    # Obtener el usuario por email
    usuario = db.session.query(UsuarioModel).filter(UsuarioModel.email == request.get_json().get("email")).first_or_404()
    
    # Validar la contraseña
    if usuario.validate_password(request.get_json().get("password")):
        # Crear el access_token utilizando el ID del usuario (serializable)
        access_token = create_access_token(identity=str(usuario.id))  # Usar el ID como identidad en el token
        
        # Preparar los datos para el retorno
        data = {
            "id": str(usuario.id),
            "username": usuario.username,
            "email": usuario.email,
            "access_token": access_token
        }
        
        # Devolver el token y la información del usuario
        return data, 200
    else:
        return {"message": "Invalid credentials"}, 401
