from .. import db
import datetime as dt

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cellphone = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)  # Solo la fecha
    time = db.Column(db.Time, nullable=False)   # Solo la hora
    services = db.Column(db.String(50), nullable=False)
    register_date = db.Column(db.Date, default=dt.datetime.now)
    days_for_appointment = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f"<Cliente {self.name}>"

    def to_json(self):
        return {
            "id": self.id,
            "cellphone": self.cellphone,
            "name": self.name,
            "register_date": self.register_date.isoformat() if self.register_date else None,
            "date": self.date.isoformat() if self.date else None,
            "time": self.time.strftime("%H:%M:%S") if self.time else None,
            "services": self.services,
            "days_for_appointment": self.days_for_appointment
        }

    @staticmethod
    def from_json(cliente_json):
        try:
            cellphone = cliente_json.get("cellphone")
            name = cliente_json.get("name")

            # Convertir el timestamp de milisegundos a segundos y luego a fecha
            timestamp_ms = int(cliente_json.get('date')) / 1000.0
            date = dt.datetime.fromtimestamp(timestamp_ms).date()  # Solo la parte de la fecha

            # Convertir la hora de formato "%H:%M:%S"
            time = dt.datetime.strptime(cliente_json.get('time'), "%H:%M:%S").time()

            # Obtener el servicio o asignar un valor predeterminado si no se proporciona
            services = cliente_json.get("services", "Servicio estándar")  # Valor predeterminado

            # Crear el objeto cliente con la fecha y hora convertidas
            register_date = dt.datetime.now()

            # Calcular los días hasta la cita
            days_for_appointment = (date - register_date.date()).days

            return Cliente(
                cellphone=cellphone, 
                name=name, 
                date=date, 
                time=time,
                services=services,
                register_date=register_date, 
                days_for_appointment=days_for_appointment
            )

        except (ValueError, TypeError) as e:
            raise ValueError(f"Error al convertir JSON a Cliente: {e}")
