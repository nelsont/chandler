@ECHO OFF
setlocal
cd ..\Chandler
set PATH=..\debug\bin
..\debug\bin\python_d Chandler.py $*
endlocal
