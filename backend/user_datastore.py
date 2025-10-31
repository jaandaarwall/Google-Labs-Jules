from flask_security import SQLAlchemyUserDatastore

from .Sqldatabase import db
from .models import *

user_datastore = SQLAlchemyUserDatastore(db,User, Roles)