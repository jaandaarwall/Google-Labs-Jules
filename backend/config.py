class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'thisisasecretkey'
    SECURITY_PASSWORD_SALT = 'thisisasecretsalt'
    