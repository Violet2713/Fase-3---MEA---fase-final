# --- app.py (El "Motor" y "Cocina") ---
# 1. Copiamos y pegamos todo el código de v5.2
# 2. Añadimos Flask, CORS, y webbrowser
# 3. Quitamos la función main() y los 'input()'
# 4. Añadimos las "puertas" (rutas API) para que el HTML se comunique.

import os
import shutil
from pathlib import Path
import time
import unicodedata
import re
import csv
from datetime import datetime
import getpass
import json # Necesario para enviar datos al HTML
import webbrowser # Para abrir el navegador
import threading # Para abrir el navegador después de que inicie Flask

# --- Importaciones de Flask ---
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# --- Configuración de Flask ---
app = Flask(__name__)
# Permitir que nuestro HTML (que corre en un "dominio" diferente)
# hable con nuestro servidor Python (que corre en otro).
CORS(app) 

# --- Constantes Globales (Las mismas de v5.2) ---
APP_DATA_DIR = Path(os.environ.get('APPDATA', Path.home())) / "OrganizadorMaterias"
PERFILES_CSV = APP_DATA_DIR / "perfiles.csv"
ADMIN_LOG_DIR = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / "OrganizadorMaterias"
ADMIN_LOG_CSV = ADMIN_LOG_DIR / "admin_log.csv"
MATERIAS_SEPARATOR = "|"
PROFILE_FIELDNAMES = [
    'id_perfil', 'nombre_visible', 'lista_materias_pipe', 'ruta_origen', 
    'ruta_destino', 'nombre_carpeta_principal', 'ultimo_uso_timestamp', 
    'creado_en_timestamp', 'contador_archivos_movidos', 'manejo_otros'
]
ADMIN_LOG_FIELDNAMES = ['timestamp', 'username', 'action']

# --- Funciones de Ayuda (Imprimir con color en la TERMINAL) ---
# Estas son útiles para *nosotros* (desarrolladores) para ver qué pasa en el servidor
def print_error(message: str):
    print(f"\n\033[91m [X] ERROR: {message}\033[0m")

def print_warning(message: str):
    print(f"\n\033[93m [!] AVISO: {message}\033[0m")

def print_success(message: str):
    print(f"\n\033[92m [✓] ÉXITO: {message}\033[0m")

