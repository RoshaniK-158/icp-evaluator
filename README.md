# AI ICP Fit Evaluator

A complete Python application that evaluates LinkedIn profiles against your Ideal Customer Profile (ICP) criteria using AI.

## 🏗️ Architecture

This application uses a **secure two-tier architecture**:

- **Frontend**: Streamlit web interface for user interactions
- **Backend**: FastAPI server that securely handles OpenAI API calls
- **Security**: API keys are kept on the backend server, never exposed to the frontend

## Features

- **Streamlit Web Interface**: User-friendly interface for uploading ICP configurations and entering profile data
- **Secure API Backend**: Custom FastAPI backend that handles OpenAI API calls securely
- **OpenAI Integration**: Uses GPT-3.5-turbo for intelligent profile evaluation  
- **Modular Design**: Separated frontend, backend, and API logic for security and maintainability
- **Error Handling**: Robust error handling for API calls and malformed responses
- **Visual Results**: Clear "Fit"/"Not Fit" results with detailed reasoning

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set OpenAI API Key

**IMPORTANT**: Never commit your API key to version control!

**Option A: Environment Variable (Recommended)**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

**Option B: Create .env file**
```bash
# Copy the template and edit it
copy .env.template .env
# Edit .env file and add your API key
```

### 3. Start the Backend API Server

**Open a new terminal and run:**
```bash
python api_backend.py
```

The API server will start at `http://127.0.0.1:8000`

### 4. Start the Frontend Application

**In another terminal, run:**
```bash
streamlit run app.py
```

The Streamlit app will open at `http://localhost:8501`

## Usage

1. **Upload ICP Configuration**: Upload a JSON file containing your ICP focus and rules
2. **Enter Profile Text**: Paste the LinkedIn "About Section" text into the text area
3. **Run Evaluation**: Click the "Run AI Evaluation" button to get results
4. **View Results**: See the "Fit"/"Not Fit" decision with detailed reasoning

## ICP Configuration Format

Your JSON configuration file should follow this structure:

```json
{
  "icp_focus": "Enterprise SaaS Sales Director",
  "rules": [
    "Must be a Director-level or higher.",
    "Must explicitly mention experience selling software or SaaS products.",
    "Must mention keywords like 'quota', 'pipeline management', or 'global teams'."
  ]
}
```

A sample configuration file (`sample_icp_config.json`) is included for reference.

## File Structure

- `app.py` - Streamlit frontend application
- `api_backend.py` - FastAPI backend server that handles OpenAI calls
- `requirements.txt` - Python dependencies
- `sample_icp_config.json` - Example ICP configuration
- `.env.template` - Template for environment variables
- `.gitignore` - Prevents sensitive files from being committed
- `README.md` - This documentation

## Key Functions

### Backend (`api_backend.py`)
- **`construct_prompt()`** - Dynamically builds AI prompts using ICP rules
- **`/evaluate` endpoint** - Handles profile evaluation requests securely
- **Health check endpoints** - Monitor API status

### Frontend (`app.py`)
- **`evaluate_profile()`** - Calls the backend API instead of OpenAI directly
- **Streamlit UI components** - File upload, text input, results display

## Security Features

🔒 **API Key Protection**: OpenAI API key is kept on the backend server only
🚫 **No Frontend Exposure**: Frontend never sees or handles the API key
📝 **Git Protection**: `.gitignore` prevents accidental key commits
🔄 **Request Validation**: Backend validates all requests before calling OpenAI
⚡ **Error Handling**: Graceful handling of API failures and network issues

## Error Handling

The application includes comprehensive error handling for:
- Missing OpenAI API key on backend
- Backend server connection issues
- Invalid JSON configuration files
- API call failures and timeouts
- Malformed AI responses
- Missing input validation

## Requirements

- Python 3.7+
- Streamlit 1.28.0+
- FastAPI 0.104.0+
- OpenAI 0.28.0+
- Valid OpenAI API key

## Notes

- **Security First**: API key is never exposed to the frontend
- **Two-Server Architecture**: Frontend (port 8501) + Backend (port 8000)
- **Production Ready**: Proper error handling and request validation
- The backend uses the `gpt-3.5-turbo` model for cost-effectiveness
- All AI evaluation logic is separated in the secure backend
- The prompt enforces strict output formatting for reliable parsing