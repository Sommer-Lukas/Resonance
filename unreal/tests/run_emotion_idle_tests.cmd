@echo off
setlocal
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -all -latest -products * -property installationPath`) do set "RESONANCE_VS=%%i"
if not defined RESONANCE_VS exit /b 1
call "%RESONANCE_VS%\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64 >nul
if errorlevel 1 exit /b 1
if not exist "%~dp0..\ResonanceVR\Saved\EmotionTests" mkdir "%~dp0..\ResonanceVR\Saved\EmotionTests"
cl /nologo /EHsc /std:c++17 /W4 /WX /I"%~dp0..\ResonanceVR\Plugins\ResonanceFace\Source\ResonanceFace\Public" "%~dp0emotion_idle_test.cpp" /Fe:"%~dp0..\ResonanceVR\Saved\EmotionTests\emotion_idle_test.exe" /Fo:"%~dp0..\ResonanceVR\Saved\EmotionTests\emotion_idle_test.obj"
if errorlevel 1 exit /b 1
"%~dp0..\ResonanceVR\Saved\EmotionTests\emotion_idle_test.exe"
exit /b %errorlevel%
