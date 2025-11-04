"""
Custom API Backend for ICP Evaluator
This backend handles OpenAI API calls securely without exposing the API key to the frontend.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import os
from typing import Dict, Any
import uvicorn
from contextlib import asynccontextmanager

# Global variable to store the OpenAI client
openai_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize OpenAI client on startup"""
    global openai_client
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not found!")
        print("💡 Please set it using: $env:OPENAI_API_KEY='your-key-here'")
        raise RuntimeError("OPENAI_API_KEY environment variable not found!")
    
    # Initialize OpenAI client with the new API
    openai_client = openai.OpenAI(api_key=api_key)
    print("✅ OpenAI API initialized successfully")
    yield
    # Cleanup code would go here if needed

app = FastAPI(title="ICP Evaluator API", version="1.0.0", lifespan=lifespan)

# Add CORS middleware to allow Streamlit frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ICPEvaluationRequest(BaseModel):
    profile_text: str
    icp_rules_json: Dict[str, Any]

class ICPEvaluationResponse(BaseModel):
    decision: str
    reasoning: str
    success: bool
    error_message: str = None

def construct_prompt(icp_rules_json: dict, profile_text: str) -> str:
    """
    Dynamically construct the AI's System Prompt using the ICP rules and profile text.
    """
    icp_focus = icp_rules_json.get("icp_focus", "")
    rules = icp_rules_json.get("rules", [])
    
    rules_text = "\n".join([f"- {rule}" for rule in rules])
    
    prompt = f"""You are an expert ICP (Ideal Customer Profile) evaluator. Your task is to determine if a LinkedIn profile matches the specified ICP criteria.

ICP FOCUS: {icp_focus}

ICP RULES:
{rules_text}

PROFILE TEXT TO EVALUATE:
{profile_text}

INSTRUCTIONS:
1. Carefully analyze the profile text against each ICP rule
2. Determine if the profile is a "Fit" or "Not Fit" based on ALL criteria
3. Provide a 2-3 sentence justification for your decision

REQUIRED OUTPUT FORMAT:
You must respond in this exact format:
[Fit OR Not Fit]; [2-3 sentence reasoning explaining your decision]

Example responses:
- "Fit; The candidate is a VP of Sales with 8+ years of SaaS experience and explicitly mentions managing global sales teams and exceeding quotas. They demonstrate clear leadership in enterprise software sales."
- "Not Fit; While the candidate has sales experience, they are only at Manager level rather than Director+ and their background is primarily in physical products rather than SaaS. They do not mention quota achievement or pipeline management."

Now evaluate the profile and respond in the required format:"""
    
    return prompt

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "ICP Evaluator API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    api_key_present = bool(os.getenv('OPENAI_API_KEY'))
    return {
        "status": "healthy",
        "openai_api_key_configured": api_key_present,
        "version": "1.0.0"
    }

@app.post("/evaluate", response_model=ICPEvaluationResponse)
async def evaluate_profile(request: ICPEvaluationRequest):
    """
    Evaluate a LinkedIn profile against ICP criteria using OpenAI.
    """
    try:
        # Validate inputs
        if not request.profile_text.strip():
            raise HTTPException(status_code=400, detail="Profile text cannot be empty")
        
        if not request.icp_rules_json:
            raise HTTPException(status_code=400, detail="ICP rules cannot be empty")
        
        # Construct the prompt
        prompt = construct_prompt(request.icp_rules_json, request.profile_text)
        
        # Make the OpenAI API call using the new client
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        # Extract the response content
        ai_response = response.choices[0].message.content.strip()
        
        # Parse the response to extract decision and reasoning
        if ';' in ai_response:
            parts = ai_response.split(';', 1)
            decision = parts[0].strip()
            reasoning = parts[1].strip()
            
            # Validate the decision
            if decision in ['Fit', 'Not Fit']:
                return ICPEvaluationResponse(
                    decision=decision,
                    reasoning=reasoning,
                    success=True
                )
            else:
                return ICPEvaluationResponse(
                    decision="Error",
                    reasoning=f"Invalid decision format received: {decision}. Expected 'Fit' or 'Not Fit'.",
                    success=False,
                    error_message="Invalid AI response format"
                )
        else:
            return ICPEvaluationResponse(
                decision="Error",
                reasoning=f"Could not parse AI response. Expected format: 'Decision; Reasoning'. Received: {ai_response}",
                success=False,
                error_message="Failed to parse AI response"
            )
            
    except openai.OpenAIError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"OpenAI API error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )

if __name__ == "__main__":
    print("🚀 Starting ICP Evaluator API Backend...")
    print("📝 Make sure OPENAI_API_KEY environment variable is set")
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000,
        log_level="info"
    )