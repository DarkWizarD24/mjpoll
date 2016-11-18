# coding: utf-8

from flask import Flask
from flask_babel import Babel
from flask_bootstrap import Bootstrap

app = Flask(__name__)
app.config.from_pyfile('application.cfg')

app.secret_key = '_\xeb\xaa9\xea\xb9&\xe8\xdfx\xd4oKu\x01\xf3\x94d\x08\xdeGs\x11<' #TODO get if from config

babel = Babel(app)

Bootstrap(app)

import views
import data
from data import init_db
