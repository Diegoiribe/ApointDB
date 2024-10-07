from sqlalchemy.schema import CreateTable
from sqlalchemy import text
from main import db
from ..models.Cliente import Cliente as ClienteModel  # Importamos el modelo de Cliente

def create_client_table_for_user(username):
    """Crea una tabla personalizada para los clientes de cada usuario usando el modelo Cliente."""
    table_name = f"{username}"
    cliente_model_table = ClienteModel.__table__
    
    create_table_statement = CreateTable(cliente_model_table).compile(db.engine)
    modified_create_table = str(create_table_statement).replace(ClienteModel.__tablename__, table_name)
    
    db.engine.execute(text(modified_create_table))
    
    return table_name
