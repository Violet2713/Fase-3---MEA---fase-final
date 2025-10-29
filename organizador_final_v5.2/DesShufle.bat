@echo off
REM --- iniciar.bat (El "Botón de Encendido") ---

REM Mover la terminal a la carpeta donde este script .bat está guardado.
cd /d "%~dp0"

echo Iniciando el servidor del Organizador de Archivos en segundo plano...

REM CAMBIO IMPORTANTE:
REM Usar 'START /B' para lanzar el servidor de Python en segundo plano
REM (invisible) y permitir que esta ventana se cierre inmediatamente.
START "" /B py app.py

REM El script 'app.py' se encargará de abrir el navegador.
REM Esta ventana .bat se cerrará ahora.
exit
