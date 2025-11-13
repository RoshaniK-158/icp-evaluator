import streamlit as st
import json
import openai
import os
from typing import Tuple, Optional
import PyPDF2
import pdfplumber
import io
import re


def extract_text_from_pdf(pdf_file) -> Optional[str]:
    """Extract text from uploaded PDF file using multiple methods for better accuracy."""
    try:
        # Reset file pointer to beginning
        pdf_file.seek(0)
        
        # Method 1: Try pdfplumber first (better for complex layouts)
        try:
            with pdfplumber.open(pdf_file) as pdf:
                text_parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                
                if text_parts:
                    extracted_text = '\n\n'.join(text_parts)
                    # Clean up the text
                    extracted_text = re.sub(r'\n+', '\n', extracted_text)  # Remove excessive newlines
                    extracted_text = re.sub(r'\s+', ' ', extracted_text)   # Normalize whitespace
                    return extracted_text.strip()
        except Exception:
            pass
        
        # Method 2: Fallback to PyPDF2
        pdf_file.seek(0)
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_parts = []
            
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            if text_parts:
                extracted_text = '\n\n'.join(text_parts)
                # Clean up the text
                extracted_text = re.sub(r'\n+', '\n', extracted_text)
                extracted_text = re.sub(r'\s+', ' ', extracted_text)
                return extracted_text.strip()
        except Exception:
            pass
            
        return None
        
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return None


def get_openai_client():
    """Initialize OpenAI client using Streamlit secrets or environment variables"""
    try:
        # Try Streamlit secrets first (for cloud deployment)
        if hasattr(st, 'secrets') and 'openai' in st.secrets:
            api_key = st.secrets.openai.api_key
        else:
            # Fallback to environment variable (for local development)
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            return None, "OpenAI API key not found. Please configure it in Streamlit secrets or environment variables."
        
        return openai.OpenAI(api_key=api_key), None
    except Exception as e:
        return None, f"Error initializing OpenAI client: {str(e)}"


def construct_prompt(icp_rules_json: dict, profile_text: str) -> str:
    """
    Dynamically construct the AI's System Prompt using the ICP rules and profile text.
    """
    icp_title = icp_rules_json.get("icp_title", icp_rules_json.get("icp_focus", ""))
    rules = icp_rules_json.get("rules", [])
    
    rules_text = "\n".join([f"- {rule}" for rule in rules])
    
    prompt = f"""You are an expert ICP (Ideal Customer Profile) evaluator. Analyze if this candidate profile matches the specified criteria.

ICP TARGET: {icp_title}

CRITERIA TO EVALUATE:
{rules_text}

CANDIDATE PROFILE:
{profile_text}

INSTRUCTIONS:
1. Analyze the profile against each criteria
2. Determine "Fit" or "Not Fit" based on ALL criteria
3. Provide clear justification

REQUIRED FORMAT:
Fit; [Your reasoning in 2-3 sentences]
OR
Not Fit; [Your reasoning in 2-3 sentences]

Examples:
- "Fit; Candidate is a Senior Full Stack Engineer with 6+ years experience, explicitly mentions Node.js and React expertise, and has PostgreSQL database experience with CI/CD knowledge."
- "Not Fit; While candidate has frontend React skills, they lack backend Node.js experience and don't mention database technologies or testing frameworks required for this role."

Evaluate now:"""
    
    return prompt


