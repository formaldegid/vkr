import dash
from dash import html, dcc, Input, Output, State
from flask_login import login_user
import flask

dash.register_page(__name__, path='/login')

def layout():
    return html.Div([
        html.Div([
            html.H2("Авторизация", style={'text-align': 'center', 'color': '#333'}),
            dcc.Input(id='login-user', type='text', placeholder='Логин', 
                     style={'width': '100%', 'margin-bottom': '15px', 'padding': '10px', 'height': '100%'}),
            dcc.Input(id='login-pass', type='password', placeholder='Пароль', 
                     style={'width': '100%', 'margin-bottom': '20px', 'padding': '10px', 'height': '100%'}),
            html.Button('Войти', id='btn-login', n_clicks=0,
                        style={'width': '100%', 'background': '#007bff', 'color': 'white', 'border': 'none', 'padding': '10px', 'cursor': 'pointer'}),
            html.Div(id='login-error', style={'color': 'red', 'margin-top': '15px', 'text-align': 'center'})
        ], style={'width': '350px', 'margin': '100px auto', 'padding': '30px', 'border': '1px solid #ddd', 'border-radius': '8px', 'background': 'white', 'box-shadow': '0 4px 6px rgba(0,0,0,0.1)'})
    ])

@dash.callback(
    Output('url', 'pathname', allow_duplicate=True),
    Output('login-error', 'children'),
    Input('btn-login', 'n_clicks'),
    State('login-user', 'value'),
    State('login-pass', 'value'),
    prevent_initial_call=True
)
def handle_login(n, username, password):
    if n > 0:
        
        from auth_utils import load_users_db, User 
        from flask_login import login_user
        
        users = load_users_db()
        if username in users and users[username]['password'] == password:
            user_data = users[username]
            user_obj = User(username, user_data['role'], user_data['depts'])
            login_user(user_obj)
            return '/', ""
        return dash.no_update, "Неверный логин или пароль"
    return dash.no_update, ""
