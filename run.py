import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.app import app, init_db

if __name__ == '__main__':
    init_db(app)
    app.run(debug=True)
