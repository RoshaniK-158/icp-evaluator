@echo off
echo Starting ICP Evaluator Application...
echo.

echo Checking if API key is set...
if "%OPENAI_API_KEY%"=="" (
    echo ERROR: OPENAI_API_KEY environment variable is not set!
    echo Please set it using: set OPENAI_API_KEY=your-api-key-here
    pause
    exit /b 1
)

echo API key is configured ✓
echo.

echo Starting Backend API Server...
start "ICP Backend API" cmd /k "python api_backend.py"

echo Waiting for backend to start...
timeout /t 3 /nobreak >nul

echo Starting Frontend Streamlit App...
start "ICP Frontend" cmd /k "streamlit run app.py"

echo.
echo ✅ Both servers are starting!
echo 📊 Frontend: http://localhost:8501
echo 🔧 Backend API: http://localhost:8000
echo.
echo Press any key to close this window...
pause >nul