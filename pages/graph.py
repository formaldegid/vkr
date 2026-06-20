import dash
from dash import html, dcc, Input, Output, State, ctx, clientside_callback, callback, ALL, no_update
import json
import os
import requests
import datetime
import time
from flask_login import current_user

dash.register_page(__name__, path_template='/graph/<dept_id>')

# --- Утилита для логирования ---
def log_action(dept_id, title, category):
    if not dept_id or dept_id == 'root': return
    log_file = os.path.join('data', f"{dept_id}_logs.json")
    
    
    username = current_user.id if current_user.is_authenticated else "Unknown"
    
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except: pass
        
    logs.insert(0, {
        'title': title,
        'category': f"{category} ({username})", 
        'date': datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(logs[:50], f, ensure_ascii=False, indent=4)

# --- Работа с БД ---
def get_path(dept_id):
    return os.path.join('data', f"{dept_id}.json")

def load_all_data(dept_id):
    DB_FILE = get_path(dept_id)
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict): return data
            except: pass
    return {dept_id: []}

def save_all_data(data, dept_id):
    DB_FILE = get_path(dept_id)
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- Макет страницы ---
def layout(dept_id=None, **kwargs):
    if not current_user.is_authenticated:
        return html.Div("Доступ запрещен")

    if dept_id not in current_user.depts:
        return html.Div(f"У вас нет прав для просмотра отдела {dept_id}")

    is_admin = getattr(current_user, 'role', 'user') == 'admin'

    initial_id = dept_id if dept_id else 'root'

    return html.Div([
        # Хранилища состояния
        dcc.Store(id='current-graph-id', data=initial_id),
        dcc.Store(id='root-dept-id', data=initial_id),
        dcc.Store(id='nav-history', data=[]),
        dcc.Store(id='selected-item-id', data=None),
        dcc.Store(id='folder-click-timestamp', data={'id': None, 'ts': 0}),
        dcc.Store(id='ai-context-store', data=[]),

        # Поля связи JS с Python
        html.Div([
            dcc.Input(id='js-ctx-target-id', value=''),
            dcc.Input(id='js-ctx-target-label', value=''),
            dcc.Input(id='js-ctx-target-date', value=''), 
            dcc.Input(id='js-ctx-x', value=''),
            dcc.Input(id='js-ctx-y', value=''),
            dcc.Input(id='js-ctx-mode', value=''),
            html.Button(id='js-ctx-trigger'),
            html.Button(id='js-ctx-hide-trigger'),
        
            dcc.Input(id='js-drop-file-id', value='', style={'display': 'none'}),
            html.Button(id='js-drop-trigger', style={'display': 'none'})
        ], style={'display': 'none'}),

        
        html.H1(f"База знаний: Отдел {dept_id}", style={'padding': '15px 20px', 'margin': '0'}),

        # Основной контейнер
        html.Div([

            # 1. Левая панель
            html.Div([
                html.H3("Проводник", style={'background': '#f4f5f7', 'padding': '10px', 'margin': '0', 'font-size': '16px'}),
                html.Div(id='left-sidebar-tree', style={'padding': '10px', 'overflow-y': 'auto', 'height': 'calc(100% - 40px)'})
            ], style={'width': '25%', 'border': '1px solid #dee2e6', 'border-radius': '5px 0 0 5px', 'background': 'white', 'display': 'flex', 'flex-direction': 'column'}),

            # 2. Центральная панель
            html.Div(id='central-panel', children=[
                html.Div([
                    html.Div([
                        html.Button("← Назад", id='btn-step-back', style={'margin-right': '10px', 'padding': '5px 10px', 'cursor': 'pointer'}),
                        html.Button("В корень", id='btn-back', style={'margin-right': '20px', 'padding': '5px 10px', 'cursor': 'pointer'}),
                    ], style={'display': 'flex', 'align-items': 'center'}),
                    
                    html.Div([
                        dcc.Input(id='doc-search', type="text", placeholder="Поиск по файлам...", style={'padding': '5px', 'width': '200px', 'border': '1px solid #ddd', 'border-radius': '4px', 'position': 'relative', 'zIndex': '2001'}),
                        html.Div(id='suggestions-container', style={'display': 'none', 'position': 'absolute', 'top': '100%', 'right': '0', 'zIndex': '2000', 'background': 'white', 'width': '100%', 'boxShadow': '0 4px 12px rgba(0,0,0,0.2)'}) 
                    ], style={'position': 'relative'})
                ], style={'padding': '10px', 'background': '#f8f9fa', 'border-bottom': '1px solid #dee2e6', 'display': 'flex', 'justify-content': 'space-between', 'align-items': 'center', 'overflow': 'visible', 'position': 'relative', 'zIndex': '10'}),
                
                html.Div(id='breadcrumbs', style={'padding': '10px', 'font-weight': 'bold', 'color': '#495057'}),

                html.Div([
                    html.Div("Имя", style={'width': '70%', 'display': 'inline-block', 'color': '#adb5bd', 'font-size': '14px'}),
                    html.Div("Статус", style={'width': '30%', 'display': 'inline-block', 'color': '#adb5bd', 'text-align': 'right', 'font-size': '14px'}),
                ], style={'padding': '5px 10px', 'border-bottom': '2px solid #dee2e6'}),

                html.Div(id='file-explorer-container', children=[
                    html.Div(id='file-explorer-list', style={'min-height': '400px', 'padding': '10px', 'position': 'relative'})
                ])

            ], style={'width': '50%', 'border-top': '1px solid #dee2e6', 'border-bottom': '1px solid #dee2e6', 'background': 'white', 'display': 'flex', 'flex-direction': 'column', 'padding-bottom': '50vh', 'flex': '1', 'box-sizing': 'border-box'}),

            # 3. Правая панель
            html.Div([
                html.H3("Просмотр данных", style={'margin-top': '0'}),
                html.Div(id='node-info', style={'padding': '10px', 'background': '#e7f3ff', 'border-radius': '5px', 'margin-bottom': '20px', 'min-height': '100px', 'overflow-y': 'auto'}, children="Выберите файл для просмотра"),
                html.Hr(),
                html.H3("ИИ Помощник"),
                
                # Drop Zone
                html.Div(id='ai-drop-zone', children=[
                    html.Div(id='ai-context-badges', style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '5px', 'marginBottom': '10px'}),
                    dcc.Textarea(id='ai-query', placeholder='Перетащите файлы сюда для добавления в контекст,\nа затем задайте вопрос...', style={'width': '100%', 'height': '80px', 'padding': '8px', 'boxSizing': 'border-box'}),
                ], style={'border': '2px dashed #ccc', 'borderRadius': '5px', 'padding': '10px', 'transition': '0.3s', 'background': '#fff', 'marginBottom': '10px'}),
                
                html.Button('Спросить ИИ', id='btn-ai', style={'width': '100%', 'background': '#28a745', 'color': 'white', 'border': 'none', 'padding': '8px', 'cursor': 'pointer', 'border-radius': '4px'}),
                dcc.Loading(html.Div(id='ai-out', style={'margin-top': '15px', 'font-size': '14px', 'white-space': 'pre-wrap'}))
            ], style={'width': '30%', 'border': '1px solid #dee2e6', 'border-left': 'none', 'padding': '15px', 'border-radius': '0 5px 5px 0', 'background': '#fafafa', 'display': 'flex', 'flex-direction': 'column'})

        ], style={'display': 'flex', 'margin': '0 20px', 'font-family': 'sans-serif', 'min-height': 'calc(100vh - 120px)', 'height': 'auto', 'align-items': 'stretch'}),

        # --- Контекстное меню ---
        html.Div(id='context-menu', style={'display': 'none'}, children=[
            html.Div(id='ctx-menu-create', children=[
                 html.Div("Новый элемент", style={'font-weight': 'bold', 'margin-bottom': '10px'}),
                 dcc.Input(id={'type': 'admin-input', 'index': 'new-id'}, placeholder='ID', style={'width': '100%', 'margin-bottom': '8px', 'padding': '5px', 'box-sizing': 'border-box'}),
                 dcc.Input(id={'type': 'admin-input', 'index': 'new-label'}, placeholder='Название', style={'width': '100%', 'margin-bottom': '8px', 'padding': '5px', 'box-sizing': 'border-box'}),
                 
                 # Поле даты для создания
                 html.Div("Актуален до (оставьте пустым для бессрочно):", style={'font-size': '11px', 'color': '#666', 'margin-bottom': '2px'}),
                 dcc.Input(id={'type': 'admin-input', 'index': 'new-valid-until'}, type='date', style={'width': '100%', 'margin-bottom': '8px', 'padding': '5px', 'box-sizing': 'border-box'}),
                 
                 dcc.Checklist(id={'type': 'admin-input', 'index': 'is-folder'}, options=[{'label': ' Папка', 'value': 'sub'}], style={'font-size': '13px', 'margin-bottom': '10px'}),
                 html.Button('Создать', id={'type': 'admin-btn', 'index': 'create'}, style={'background': '#28a745', 'color': 'white', 'border': 'none', 'padding': '8px', 'width': '100%', 'cursor': 'pointer', 'border-radius': '4px'})
            ]),
            html.Div(id='ctx-menu-edit', children=[
                 html.Div("Действия", style={'font-weight': 'bold', 'margin-bottom': '10px'}),
                 html.Div('ID', style={'margin-bottom': '5px', 'font-size': '12px'}),
                 dcc.Input(id={'type': 'admin-input', 'index': 'edit-id'}, placeholder='Новый ID', style={'width': '100%', 'margin-bottom': '8px', 'padding': '5px', 'box-sizing': 'border-box'}),
                 html.Div('Название', style={'margin-bottom': '5px', 'font-size': '12px'}),
                 dcc.Input(id={'type': 'admin-input', 'index': 'edit-label'}, placeholder='Название', style={'width': '100%', 'margin-bottom': '8px', 'padding': '5px', 'box-sizing': 'border-box'}),
                 
                 # Поле даты для редактирования
                 html.Div('Актуален до', style={'margin-bottom': '5px', 'font-size': '12px'}),
                 dcc.Input(id={'type': 'admin-input', 'index': 'edit-valid-until'}, type='date', style={'width': '100%', 'margin-bottom': '12px', 'padding': '5px', 'box-sizing': 'border-box'}),
                 
                 html.Button('Сохранить', id={'type': 'admin-btn', 'index': 'save'}, style={'background': '#0074D9', 'color': 'white', 'border': 'none', 'padding': '8px', 'width': '100%', 'margin-bottom': '8px', 'cursor': 'pointer', 'border-radius': '4px'}),
                 html.Button('Удалить', id={'type': 'admin-btn', 'index': 'delete'}, style={'background': '#dc3545', 'color': 'white', 'border': 'none', 'padding': '8px', 'width': '100%', 'cursor': 'pointer', 'border-radius': '4px'})
            ])
        ])
    ])