def evaluate_profile(profile_text: str, icp_rules_json: dict) -> Tuple[str, str]:
    """
    Evaluate the profile using OpenAI directly (cloud-compatible version).
    
    Args:
        profile_text (str): The candidate profile text from resume, profile, or manual input
        icp_rules_json (dict): The ICP configuration
        
    Returns:
        Tuple[str, str]: (Decision, Reasoning) where Decision is 'Fit', 'Not Fit', or 'Error'
    """
    try:
        # Initialize OpenAI client
        client, error = get_openai_client()
        if not client:
            return ("Error", error)
        
        # Construct the prompt
        prompt = construct_prompt(icp_rules_json, profile_text)
        
        # Make the OpenAI API call
        response = client.chat.completions.create(
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
            
            # Clean up the decision by removing brackets and normalizing
            decision = decision.replace('[', '').replace(']', '').strip()
            
            # Validate the decision
            if decision in ['Fit', 'Not Fit']:
                return (decision, reasoning)
            else:
                return ('Error', f'Invalid decision format received: {decision}. Expected "Fit" or "Not Fit".')
        else:
            return ('Error', f'Could not parse AI response. Expected format: "Decision; Reasoning". Received: {ai_response}')
            
    except Exception as e:
        return ('Error', f'An API error occurred: {str(e)}')


def main():
    """
    Main Streamlit application logic.
    """
    # Set page configuration
    st.set_page_config(
        page_title="AI ICP Fit Evaluator",
        page_icon="🎯",
        layout="centered"
    )
    
    # Add Font Awesome CSS
    st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
    .icon {
        margin-right: 8px;
    }
    .big-label {
        font-size: 18px !important;
        font-weight: bold !important;
        margin-bottom: 8px !important;
        color: rgb(49, 51, 63) !important;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 16px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Page title and description
    st.markdown("# <i class='fas fa-bullseye icon'></i>AI ICP Fit Evaluator", unsafe_allow_html=True)
    st.markdown("""
    This application evaluates candidate profiles against your Ideal Customer Profile (ICP) criteria using AI.
    Upload your ICP configuration and add candidate profile data to get an instant evaluation.
    """)
    
    # Check API key configuration
    client, error = get_openai_client()
    if not client:
        st.markdown(f"<div style='color: red;'><i class='fas fa-exclamation-triangle icon'></i><strong>Configuration Error</strong>: {error}</div>", unsafe_allow_html=True)
        st.markdown("<div style='color: blue;'><i class='fas fa-lightbulb icon'></i><strong>For local development</strong>: Set the `OPENAI_API_KEY` environment variable</div>", unsafe_allow_html=True)
        st.markdown("<div style='color: blue;'><i class='fas fa-cloud icon'></i><strong>For Streamlit Cloud</strong>: Configure the API key in the Secrets management section</div>", unsafe_allow_html=True)
        return
    
    st.divider()
    
    # File uploader for ICP configuration
    st.markdown("## <i class='fas fa-file-alt icon'></i>ICP Configuration", unsafe_allow_html=True)

    # Download example configuration button
    example_config = {
        "icp_title": "Senior Full Stack Engineer (Node.js/React Focus)",
        "rules": [
            "Must hold the title of 'Senior Software Engineer' or equivalent, with 5+ years of experience.",
            "Must explicitly mention proficiency in a modern backend runtime, specifically Node.js (or Express for APIs).",
            "Must demonstrate strong frontend expertise using a library like React (or including TypeScript).",
            "Must list experience with a relational database technology, such as PostgreSQL or MySQL (mentioning AWS RDS is a strong indicator).",
            "Must use keywords related to testing, APIs, and continuous integration (e.g., Unit Tests, REST APIs, CI/CD pipelines).",
            "Should include experience with containerization, specifically Docker, for local development or deployment."
        ]
    }
    example_json = json.dumps(example_config, indent=2)
    st.download_button(
        label="📥 Download Sample Configuration",
        data=example_json,
        file_name="example_icp_config.json",
        mime="application/json",
        help="Download this sample configuration as a JSON file to use as a template"
    )
        
    st.markdown('<div class="big-label"><i class="fas fa-upload icon"></i>Upload your ICP configuration JSON file</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "",
        type=['json'],
        help="Upload a JSON file containing your ICP focus and rules"
    )
    
    # Profile Input Section with multiple methods
    st.markdown("## <i class='fas fa-user icon'></i>Candidate Profile Input", unsafe_allow_html=True)
    
    # Create tabs for different input methods (removed LinkedIn URL tab)
    tab1, tab2 = st.tabs(["📝 Manual Text", "📄 PDF Resume"])
    
    profile_text = ""
    input_source = ""
    
    with tab1:
        st.markdown('<div class="big-label"><i class="fas fa-keyboard icon"></i>Paste profile/resume text here:</div>', unsafe_allow_html=True)
        manual_text = st.text_area(
            "",
            height=200,
            placeholder="Paste the candidate's profile text, resume content, or profile information here...",
            key="manual_text"
        )
        if manual_text.strip():
            profile_text = manual_text
            input_source = "Manual Text"
    
    with tab2:
        st.markdown('<div class="big-label"><i class="fas fa-file-upload icon"></i>Upload PDF Resume:</div>', unsafe_allow_html=True)
        uploaded_pdf = st.file_uploader(
            "",
            type=['pdf'],
            help="Upload a PDF resume or profile export",
            key="pdf_uploader"
        )
        
        if uploaded_pdf is not None:
            with st.spinner("Extracting text from PDF..."):
                extracted_text = extract_text_from_pdf(uploaded_pdf)
                
            if extracted_text:
                st.markdown(f"<div style='color: green;'><i class='fas fa-check icon'></i>Successfully extracted {len(extracted_text)} characters from PDF</div>", unsafe_allow_html=True)
                
                # Show preview of extracted text
                with st.expander("Preview Extracted Text", expanded=False):
                    st.text_area(
                        "Extracted content:",
                        value=extracted_text[:1000] + ("..." if len(extracted_text) > 1000 else ""),
                        height=150,
                        disabled=True
                    )
                
                profile_text = extracted_text
                input_source = "PDF Resume"
            else:
                st.markdown("<div style='color: red;'><i class='fas fa-times icon'></i>Failed to extract text from PDF. Please try a different file or use manual text input.</div>", unsafe_allow_html=True)
    
    # Display ICP configuration if uploaded
    icp_rules_json = None
    if uploaded_file is not None:
        try:
            icp_rules_json = json.load(uploaded_file)
            
            with st.expander("View ICP Configuration", expanded=False):
                st.json(icp_rules_json)
                
        except json.JSONDecodeError:
            st.markdown("<div style='color: orange;'><i class='fas fa-exclamation-triangle icon'></i>Invalid JSON file. Please upload a valid ICP configuration file.</div>", unsafe_allow_html=True)
            icp_rules_json = None
        except Exception as e:
            st.markdown(f"<div style='color: orange;'><i class='fas fa-exclamation-triangle icon'></i>Error reading file: {str(e)}</div>", unsafe_allow_html=True)
            icp_rules_json = None
    
    st.divider()
    
    # Show current input status
    if profile_text.strip():
        st.markdown(f"<div style='color: green;'><i class='fas fa-check icon'></i><strong>Profile loaded from</strong>: {input_source} ({len(profile_text)} characters)</div>", unsafe_allow_html=True)
    
    # Evaluation button and results
    if st.button("🚀 Run AI Evaluation", type="primary", use_container_width=True, help="Click to start AI evaluation"):
        # Validate inputs
        if icp_rules_json is None:
            st.markdown("<div style='color: orange;'><i class='fas fa-exclamation-triangle icon'></i>Please upload a valid ICP configuration JSON file.</div>", unsafe_allow_html=True)
            return
            
        if not profile_text.strip():
            st.markdown("<div style='color: orange;'><i class='fas fa-exclamation-triangle icon'></i>Please provide candidate profile data using one of the input methods above.</div>", unsafe_allow_html=True)
            return
        
        # Show processing spinner
        with st.spinner("AI is evaluating the profile..."):
            # Call the evaluation function
            decision, reasoning = evaluate_profile(profile_text, icp_rules_json)
        
        # Display results
        st.markdown("## <i class='fas fa-chart-bar icon'></i>Evaluation Results", unsafe_allow_html=True)
        
        if decision == "Fit":
            st.markdown(f"<div style='color: green; font-size: 20px; font-weight: bold;'><i class='fas fa-check-circle icon'></i>{decision}</div>", unsafe_allow_html=True)
        elif decision == "Not Fit":
            st.markdown(f"<div style='color: red; font-size: 20px; font-weight: bold;'><i class='fas fa-times-circle icon'></i>{decision}</div>", unsafe_allow_html=True)
        else:  # Error case
            st.markdown(f"<div style='color: red; font-size: 20px; font-weight: bold;'><i class='fas fa-exclamation-triangle icon'></i>{decision}</div>", unsafe_allow_html=True)
        
        # Display reasoning
        st.info(f"**Reasoning:** {reasoning}")
        
        
if __name__ == "__main__":
    main()