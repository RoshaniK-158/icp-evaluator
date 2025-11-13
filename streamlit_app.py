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
                    # Enhanced text cleanup for PDF extraction
                    extracted_text = re.sub(r'\n+', '\n', extracted_text)  # Remove excessive newlines
                    extracted_text = re.sub(r'[ \t]+', ' ', extracted_text)   # Normalize whitespace
                    extracted_text = re.sub(r'\n ', '\n', extracted_text)     # Remove spaces after newlines
                    extracted_text = re.sub(r' \n', '\n', extracted_text)     # Remove spaces before newlines
                    extracted_text = extracted_text.replace('\x00', '')       # Remove null characters
                    extracted_text = extracted_text.replace('\ufffd', '')     # Remove replacement characters
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
                # Enhanced text cleanup for PDF extraction
                extracted_text = re.sub(r'\n+', '\n', extracted_text)
                extracted_text = re.sub(r'[ \t]+', ' ', extracted_text)
                extracted_text = re.sub(r'\n ', '\n', extracted_text)
                extracted_text = re.sub(r' \n', '\n', extracted_text)
                extracted_text = extracted_text.replace('\x00', '')
                extracted_text = extracted_text.replace('\ufffd', '')
                return extracted_text.strip()
        except Exception:
            pass
            
        return None
        
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return None


def normalize_text(text: str) -> str:
    """Normalize text to ensure consistent processing between PDF and manual input."""
    if not text:
        return ""
    
    # Remove excessive whitespace and normalize line breaks
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove special characters that might interfere
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)  # Remove zero-width characters
    # Normalize quotes and dashes
    text = re.sub(r'[\u2018\u2019]', "'", text)  # Normalize quotes
    text = re.sub(r'[\u2013\u2014]', "-", text)  # Normalize dashes
    
    return text


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


