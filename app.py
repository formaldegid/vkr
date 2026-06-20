import dash
from dash import Dash, html, dcc, Input, Output, State
import flask
from flask_login import LoginManager, logout_user, current_user
import os
from auth_utils import User, load_users_db

# --- Настройка Flask-Login ---
server = flask.Flask(__name__)
server.config.update(SECRET_KEY=os.urandom(24))

login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'

@login_manager.user_loader
def load_user(user_id):
    users = load_users_db()
    if user_id in users:
        u = users[user_id]
        return User(user_id, u['role'], u['depts'])
    return None

# --- Инициализация Dash ---
app = Dash(__name__, server=server, use_pages=True, suppress_callback_exceptions=True)

# Глобальный макет с проверкой авторизации
app.layout = html.Div([
    dcc.Location(id='url', refresh=True),
    # Верхняя панель
    html.Div(id='header-container'),
    
    
    dash.page_container
])

#Отображения хедера и редиректа
@app.callback(
    Output('header-container', 'children'),
    Output('url', 'pathname', allow_duplicate=True),
    Input('url', 'pathname'),
    prevent_initial_call=True
)
def check_auth(pathname):
    if not current_user.is_authenticated and pathname != '/login':
        return None, '/login'
    
    if current_user.is_authenticated:
        header = html.Div([
            html.Span(f"Пользователь: {current_user.id} ({current_user.role})", style={'margin-right': '20px'}),
            html.A("Выйти", href="/logout", style={'color': 'red', 'text-decoration': 'none', 'font-weight': 'bold'}),
            html.Hr()
        ], style={'padding': '10px 20px', 'background': '#f8f9fa', 'text-align': 'right'})
        return header, dash.no_update
    
    return None, dash.no_update

#Разлогин
@server.route('/logout')
def logout():
    logout_user()
    return flask.redirect('/login')

if __name__ == '__main__':
    app.run(debug=False)
