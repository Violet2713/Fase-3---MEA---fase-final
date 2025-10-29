# --- analisis_de_datos.py ---
# Un script de administrador para analizar los datos de uso de "Desshufle"
#
# REQUISITO PREVIO:
# 1. Asegúrate de tener Pandas instalado:
#    pip install pandas
#
# 2. Para leer los perfiles de todos los usuarios, es mejor
#    ejecutar este script como Administrador.
# -----------------------------------------------------------------

import pandas as pd
import os
from pathlib import Path
import warnings

# --- Configuración de Rutas (Debe coincidir con app.py) ---
# 1. Ubicación del Log de Administrador
ADMIN_LOG_DIR = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / "OrganizadorMaterias"
ADMIN_LOG_CSV = ADMIN_LOG_DIR / "admin_log.csv"

# 2. Ubicación de los Perfiles de Usuario
# Debemos escanear TODOS los directorios de usuario
USERS_DIR = Path.home().parent  # Esto usualmente nos lleva a C:\Users
APP_DATA_SUBPATH = "AppData/Roaming/OrganizadorMaterias/perfiles.csv"

# Ignorar advertencias comunes de Pandas
warnings.simplefilter(action='ignore', category=FutureWarning)

def cargar_log_admin() -> pd.DataFrame:
    """Carga el log principal de transacciones (admin_log.csv)"""
    print(f"Cargando log de administrador desde: {ADMIN_LOG_CSV}")
    if not ADMIN_LOG_CSV.exists():
        print(f"ERROR: No se encontró el archivo de log. ¿Se ha ejecutado la app al menos una vez?")
        return pd.DataFrame()

    try:
        df_log = pd.read_csv(ADMIN_LOG_CSV)
        
        # --- Limpieza de Datos Esencial (ETL) ---
        # Convertir timestamps a objetos de fecha para análisis de series de tiempo
        df_log['log_timestamp'] = pd.to_datetime(df_log['log_timestamp'])
        
        # Convertir bytes a numérico para poder sumar
        df_log['file_size_bytes'] = pd.to_numeric(df_log['file_size_bytes'], errors='coerce').fillna(0)
        
        # Añadir columnas útiles
        df_log['log_hora'] = df_log['log_timestamp'].dt.hour
        df_log['log_dia_semana'] = df_log['log_timestamp'].dt.day_name()
        df_log['gb_organizados'] = df_log['file_size_bytes'] / (1024**3)
        
        print(f"Log de administrador cargado. {len(df_log)} acciones registradas.")
        return df_log
    
    except Exception as e:
        print(f"Error al leer {ADMIN_LOG_CSV}: {e}")
        return pd.DataFrame()

def cargar_todos_los_perfiles() -> pd.DataFrame:
    r"""
    Escanea C:\Users para encontrar todos los perfiles.csv de todos los usuarios
    y los consolida en una sola tabla.
    """
    print(f"\nBuscando perfiles de usuario en: {USERS_DIR}")
    perfiles_encontrados = []
    
    # Iterar sobre cada carpeta en C:\Users
    for user_dir in USERS_DIR.iterdir():
        if not user_dir.is_dir():
            continue
            
        perfil_path = user_dir / APP_DATA_SUBPATH
        
        if perfil_path.exists():
            try:
                # Leer el CSV de este usuario
                df_perfil_usuario = pd.read_csv(perfil_path)
                # Añadir una columna para saber a quién pertenece este perfil
                df_perfil_usuario['propietario_perfil'] = user_dir.name
                perfiles_encontrados.append(df_perfil_usuario)
                print(f"  > Perfil encontrado para el usuario: {user_dir.name}")
            except Exception as e:
                print(f"  > Error al leer perfil {perfil_path}: {e}")
                
    if not perfiles_encontrados:
        print("No se encontró ningún archivo de perfil.")
        return pd.DataFrame()

    # Consolidar todos los dataframes de perfiles en uno solo
    df_perfiles_total = pd.concat(perfiles_encontrados, ignore_index=True)
    
    # --- Limpieza de Datos Esencial (ETL) ---
    df_perfiles_total['last_used_timestamp'] = pd.to_datetime(df_perfiles_total['last_used_timestamp'])
    df_perfiles_total['created_timestamp'] = pd.to_datetime(df_perfiles_total['created_timestamp'])
    
    print(f"Perfiles consolidados. {len(df_perfiles_total)} perfiles encontrados en total.")
    return df_perfiles_total

def ejecutar_analisis(df_log, df_perfiles):
    """Ejecuta y muestra los KPIs principales"""
    
    if df_log.empty:
        print("\nNo hay datos de log para analizar.")
        return

    # --- Análisis del Log (KPIs de Actividad) ---
    print("\n--- ANÁLISIS DE ACTIVIDAD (admin_log.csv) ---")
    
    total_acciones = len(df_log)
    total_gb = df_log['gb_organizados'].sum()
    usuarios_activos = df_log['username'].nunique()
    
    print(f"\nKPIs Generales:")
    print(f"  - Total de acciones (archivos procesados): {total_acciones}")
    print(f"  - Total de Gigabytes (GB) organizados:   {total_gb:.4f} GB")
    print(f"  - Usuarios únicos activos:                {usuarios_activos}")

    print(f"\nActividad por Usuario (TOP 5):")
    print(df_log.groupby('username')['gb_organizados'].sum().nlargest(5).to_markdown(floatfmt=".4f"))

    print(f"\nMaterias Más Organizadas (TOP 10):")
    print(df_log['subject_assigned'].value_counts().nlargest(10).to_markdown(header=["Materia", "Conteos"]))

    print(f"\nResultados de Acciones (Status):")
    print(df_log['status'].value_counts().to_markdown(header=["Status", "Conteos"]))

    print(f"\nHoras Pico de Uso (0-23h):")
    print(df_log['log_hora'].value_counts().sort_index().to_markdown(header=["Hora", "Conteos"]))

    # --- Análisis Combinado (Merge) ---
    if df_perfiles.empty:
        print("\nNo se encontraron perfiles, omitiendo análisis combinado.")
        return
        
    print("\n--- ANÁLISIS COMBINADO (Log + Perfiles) ---")
    
    # ¡La magia del merge!
    df_combinado = pd.merge(df_log, df_perfiles, on='profile_id', how='left', suffixes=('_log', '_perfil'))
    
    print(f"\nActividad por Nombre de Perfil (TOP 5):")
    # Usamos profile_name de la tabla de perfiles
    print(df_combinado.groupby('profile_name')['gb_organizados'].sum().nlargest(5).to_markdown(floatfmt=".4f"))
    
    print(f"\nPreferencia de Manejo de 'Otros':")
    # Usamos others_handling de la tabla de perfiles
    print(df_combinado.groupby('others_handling')['gb_organizados'].sum().to_markdown(floatfmt=".4f"))
    
    print(f"\nActividad por Propietario de Perfil (TOP 5):")
    # Usamos propietario_perfil que añadimos al cargar
    print(df_combinado.groupby('propietario_perfil')['gb_organizados'].sum().nlargest(5).to_markdown(floatfmt=".4f"))


# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    print("=============================================")
    print("  Reporte de Análisis de 'Desshufle' v1.0  ")
    print("=============================================")
    
    # 1. Cargar los dos datasets
    df_log = cargar_log_admin()
    df_perfiles = cargar_todos_los_perfiles()
    
    # 2. Ejecutar el análisis
    ejecutar_analisis(df_log, df_perfiles)
    
    print("\n--- Fin del Análisis ---")
    