def construct_prompt(icp_content: str, profile_text: str) -> str:
    """
    Dynamically construct the AI's System Prompt using the ICP criteria text and profile text.
    """
    prompt = f"""You are an expert ICP (Ideal Customer Profile) evaluator. Analyze if this candidate profile matches the specified criteria.

ICP CRITERIA:
{icp_content}

CANDIDATE PROFILE:
{profile_text}

INSTRUCTIONS:
1. Analyze the profile against the ICP criteria
2. Determine "Fit" or "Not Fit" based on how well the candidate matches the criteria
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


def evaluate_profile(profile_text: str, icp_content: str) -> Tuple[str, str]:
    """
    Evaluate the profile using OpenAI directly (cloud-compatible version).
    
    Args:
        profile_text (str): The candidate profile text from resume, profile, or manual input
        icp_content (str): The ICP criteria in plain text format
        
    Returns:
        Tuple[str, str]: (Decision, Reasoning) where Decision is 'Fit', 'Not Fit', or 'Error'
    """
    try:
        # Normalize the text for consistent processing
        normalized_text = normalize_text(profile_text)
        
        # Initialize OpenAI client
        client, error = get_openai_client()
        if not client:
            return ("Error", error)
        
        # Construct the prompt
        prompt = construct_prompt(icp_content, normalized_text)
        
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
    
    # ICP Configuration Input Section
    st.markdown("## <i class='fas fa-file-alt icon'></i>ICP Configuration", unsafe_allow_html=True)
    
    # Create tabs for different ICP input methods
    icp_tab1, icp_tab2 = st.tabs(["✏️ Text Input", "📁 Upload Text File"])
    
    icp_content = ""
    
    with icp_tab1:
        st.markdown('<div class="big-label"><i class="fas fa-edit icon"></i>Enter your ICP criteria:</div>', unsafe_allow_html=True)
        icp_text = st.text_area(
            "",
            height=200,
            placeholder="Enter your ICP criteria in simple text format. For example:\n\nTitle: Senior Full Stack Engineer\n\nCriteria:\n- Must have 5+ years of experience\n- Must know Node.js and React\n- Must have database experience (PostgreSQL/MySQL)\n- Should have testing and CI/CD knowledge\n- Docker experience preferred",
            key="icp_text_input"
        )
        if icp_text.strip():
            icp_content = icp_text.strip()
    
    with icp_tab2:
        st.markdown('<div class="big-label"><i class="fas fa-file-upload icon"></i>Upload ICP criteria text file:</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "",
            type=['txt'],
            help="Upload a text file containing your ICP criteria"
        )
        
        if uploaded_file is not None:
            try:
                icp_content = uploaded_file.read().decode('utf-8').strip()
                st.markdown(f"<div style='color: green;'><i class='fas fa-check icon'></i>Successfully loaded ICP criteria ({len(icp_content)} characters)</div>", unsafe_allow_html=True)
                
                # Show preview of uploaded content
                with st.expander("Preview ICP Criteria", expanded=False):
                    st.text_area(
                        "ICP content:",
                        value=icp_content[:500] + ("..." if len(icp_content) > 500 else ""),
                        height=150,
                        disabled=True
                    )
            except Exception as e:
                st.markdown(f"<div style='color: red;'><i class='fas fa-times icon'></i>Error reading file: {str(e)}</div>", unsafe_allow_html=True)
                icp_content = ""
    
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
            # Normalize manual text input to match PDF processing
            normalized_text = manual_text.strip()
            normalized_text = re.sub(r'\n+', '\n', normalized_text)
            normalized_text = re.sub(r'[ \t]+', ' ', normalized_text)
            normalized_text = re.sub(r'\n ', '\n', normalized_text)
            normalized_text = re.sub(r' \n', '\n', normalized_text)
            
            profile_text = normalized_text
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
                
                profile_text = normalize_text(extracted_text)
                input_source = "PDF Resume"
            else:
                st.markdown("<div style='color: red;'><i class='fas fa-times icon'></i>Failed to extract text from PDF. Please try a different file or use manual text input.</div>", unsafe_allow_html=True)
    
    # Display ICP content if provided
    if icp_content:
        with st.expander("View Current ICP Criteria", expanded=False):
            st.text(icp_content)
    
    st.divider()
    
    # Show current input status
    if profile_text.strip():
        st.markdown(f"<div style='color: green;'><i class='fas fa-check icon'></i><b>Profile loaded from:</b> {input_source} ({len(profile_text)} characters)</div>", unsafe_allow_html=True)
        
        # Add debug information to help troubleshoot
        with st.expander("Debug Information", expanded=False):
            st.write(f"**Text length:** {len(profile_text)} characters")
            st.write(f"**First 200 characters:**")
            st.code(repr(profile_text[:200]))
            st.write(f"**Last 200 characters:**")
            st.code(repr(profile_text[-200:]))
            
            # Show whitespace and special character count
            import string
            whitespace_count = sum(1 for c in profile_text if c.isspace())
            special_char_count = sum(1 for c in profile_text if not c.isalnum() and not c.isspace())
            st.write(f"**Whitespace characters:** {whitespace_count}")
            st.write(f"**Special characters:** {special_char_count}")
            st.write(f"**Line breaks:** {profile_text.count(chr(10))}")
            
            # Show a downloadable version of the processed text
            st.download_button(
                label="Download Processed Text",
                data=profile_text,
                file_name=f"processed_text_{input_source.lower().replace(' ', '_')}.txt",
                mime="text/plain",
                help="Download the exact text that will be sent to AI for evaluation"
            )
    
    # Evaluation button and results
    if st.button("🚀 Run AI Evaluation", type="primary", use_container_width=True, help="Click to start AI evaluation"):
        # Validate inputs
        if not icp_content:
            st.markdown("<div style='color: orange;'><i class='fas fa-exclamation-triangle icon'></i>Please provide ICP criteria using one of the input methods above.</div>", unsafe_allow_html=True)
            return
            
        if not profile_text.strip():
            st.markdown("<div style='color: orange;'><i class='fas fa-exclamation-triangle icon'></i>Please provide candidate profile data using one of the input methods above.</div>", unsafe_allow_html=True)
            return
        
        # Show processing spinner with debugging info
        with st.spinner("🤖 AI is evaluating the profile..."):
            # Show debugging information
            with st.expander("🔍 Debug: Text being sent to AI", expanded=False):
                st.text_area(
                    "Normalized text for AI evaluation:",
                    value=profile_text[:500] + ("..." if len(profile_text) > 500 else ""),
                    height=100,
                    disabled=True,
                    help="This shows the first 500 characters of the normalized text that will be sent to the AI"
                )
                st.write(f"**Text length:** {len(profile_text)} characters")
                st.write(f"**Input source:** {input_source}")
                
                # Also show key terms that should be detected from the ICP configuration
                key_terms = []
                if icp_content:
                    # Extract key terms from ICP content dynamically
                    # Look for technology names, frameworks, databases, etc.
                    tech_pattern = r'\b([A-Z][a-z]*(?:\.[a-z]+)?|[A-Z]{2,}(?:/[A-Z]+)*)\b'
                    potential_terms = re.findall(tech_pattern, icp_content)
                    # Filter to likely technology/skill terms (length > 2, not common words)
                    common_words = {'Must', 'Should', 'The', 'And', 'For', 'With', 'Experience', 'Years', 'Including', 'Such', 'Like', 'Have', 'Know', 'Title', 'Criteria', 'Senior', 'Junior', 'Preferred'}
                    key_terms = [term for term in set(potential_terms) if len(term) > 2 and term not in common_words][:10]  # Limit to 10 terms
                
                found_terms = [term for term in key_terms if term.lower() in profile_text.lower()]
                missing_terms = [term for term in key_terms if term.lower() not in profile_text.lower()]
                
                if key_terms:
                    st.write("**Key terms from ICP found in text:**", found_terms if found_terms else "None")
                    st.write("**Key terms from ICP missing:**", missing_terms if missing_terms else "None")
            
            # Call the evaluation function
            decision, reasoning = evaluate_profile(profile_text, icp_content)
        
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