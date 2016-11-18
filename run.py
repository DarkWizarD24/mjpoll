# coding: utf-8

from mjpoll import app

if __name__ == "__main__":
    app.config.update(TEMPLATES_AUTO_RELOAD=True)
    app.run(debug=True)
