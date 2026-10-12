@echo off
set "PATH=%LOCALAPPDATA%\agy\bin;%PATH%"
pushd "%~dp0..\.."
python "tools\inbox_runner\runner.py" >> "tools\inbox_runner\runner.log" 2>&1
popd
