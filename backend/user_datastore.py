from flask_security import SQLAlchemyUserDatastore
from .Sqldatabase import db
from .models import User, Roles

user_datastore = SQLAlchemyUserDatastore(db, User, Roles)
