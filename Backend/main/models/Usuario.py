from werkzeug.security import generate_password_hash, check_password_hash
from .. import db

class Usuario(db.Model):
    __tablename__ = 'Usuario'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Aquí se almacena el hash de la contraseña
    active = db.Column(db.Boolean, default=True)
    imagen = db.Column(db.String(255))  # Almacenar la URL de la imagen
    workdays = db.Column(db.String(255), nullable=False)
    workingHours = db.Column(db.String(255), nullable=False)

    # Setter para hashear la contraseña
    @property
    def plain_password(self):
        raise AttributeError("No se puede acceder a la contraseña en texto plano")

    @plain_password.setter
    def plain_password(self, password):
        """Genera el hash de la contraseña y lo guarda en el campo 'password'"""
        print(f"Generando hash para la contraseña: {password}")  # Depuración
        self.password = generate_password_hash(password)  # Aquí se genera el hash

    # Método para validar la contraseña
    def validate_password(self, password):
        """Valida si la contraseña es correcta comparando el hash"""
        return check_password_hash(self.password, password)

    def __repr__(self):
        return f"<Usuario {self.username}>"

    def to_json(self):
        """Convierte la instancia de Usuario a formato JSON"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "active": self.active,
            "imagen": self.imagen,
            "workdays": self.workdays,
            "workingHours": self.workingHours
        }

    @staticmethod
    def from_json(usuario_json):
        """Crea una instancia de UsuarioModel a partir de un JSON"""
        try:
            username = usuario_json.get("username")
            email = usuario_json.get("email")
            password = usuario_json.get("password")  # La contraseña llega en texto plano
            active = usuario_json.get("active", True)  # Valor por defecto a True
            imagen = usuario_json.get("imagen")  # URL de la imagen
            workdays = usuario_json.get("workdays")
            workingHours = usuario_json.get("workingHours")

            # Crear la instancia del usuario
            usuario = UsuarioModel(
                username=username,
                email=email,
                active=active,
                imagen=imagen,
                workdays=workdays,
                workingHours=workingHours
            )

            # Asignar la contraseña usando el setter (esto generará el hash)
            usuario.plain_password = password

            return usuario
        except (TypeError, ValueError) as e:
            raise ValueError(f"Error al convertir JSON a Usuario: {e}")