# --- Funciones de Log de Administrador (Sin cambios de v5.2) ---
def setup_admin_log():
    try:
        os.makedirs(ADMIN_LOG_DIR, exist_ok=True)
        if not ADMIN_LOG_CSV.exists():
            with open(ADMIN_LOG_CSV, mode='w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=ADMIN_LOG_FIELDNAMES)
                writer.writeheader()
            print_success(f"Log de Administrador creado en: {ADMIN_LOG_CSV}")
    except PermissionError:
        print_error("¡Fallo de permisos al crear el Log de Administrador!")
        print_warning("Por favor, ejecuta este script UNA VEZ 'Como Administrador' para habilitar el log.")
    except Exception as e:
        print_error(f"Error desconocido al crear el log: {e}")

def log_admin_action(action: str):
    try:
        username = getpass.getuser()
        timestamp = datetime.now().isoformat()
        with open(ADMIN_LOG_CSV, mode='a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=ADMIN_LOG_FIELDNAMES)
            writer.writerow({
                'timestamp': timestamp,
                'username': username,
                'action': action
            })
    except (IOError, PermissionError):
        pass 
    except Exception as e:
        print_warning(f"No se pudo escribir en el log de admin: {e}")

# --- Funciones de Lógica de Archivos (Sin cambios de v5.2) ---
def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    )
    text = re.sub(r'[^a-z0-9\._]+', '_', text).strip('_')
    return text

def handle_duplicates(destination_path: Path) -> Path:
    if not destination_path.exists():
        return destination_path
    parent = destination_path.parent
    base_name = destination_path.stem if destination_path.is_file() else destination_path.name
    extension = destination_path.suffix if destination_path.is_file() else ""
    counter = 1
    while True:
        clean_base_name = re.sub(r' \(\d+\)$', '', base_name)
        new_name = f"{clean_base_name} ({counter}){extension}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1

def sanitize_folder_name(name: str) -> str:
    name = name.strip()
    if not name:
        return "Carpeta_Sin_Nombre"
    illegal_chars = r'[\\/:*?"<>|]'
    sanitized_name = re.sub(illegal_chars, '', name)
    sanitized_name = re.sub(r'[\s_]+', '_', sanitized_name).strip('_')
    return sanitized_name

def is_valid_name(name: str) -> bool:
    if not name:
        return False
    return any(c.isalpha() for c in name)

# --- Funciones de Gestión de Perfiles (Modificadas para Flask) ---
# Ya no imprimen tanto, solo devuelven los datos.

def load_profiles() -> dict:
    """Carga perfiles desde AppData. Devuelve un diccionario de perfiles."""
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
    except Exception as e:
        print_error(f"No se pudo crear el directorio de perfiles en AppData: {e}")
        return {}
        
    if not Path(PERFILES_CSV).exists():
        return {} 

    profiles_data = {}
    try:
        with open(PERFILES_CSV, mode='r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not set(PROFILE_FIELDNAMES).issubset(set(reader.fieldnames)):
                base_fieldnames_ok = set(PROFILE_FIELDNAMES) - {'manejo_otros'}
                if not set(base_fieldnames_ok).issubset(set(reader.fieldnames)):
                    print_error(f"El archivo '{PERFILES_CSV}' está corrupto.")
                    return {} 
                
            for row in reader:
                try:
                    if 'id_perfil' not in row or not row['id_perfil']:
                        continue
                    row['contador_archivos_movidos'] = int(row.get('contador_archivos_movidos', 0))
                    row['manejo_otros'] = row.get('manejo_otros', 'mover') 
                    profiles_data[row['id_perfil']] = row
                except (ValueError, TypeError):
                    pass
        return profiles_data
    except Exception as e:
        print_error(f"No se pudo leer el archivo '{PERFILES_CSV}': {e}")
        return {}

def save_profiles(profiles_data: dict):
    """Guarda el diccionario de perfiles en AppData."""
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        with open(PERFILES_CSV, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=PROFILE_FIELDNAMES)
            writer.writeheader()
            for profile in profiles_data.values():
                writer.writerow(profile)
        print_success("Perfiles guardados.")
        return True
    except Exception as e:
        print_error(f"No se pudo guardar el archivo '{PERFILES_CSV}': {e}")
        return False

def generate_profile_id() -> str:
    return f"perfil_{int(time.time())}"

# --- Lógica de Organización (Modificada para devolver reporte) ---
# Esta es la lógica v5.2, pero 'print' se reemplaza por 'log_messages'
# para poder enviarlos al HTML en el futuro (por ahora solo devuelve el reporte final).

def organize_by_subject(source_dir: Path, dest_dir: Path, subjects: list[str], manage_others: str):
    """Analiza, clasifica y mueve los archivos. Devuelve un reporte."""
    report = {"movidos": 0, "omitidos": 0, "renombrados": 0, "logs": []}
    log_messages = report["logs"]

    log_messages.append(f"Iniciando organización...")
    log_messages.append(f"Buscando en: {source_dir}")

    other_dir = None
    if manage_others == 'mover':
        other_dir = dest_dir / "Otros"
        os.makedirs(other_dir, exist_ok=True)
    
    for subject in subjects:
        subject_folder_name = sanitize_folder_name(subject)
        subject_path = dest_dir / subject_folder_name
        os.makedirs(subject_path, exist_ok=True)

    try:
        items_to_process = list(source_dir.iterdir())
        if not items_to_process:
            log_messages.append("AVISO: La carpeta de origen está vacía.")
            return report
            
        log_messages.append(f"Se encontraron {len(items_to_process)} items para analizar...")
        
        for item in items_to_process:
            if (item.name == "app.py" or # Actualizado de "organizador_archivos.py"
                item.name == PERFILES_CSV.name or 
                item.name == ADMIN_LOG_CSV.name or
                item.is_symlink() or 
                item.suffix.lower() == '.lnk' or 
                item.name.startswith("~$")):
                log_messages.append(f"Omitiendo (sistema/temporal): {item.name}")
                report["omitidos"] += 1
                continue
            
            if not item.is_file() and not item.is_dir():
                log_messages.append(f"Omitiendo (tipo desconocido): {item.name}")
                report["omitidos"] += 1
                continue

            item_name_normalized = normalize_text(item.name)
            destination_folder = None
            found_match = False

            for subject in subjects:
                if subject in item_name_normalized:
                    subject_folder_name = sanitize_folder_name(subject)
                    destination_folder = dest_dir / subject_folder_name
                    found_match = True
                    break 

            if not found_match:
                if manage_others == 'mover':
                    destination_folder = other_dir
                else: 
                    log_messages.append(f"Omitiendo (no coincide): {item.name}")
                    report["omitidos"] += 1
                    continue

            try:
                final_destination = destination_folder / item.name
                final_destination = handle_duplicates(final_destination)
                shutil.move(str(item), str(final_destination))
                
                if final_destination.name != item.name:
                    log_messages.append(f"Renombrado: '{item.name}' -> '{final_destination.name}'")
                    report["renombrados"] += 1
                else:
                    log_messages.append(f"Movido: '{item.name}' -> (en {destination_folder.name})")
                report["movidos"] += 1

            except (IOError, OSError, shutil.Error) as move_error:
                log_messages.append(f"ERROR al mover '{item.name}': {move_error}")
                report["omitidos"] += 1
            
    except Exception as e:
        log_messages.append(f"ERROR CRÍTICO al procesar items: {e}")
        return report

    log_messages.append("¡Organización Completada!")
    return report

# --- (NUEVO) Puertas de la "Cocina" (Rutas de la API de Flask) ---

@app.route('/')
def home():
    """Sirve el archivo HTML principal."""
    # Flask buscará 'index.html' en la carpeta 'templates'
    return render_template('index.html')

@app.route('/api/get-profiles', methods=['GET'])
def api_get_profiles():
    """Envía todos los perfiles guardados al HTML."""
    print("Petición recibida: /api/get-profiles")
    profiles = load_profiles()
    # Convertimos el diccionario a una lista para que sea más fácil de usar en JS
    return jsonify(list(profiles.values()))

@app.route('/api/get-default-folders', methods=['GET'])
def api_get_default_folders():
    """
    Intenta encontrar las rutas de Descargas, Escritorio y Documentos.
    Esto reemplaza la función interactiva 'get_directory' para el HTML.
    """
    print("Petición recibida: /api/get-default-folders")
    home = Path.home()
    locations = {
        "Descargas": [
            home / "OneDrive" / "Descargas", home / "Descargas",
            home / "OneDrive" / "Downloads", home / "Downloads"
        ],
        "Escritorio": [
            home / "OneDrive" / "Escritorio", home / "Escritorio",
            home / "OneDrive" / "Desktop", home / "Desktop"
        ],
        "Documentos": [
            home / "OneDrive" / "Documentos", home / "Documentos",
            home / "OneDrive" / "Documents", home / "Documents"
        ]
    }
    
    found_paths = {}
    for name, paths in locations.items():
        for path in paths:
            if path.exists() and path.is_dir():
                found_paths[name] = str(path) # Guardar como string
                break # Encontramos una, pasar a la siguiente
    
    return jsonify(found_paths)

@app.route('/api/create-profile', methods=['POST'])
def api_create_profile():
    """Recibe datos de un formulario HTML y crea un nuevo perfil."""
    print("Petición recibida: /api/create-profile")
    data = request.json
    
    # --- Validaciones (Simplificadas para la API) ---
    if not data or not data.get('nombre_visible') or not data.get('lista_materias'):
        return jsonify({"success": False, "error": "Datos incompletos."}), 400
    
    if not is_valid_name(data['nombre_visible']):
        return jsonify({"success": False, "error": "El nombre del perfil debe tener letras."}), 400

    profiles_data = load_profiles()
    if any(p['nombre_visible'].lower() == data['nombre_visible'].lower() for p in profiles_data.values()):
        return jsonify({"success": False, "error": "Ese nombre de perfil ya existe."}), 400

    # Procesar materias
    subjects_list = []
    for subject in data['lista_materias'].split(","):
        subject_clean = subject.strip()
        if is_valid_name(subject_clean):
            subjects_list.append(normalize_text(subject_clean))
    if not subjects_list:
        return jsonify({"success": False, "error": "La lista de materias no es válida."}), 400
    
    lista_materias_pipe = MATERIAS_SEPARATOR.join(sorted(list(set(subjects_list))))

    # --- Ensamblar el perfil ---
    new_id = generate_profile_id()
    now_iso = datetime.now().isoformat()
    
    new_profile = {
        'id_perfil': new_id,
        'nombre_visible': data['nombre_visible'],
        'lista_materias_pipe': lista_materias_pipe,
        'ruta_origen': data['ruta_origen'], # El HTML nos dará el string de la ruta
        'ruta_destino': data['ruta_destino'],
        'nombre_carpeta_principal': sanitize_folder_name(data['nombre_carpeta_principal']),
        'ultimo_uso_timestamp': now_iso,
        'creado_en_timestamp': now_iso,
        'contador_archivos_movidos': 0,
        'manejo_otros': data.get('manejo_otros', 'mover')
    }
    
    profiles_data[new_id] = new_profile
    save_profiles(profiles_data)
    log_admin_action("PROFILE_CREATED_API")
    
    return jsonify({"success": True, "new_profile": new_profile})


@app.route('/api/run-profile', methods=['POST'])
def api_run_profile():
    """Recibe un ID de perfil y ejecuta la organización."""
    data = request.json
    profile_id = data.get('id')
    print(f"Petición recibida: /api/run-profile (ID: {profile_id})")

    profiles_data = load_profiles()
    
    if not profile_id or profile_id not in profiles_data:
        return jsonify({"success": False, "error": "Perfil no encontrado."}), 404
        
    try:
        profile = profiles_data[profile_id]
        source_dir = Path(profile['ruta_origen'])
        dest_parent_dir = Path(profile['ruta_destino'])

        if not source_dir.exists():
            return jsonify({"success": False, "error": f"La carpeta de ORIGEN no existe: {source_dir}"}), 400
        if not dest_parent_dir.exists():
            return jsonify({"success": False, "error": f"La carpeta de DESTINO no existe: {dest_parent_dir}"}), 400

        main_folder_name = profile['nombre_carpeta_principal']
        subjects = profile['lista_materias_pipe'].split(MATERIAS_SEPARATOR)
        manage_others = profile.get('manejo_otros', 'mover')
        final_dest_dir = dest_parent_dir / main_folder_name

    except Exception as e:
        return jsonify({"success": False, "error": f"Error al cargar perfil: {e}"}), 500

    # --- Ejecución ---
    log_admin_action("ORGANIZATION_RUN_API")
    start_time = time.time()
    
    report = organize_by_subject(
        source_dir, 
        final_dest_dir, 
        subjects, 
        manage_others=manage_others
    )
    
    end_time = time.time()
    total_time = f"{end_time - start_time:.2f}"
    
    # --- Actualizar Perfil y Guardar ---
    try:
        profile['ultimo_uso_timestamp'] = datetime.now().isoformat()
        total_moved = report.get('movidos', 0) + report.get('renombrados', 0)
        if total_moved > 0:
            profile['contador_archivos_movidos'] += total_moved
        save_profiles(profiles_data) # Guardar todos los perfiles actualizados
    except Exception as e:
        print_error(f"Error al actualizar y guardar el perfil: {e}")

    return jsonify({
        "success": True, 
        "report": report, 
        "total_time": total_time,
        "updated_profile": profile
    })


# --- (NUEVO) Función para abrir el navegador ---
def open_browser():
    """Abre el navegador en nuestra app después de 1 segundo."""
    def _open():
        time.sleep(1)
        webbrowser.open_new('http://127.0.0.1:5000/')
    # Iniciar en un hilo separado para no bloquear el servidor
    threading.Thread(target=_open).start()

# --- (NUEVO) Punto de Entrada de Flask ---
if __name__ == "__main__":
    print("Iniciando Organizador de Archivos (v6.0 - Web)...")
    # 1. Configurar log de admin
    setup_admin_log()
    # 2. Registrar inicio
    log_admin_action("APP_START")
    # 3. Abrir el navegador
    open_browser()
    # 4. Iniciar el servidor web
    # (debug=False es para producción, debug=True es para desarrollar)
    app.run(host='127.0.0.1', port=5000, debug=False)