# JS скрипт для контекстного меню
clientside_callback(
    """
    function(id) {
        if (!window.dashCtxAttached) {
            document.addEventListener('contextmenu', function(e) {
                const container = document.getElementById('central-panel');
                if (container && container.contains(e.target)) {
                    e.preventDefault();
                    
                    const item = e.target.closest('.explorer-item');
                    const isItem = !!item;
                    
                    const setVal = (targetId, value) => {
                        const el = document.getElementById(targetId);
                        if (el) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(el, value);
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    };

                    const nodeId = isItem ? item.getAttribute('data-id') : '';
                    const nodeLabel = isItem ? item.getAttribute('data-label') : '';
                    const nodeDate = isItem ? item.getAttribute('data-date') || '' : ''; // НОВОЕ: извлекаем дату

                    setVal('js-ctx-target-id', nodeId);
                    setVal('js-ctx-target-label', nodeLabel);
                    setVal('js-ctx-target-date', nodeDate); // НОВОЕ: передаем в Python
                    setVal('js-ctx-x', e.clientX.toString());
                    setVal('js-ctx-y', e.clientY.toString());
                    setVal('js-ctx-mode', isItem ? 'edit' : 'create');
                    
                    document.getElementById('js-ctx-trigger').click();
                }
            });

            document.addEventListener('click', function(e) {
                const menu = document.getElementById('context-menu');
                if (menu && !menu.contains(e.target)) {
                    document.getElementById('js-ctx-hide-trigger').click();
                }
            });
            window.dashCtxAttached = true;
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('js-ctx-trigger', 'className'),
    Input('js-ctx-trigger', 'id')
)

#JS для ии
clientside_callback(
    """
    function(id) {
        if (!window.dndAttached) {
            document.addEventListener('dragstart', function(e) {
                const item = e.target.closest('.draggable-file');
                if (item) {
                    const data = JSON.stringify({id: item.getAttribute('data-id'), label: item.getAttribute('data-label')});
                    e.dataTransfer.setData('text/plain', data);
                }
            });

            document.addEventListener('dragover', function(e) {
                const dropZone = document.getElementById('ai-drop-zone');
                if (dropZone && dropZone.contains(e.target)) {
                    e.preventDefault();
                    dropZone.style.borderColor = '#28a745';
                    dropZone.style.backgroundColor = '#f8fff8';
                }
            });

            document.addEventListener('dragleave', function(e) {
                const dropZone = document.getElementById('ai-drop-zone');
                if (dropZone && dropZone.contains(e.target)) {
                    dropZone.style.borderColor = '#ccc';
                    dropZone.style.backgroundColor = '#fff';
                }
            });

            document.addEventListener('drop', function(e) {
                const dropZone = document.getElementById('ai-drop-zone');
                if (dropZone && dropZone.contains(e.target)) {
                    e.preventDefault();
                    dropZone.style.borderColor = '#ccc';
                    dropZone.style.backgroundColor = '#fff';
                    const data = e.dataTransfer.getData('text/plain');
                    if (data) {
                        const el = document.getElementById('js-drop-file-id');
                        if (el) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(el, data);
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            document.getElementById('js-drop-trigger').click();
                        }
                    }
                }
            });
            window.dndAttached = true;
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('js-drop-trigger', 'className'),
    Input('js-drop-trigger', 'id')
)

# Обработка навигации
@callback(
    Output('current-graph-id', 'data', allow_duplicate=True),
    Output('nav-history', 'data', allow_duplicate=True),
    Output('selected-item-id', 'data', allow_duplicate=True),
    Output('folder-click-timestamp', 'data', allow_duplicate=True),
    Input('btn-back', 'n_clicks'),
    Input('btn-step-back', 'n_clicks'),
    Input({'type': 'folder-click', 'id': ALL}, 'n_clicks'),
    Input({'type': 'file-click', 'id': ALL}, 'n_clicks'),
    Input({'type': 'sidebar-folder', 'id': ALL}, 'n_clicks'),
    Input({'type': 'search-item', 'index': ALL}, 'n_clicks'),
    State('current-graph-id', 'data'),
    State('nav-history', 'data'),
    State('root-dept-id', 'data'),
    State('folder-click-timestamp', 'data'),
    prevent_initial_call=True
)
def handle_navigation(n_back, n_step, f_clicks, file_clicks, s_clicks, search_clicks, current_id, history, root_id, click_ts):
    tid = ctx.triggered_id
    now = time.time() * 1000 
    
    if not current_id: current_id = root_id
    if history is None: history = []

    if tid == 'btn-back':
        return root_id, [], None, {'id': None, 'ts': 0}

    if tid == 'btn-step-back':
        if history:
            prev_id = history.pop()
            return prev_id, history, None, {'id': None, 'ts': 0}
        return root_id, [], None, {'id': None, 'ts': 0}

    if isinstance(tid, dict) and tid['type'] == 'search-item':
        return current_id, history, tid['index'], {'id': None, 'ts': 0}

    if isinstance(tid, dict) and tid['type'] == 'file-click':
        return current_id, history, tid['id'], {'id': None, 'ts': 0}

    if isinstance(tid, dict) and tid['type'] == 'sidebar-folder':
        target_id = tid['id']
        if target_id == root_id:
            return root_id, [], None, {'id': None, 'ts': 0}
        if current_id not in history:
            history.append(current_id)
        return target_id, history, None, {'id': None, 'ts': 0}

    if isinstance(tid, dict) and tid['type'] == 'folder-click':
        item_id = tid['id']
        prev_id = click_ts.get('id')
        prev_time = click_ts.get('ts', 0)
        
        if item_id == prev_id and (now - prev_time) < 500:
            if current_id not in history:
                history.append(current_id)
            return item_id, history, None, {'id': None, 'ts': 0}
        
        return current_id, history, item_id, {'id': item_id, 'ts': now}

    return current_id, history, no_update, click_ts


#Левая панель
@callback(
    Output('left-sidebar-tree', 'children'),
    Input('current-graph-id', 'data'),
    Input('nav-history', 'data'),
    State('root-dept-id', 'data')
)
def render_sidebar_tree(current_id, history, root_id):
    if not history: history = []
    active_path = [root_id] + history + ([current_id] if current_id != root_id and current_id not in history else [])
    
    def build_tree_level(parent_id, depth=0):
        nodes = []
        data = load_all_data(parent_id)
        elements = data.get(parent_id, [])
        folders = [e['data'] for e in elements if e.get('data', {}).get('type') == 'subgraph']
        
        for folder in folders:
            f_id = folder['id']
            f_label = folder.get('label', f_id)
            is_active = (f_id == current_id)
            is_expanded = (f_id in active_path)
            
            arrow = "⌄ " if is_expanded else "› "
            icon = "📁 "
            
            style = {
                'padding': '4px 8px', 'cursor': 'pointer', 'margin-left': f'{depth * 15}px',
                'border-radius': '3px', 'display': 'flex', 'align-items': 'center',
                'background': '#e5f3ff' if is_active else 'transparent',
                'font-weight': 'bold' if is_active else 'normal', 'font-size': '14px'
            }

            nodes.append(html.Div([
                html.Span(arrow if any(load_all_data(f_id).get(f_id, [])) else "  ", style={'width': '15px', 'display': 'inline-block', 'color': '#808080'}),
                html.Span(icon, style={'margin-right': '5px', 'color': '#f2c94c'}),
                html.Span(f_label)
            ], id={'type': 'sidebar-folder', 'id': f_id}, style=style, className='sidebar-item'))

            if is_expanded:
                nodes.extend(build_tree_level(f_id, depth + 1))
                
        return nodes

    root_style = {
        'padding': '5px', 'cursor': 'pointer', 'font-weight': 'bold',
        'background': '#f0f0f0' if current_id == root_id else 'transparent'
    }
    
    root_node = html.Div([
        html.Span("⌄ ", style={'width': '15px', 'display': 'inline-block'}),
        html.Span("🖴 ", style={'margin-right': '5px'}),
        html.Span(f"Отдел: {root_id}")
    ], id={'type': 'sidebar-folder', 'id': root_id}, style=root_style)

    return [root_node] + build_tree_level(root_id)


# Управление видимостью меню
@callback(
    Output('context-menu', 'style'),
    Output('ctx-menu-create', 'style'),
    Output('ctx-menu-edit', 'style'),
    Output({'type': 'admin-input', 'index': 'edit-id'}, 'value'),
    Output({'type': 'admin-input', 'index': 'edit-label'}, 'value'),
    Output({'type': 'admin-input', 'index': 'edit-valid-until'}, 'value'), # НОВОЕ
    Output({'type': 'admin-input', 'index': 'new-id'}, 'value'),      
    Output({'type': 'admin-input', 'index': 'new-label'}, 'value'),
    Output({'type': 'admin-input', 'index': 'new-valid-until'}, 'value'), # НОВОЕ
    Output({'type': 'admin-input', 'index': 'is-folder'}, 'value'),
    Input('js-ctx-trigger', 'n_clicks'),
    Input('js-ctx-hide-trigger', 'n_clicks'),
    Input({'type': 'admin-btn', 'index': ALL}, 'n_clicks'),
    State('js-ctx-x', 'value'),
    State('js-ctx-y', 'value'),
    State('js-ctx-mode', 'value'),
    State('js-ctx-target-id', 'value'),
    State('js-ctx-target-label', 'value'),
    State('js-ctx-target-date', 'value'), # НОВОЕ
    prevent_initial_call=True
)
def handle_menu_state(trig, hide, admin_btns, x, y, mode, target_id, target_label, target_date):
    if getattr(current_user, 'role', 'user') != 'admin':
        return {'display': 'none'}, no_update, no_update, '', '', '', '', '', '', []

    trigger_id = ctx.triggered_id
    admin_btn_clicked = isinstance(trigger_id, dict) and trigger_id.get('type') == 'admin-btn'

    if trigger_id == 'js-ctx-hide-trigger' or admin_btn_clicked:
        return {'display': 'none'}, no_update, no_update, '', '', '', '', '', '', []

    style = {
        'display': 'block', 'position': 'fixed', 'left': f'{x}px', 'top': f'{y}px', 
        'background': 'white', 'zIndex': 1999, 'border': '1px solid #ccc', 
        'padding': '15px', 'boxShadow': '0 4px 10px rgba(0,0,0,0.2)', 'width': '200px', 'borderRadius': '6px'
    }

    if mode == 'edit':
        return style, {'display': 'none'}, {'display': 'block'}, target_id, target_label, target_date, '', '', '', []
    
    return style, {'display': 'block'}, {'display': 'none'}, "", "", "", "", "", "", []

# Обновление данных с учетом даты
@callback(
    Output('file-explorer-list', 'children'),
    Output('breadcrumbs', 'children'),
    Input('current-graph-id', 'data'),
    Input('selected-item-id', 'data'),
    Input({'type': 'admin-btn', 'index': ALL}, 'n_clicks'),
    State({'type': 'admin-input', 'index': ALL}, 'value'),
    State({'type': 'admin-input', 'index': ALL}, 'id'),
    State('js-ctx-target-id', 'value'),
    State('root-dept-id', 'data')
)
def update_explorer_full(current_id, selected_id, admin_clicks, all_values, all_ids, t_id, root_id):

    inputs = {item['index']: val for item, val in zip(all_ids, all_values)}
    
    n_id = inputs.get('new-id')
    n_lab = inputs.get('new-label')
    n_folder = inputs.get('is-folder')
    n_date = inputs.get('new-valid-until')
    
    e_id = inputs.get('edit-id')
    e_lab = inputs.get('edit-label')
    e_date = inputs.get('edit-valid-until')

    is_admin = getattr(current_user, 'role', 'user') == 'admin'
    all_data = load_all_data(current_id)
    if current_id not in all_data: all_data[current_id] = []

    tid = ctx.triggered_id
    action = tid.get('index') if isinstance(tid, dict) and tid.get('type') == 'admin-btn' else None

    # Обработка действий (Создание/Редактирование/Удаление)
    if is_admin and action:
        if action == 'create' and n_id:
            new_node = {'id': n_id, 'label': n_lab or n_id, 'type': 'subgraph' if n_folder else 'node'}
            if not n_folder and n_date:
                new_node['valid_until'] = n_date
            
            all_data[current_id].append({'data': new_node})
            log_action(root_id, n_lab or n_id, "Создание")
            
        elif action == 'save' and t_id:
            for el in all_data[current_id]:
                if el.get('data', {}).get('id') == t_id:
                    el['data']['id'], el['data']['label'] = e_id, e_lab
                    
                    if el['data'].get('type') != 'subgraph':
                        if e_date:
                            el['data']['valid_until'] = e_date
                        else:
                            el['data'].pop('valid_until', None)
                    log_action(root_id, e_lab, "Правка")
                    
        elif action == 'delete' and t_id:
            all_data[current_id] = [el for el in all_data[current_id] if el.get('data', {}).get('id') != t_id]
            log_action(root_id, t_id, "Удаление")
            
        save_all_data(all_data, current_id)

    items = []
    today = datetime.date.today()

    with open('1c_exmp.json', 'r', encoding='utf-8') as f:
        c_file = {fl['ИмяФайла']: fl['ПутьКФайлу'] for fl in json.load(f)}

    for el in all_data.get(current_id, []):
        d = el.get('data', {})
        if 'id' not in d: continue
        node_id, label, is_folder = d['id'], d.get('label', d['id']), d.get('type') == 'subgraph'
        valid_until_str = d.get('valid_until', '') 

        try:
            file_exists = os.path.exists(f"{c_file[node_id+'.txt']}")
        except:
            file_exists = False
        opacity = 1.0 if (is_folder or file_exists) else 0.4
        
        status_div = html.Div(style={'width': '30%', 'text-align': 'right'})
        
        # Статусы
        if not is_folder:
            if not file_exists:
                status_text = "Отсутствует"
                status_color = "#dc3545" 
            else:
                if not valid_until_str:
                    status_text = "Актуально" 
                    status_color = "#28a745" 
                else:
                    try:
                        valid_date = datetime.datetime.strptime(valid_until_str, "%Y-%m-%d").date()
                        delta = (valid_date - today).days

                        if delta < 0:
                            status_text = "Истёкший"
                            status_color = "#dc3545" 
                        elif delta <= 7:
                            status_text = "Истекает"
                            status_color = "#ffc107" 
                        else:
                            status_text = "Актуально"
                            status_color = "#28a745" 
                    except ValueError:
                        
                        status_text = "Актуально"
                        status_color = "#28a745"
            
            status_div.children = html.Span(
                status_text, 
                style={
                    'color': status_color, 
                    'border': f"1px solid {status_color}", 
                    'padding': '4px 10px', 
                    'borderRadius': '15px', 
                    'fontSize': '12px'
                }
            )
        
        # Рендер элемента
        item_class = 'explorer-item' + (' draggable-file' if not is_folder else '')
        
        items.append(html.Div([
            html.Div([
                html.Span("📂 " if is_folder else "📄 ", style={'marginRight': '10px', 'fontSize': '20px', 'color': '#f2c94c' if is_folder else '#2d8cf0'}), 
                html.Span(label, style={'fontSize': '15px', 'fontWeight': 'bold' if is_folder else 'normal'})
            ], style={'width': '70%', 'display': 'flex', 'alignItems': 'center'}), 
            status_div
        ], 
        id={'type': 'folder-click' if is_folder else 'file-click', 'id': node_id}, 
        className=item_class, 
        draggable='true' if not is_folder else 'false', # Разрешаем тащить только файлы
        **{'data-id': node_id, 'data-label': label, 'data-date': valid_until_str}, 
        style={'display': 'flex', 'padding': '12px 10px', 'borderBottom': '1px solid #f0f0f0', 'opacity': opacity, 'background': '#f1f8ff' if node_id == selected_id else 'transparent', 'cursor': 'pointer'}))
    
    if not items: items = [html.Div("Эта папка пуста. Нажмите правой кнопкой мыши для создания.", style={'padding': '20px', 'color': '#adb5bd', 'textAlign': 'center'})]
    return items, html.Span([html.Span("Проводник", style={'color': '#0074D9'}), f" > {current_id}"])


# Предпросмотр файлов
@callback(
    Output('node-info', 'children'),
    Input('selected-item-id', 'data'),
    State('current-graph-id', 'data'),
    prevent_initial_call=True
)
def preview_file(node_id, current_id):
    if not node_id: 
        return "Выберите файл для просмотра"
        
    
    is_folder = False
    valid_until_str = None
    
    if current_id:
        all_data = load_all_data(current_id)
        for el in all_data.get(current_id, []):
            d = el.get('data', {})
            if d.get('id') == node_id:
                is_folder = (d.get('type') == 'subgraph')
                valid_until_str = d.get('valid_until', '')
                break

    
    if is_folder:
        return "Выбрана папка. Откройте её двойным кликом для просмотра содержимого."

    
    if valid_until_str:
        try:
            
            date_obj = datetime.datetime.strptime(valid_until_str, "%Y-%m-%d").date()
            date_display = date_obj.strftime("%d.%m.%Y")
        except ValueError:
            date_display = valid_until_str
    else:
        date_display = "бессрочно"

    with open('1c_exmp.json', 'r', encoding='utf-8') as f:
        c_file = {fl['ИмяФайла']: fl['ПутьКФайлу'] for fl in json.load(f)}

    try:
        path = c_file[node_id+'.txt']
    except:
        path = ''
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            file_content = f.read(400)
            
        return html.Div([
            html.B(f"Файл: {path}"), 
            html.P(file_content, style={'font-size': '12px', 'white-space': 'pre-wrap', 'margin-top': '10px'}),
            html.Hr(style={'border-top': '1px dashed #ccc', 'margin': '15px 0 5px 0'}),
            html.Div([
                html.B("Срок действия: "),
                html.Span(date_display, style={'color': '#495057' if date_display == "бессрочно" else '#0074D9'})
            ], style={'font-size': '13px', 'background': '#f8f9fa', 'padding': '6px', 'border-radius': '4px'})
        ])
        
    return html.Div([
        html.Span(f"Текстовый документ {path} физически отсутствует на диске."),
        html.Hr(style={'border-top': '1px dashed #ccc', 'margin': '15px 0 5px 0'}),
        html.Div([
            html.B("Срок действия: "),
            html.Span(date_display)
        ], style={'font-size': '13px', 'background': '#f8f9fa', 'padding': '6px', 'border-radius': '4px'})
    ])


# Поиск
@callback(
    Output('suggestions-container', 'children'),
    Output('suggestions-container', 'style'),
    Input('doc-search', 'value')
)
def search_files(user_search):
    if not user_search or user_search.strip() == "":
        return [], {'display': 'none'}

    scan_results = []
    with os.scandir('.') as entries:
        for entry in entries:
            if len(scan_results) > 10: break
            if entry.is_file() and entry.name.endswith('.txt') and user_search.lower() in entry.name.lower():
                scan_results.append(entry.name)
            
    if not scan_results:
        return [], {'display': 'none'}

    results = [
        html.Div(
            el,
            id={'type': 'search-item', 'index': el.replace('.txt', '')},
            style={'padding': '10px', 'cursor': 'pointer', 'borderBottom': '1px solid #eee', 'background': 'white'},
            className='search_item'
        ) for el in scan_results
    ]
    
    visible_style = {
        'position': 'absolute', 'zIndex': '2000', 'backgroundColor': 'white', 'width': '100%', 
        'border': '1px solid #ddd', 'display': 'block', 'boxShadow': '0px 8px 12px rgba(0,0,0,0.1)', 
        'top': '100%', 'right': '0', 'marginTop': '4px', 'maxHeight': '200px', 'overflowY': 'auto'
    }

    return results, visible_style


# Обработка Drop-событий
@callback(
    Output('ai-context-store', 'data'),
    Output('ai-context-badges', 'children'),
    Input('js-drop-trigger', 'n_clicks'),
    Input({'type': 'remove-context-file', 'id': ALL}, 'n_clicks'),
    State('js-drop-file-id', 'value'),
    State('ai-context-store', 'data'),
    prevent_initial_call=True
)
def manage_ai_context(drop_click, remove_clicks, file_data, current_files):
    if current_files is None: current_files = []
    
    trigger = ctx.triggered_id
    
    
    if isinstance(trigger, dict) and trigger.get('type') == 'remove-context-file':
        remove_id = trigger.get('id')
        current_files = [f for f in current_files if f['id'] != remove_id]
        
    
    elif trigger == 'js-drop-trigger' and file_data:
        try:
            new_file = json.loads(file_data)
            
            if not any(f['id'] == new_file['id'] for f in current_files):
                current_files.append(new_file)
        except: pass

    
    badges = []
    for f in current_files:
        badges.append(html.Div([
            html.Span(f"📄 {f['label']}", style={'fontSize': '12px', 'marginRight': '5px'}),
            html.Span("×", id={'type': 'remove-context-file', 'id': f['id']}, 
                      style={'cursor': 'pointer', 'color': '#dc3545', 'fontWeight': 'bold', 'padding': '0 3px'})
        ], style={'background': '#e2e3e5', 'padding': '4px 8px', 'borderRadius': '12px', 'display': 'flex', 'alignItems': 'center', 'border': '1px solid #ced4da'}))
        
    return current_files, badges


# ИИ Помощник
@callback(
    Output('ai-out', 'children'),
    Input('btn-ai', 'n_clicks'),
    State('ai-query', 'value'),
    State('current-graph-id', 'data'),
    State('ai-context-store', 'data'), 
    prevent_initial_call=True
)
def ask_ai(n, query, current_id, context_files):
    if not query: return "Введите вопрос."
    elems = load_all_data(current_id).get(current_id, [])
    
    file_ids = [f['id'] for f in (context_files or [])]
    
    try:
        r = requests.post('http://127.0.0.1:8000/ask', json={
            'prompt': query, 
            'graph': elems,
            'context_files': file_ids 
        }, timeout=None)
        if r.status_code == 200:
            return r.json().get('response', 'Текст ответа пуст')
        else:
            error_detail = r.json().get('detail', 'Неизвестная ошибка')
            return f"Ошибка сервера: {error_detail}"
    except Exception as e:
        return f"Сервер ИИ недоступен: {str(e)}"
