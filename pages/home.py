import dash
from dash import html, dcc, Input, Output, State, ALL, ctx
import os
import json
from flask_login import current_user

dash.register_page(__name__, path='/')

def get_logs_as_components(dept_slug):
    log_file = os.path.join('data', f"{dept_slug}_logs.json")
    logs_ui = []
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                for log in logs:
                    logs_ui.append(
                        html.Div(className='log-item', children=[
                            html.Div("📄", className='log-icon'),
                            html.Div(className='log-text', children=[
                                html.Div(log.get('title', 'Без названия'), className='log-item-title'),
                                
                                html.Div(f"{log.get('category', '')} • {log.get('date', '')}", 
                                         className='log-item-meta')
                            ])
                        ])
                    )
        except Exception as e:
            print(f"Ошибка чтения логов {dept_slug}: {e}")
            
    if not logs_ui:
        logs_ui = html.Div("Пока нет изменений", style={'color': '#6c757d', 'padding': '20px', 'text-align': 'center'})
        
    return logs_ui


def layout():
    if not current_user.is_authenticated:
        return html.Div()

    
    all_depts = [
        {'id': 'dept-it', 'title': 'IT Департамент', 'desc': 'Архитектура серверов', 'icon': 'it-icon', 'slug': 'it'},
        {'id': 'dept-hr', 'title': 'HR Департамент', 'desc': 'Структура персонала', 'icon': 'hr-icon', 'slug': 'hr'},
        {'id': 'dept-marketing', 'title': 'Маркетинг', 'desc': 'Воронки продаж', 'icon': 'mkt-icon', 'slug': 'marketing'},
    ]
    
    allowed_cards = []
    for d in all_depts:
        if d['slug'] in current_user.depts:
            allowed_cards.append(
                html.Div([
                    html.Div(d['slug'].upper(), className=f"card-icon {d['icon']}"),
                    html.H4(d['title']),
                    html.P(d['desc']),
                ], 
                id={'type': 'dept-card', 'index': d['slug']}, 
                className="dept-card", 
                n_clicks=0)
            )

    return html.Div([
        # Левая панель
        html.Div([
            html.Div([
                html.H2("Graph AI", className="logo-title"),
                html.P("Constructor", className="logo-subtitle")
            ], className="sidebar-header"),
            html.Div([
                html.A("Главная", href="#", className="nav-link active"),
            ], className="sidebar-nav"),
        ], className="sidebar"),

        # Основная рабочая область
        html.Div([
            
            html.Div([
                html.H1("Управление графами и отделами", className="page-title"),

            ], className="top-header"),

            
            html.Div([
                html.H3("Доступные отделы", className="section-title"),
                html.Div(allowed_cards, className="card-grid")
            ], className="content-area")
        ], className="main-content"),

        # Всплывающее меню
        html.Div(id='dept-modal-overlay', className='modal-overlay', style={'display': 'none'}, children=[
            html.Div(className='modal-content', children=[
                html.Div(className='modal-header', children=[
                    html.H2(id='modal-dept-title', children="Отдел", style={'margin': 0}),
                    html.Button("×", id='btn-close-modal', className='close-btn', n_clicks=0)
                ]),
                
                dcc.Link("Перейти к графу отдела →", id='modal-graph-link', href="#", className='btn-primary btn-go-graph'),
                
                html.Div(className='logs-section', children=[
                    html.H3("Последние изменения", className='logs-title'),
                    html.P("Недавно обновленные документы", className='logs-subtitle'),
                    html.Div(id='modal-logs-list', className='logs-list')
                ])
            ])
        ])
    ], className="dashboard-layout")


# Всплывающее окно и логи
@dash.callback(
    Output('dept-modal-overlay', 'style'),
    Output('modal-dept-title', 'children'),
    Output('modal-graph-link', 'href'),
    Output('modal-logs-list', 'children'),
    Input({'type': 'dept-card', 'index': ALL}, 'n_clicks'),
    Input('btn-close-modal', 'n_clicks'),
    State('dept-modal-overlay', 'style'),
    prevent_initial_call=True
)
def toggle_modal(dept_clicks, close_clicks, current_style):
    triggered_id = ctx.triggered_id

    
    if not triggered_id or triggered_id == 'btn-close-modal':
        return {'display': 'none'}, "", "#", []

    
    if isinstance(triggered_id, dict) and triggered_id.get('type') == 'dept-card':
        dept_slug = triggered_id['index']
        
        
        titles = {
            'it': 'IT Департамент',
            'hr': 'HR Департамент',
            'marketing': 'Маркетинг'
        }
        
        
        logs_content = get_logs_as_components(dept_slug)
        
        return (
            {'display': 'flex'}, 
            titles.get(dept_slug, "Отдел"), 
            f"/graph/{dept_slug}", 
            logs_content
        )

    return {'display': 'none'}, "", "#", []
