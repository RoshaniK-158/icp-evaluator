import streamlit as st
import json
import openai
import os
from typing import Tuple, Optional, Dict, List
import PyPDF2
import pdfplumber
import io
import re
from difflib import SequenceMatcher
import datetime


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


def extract_skills_from_icp(icp_content: str) -> List[str]:
    """Dynamically extract skills and keywords from ICP content - works for any field."""
    skills = []
    
    # Extract terms
    term_patterns = [
        r'\b[A-Z][a-zA-Z]*(?:\.[a-zA-Z]+)*\b',
        r'\b[A-Z]{2,}\b',
        r'\b[a-z]+[-_][a-z]+\b',
        r'\b\w+(?:ing|tion|ment|ness|ity|ics)\b',
    ]
    
    for pattern in term_patterns:
        matches = re.findall(pattern, icp_content, re.IGNORECASE)
        skills.extend([match.strip() for match in matches if len(match) > 2])
    
    # Extract quoted terms (often important skills/tools)
    quoted_skills = re.findall(r'["\']([^"\'>]{2,30})["\']', icp_content)
    skills.extend(quoted_skills)
    
    # Extract parenthetical mentions (often certifications, tools, examples)
    paren_skills = re.findall(r'\(([^)]{2,30})\)', icp_content)
    skills.extend(paren_skills)
    
    # Filter out generic words that appear in any field
    generic_words = {
        'must', 'should', 'the', 'and', 'for', 'with', 'experience', 
        'years', 'including', 'such', 'like', 'have', 'know', 'title', 
        'criteria', 'preferred', 'required', 'minimum', 'maximum', 'work',
        'role', 'position', 'job', 'career', 'professional', 'skills'
    }
    
    # Clean and deduplicate
    clean_skills = []
    for skill in skills:
        skill_clean = skill.strip().lower()
        if (len(skill_clean) > 2 and 
            skill_clean not in generic_words and 
            not skill_clean.isdigit() and
            skill_clean not in clean_skills):
            clean_skills.append(skill_clean)
    
    return clean_skills[:20]  # Return top 20 to cover more skills

def calculate_skill_match_score(required_skills: List[str], candidate_text: str) -> Dict[str, float]:
    """Calculate skill match scores using fuzzy matching - works for any field."""
    candidate_lower = candidate_text.lower()
    scores = {}
    
    for skill in required_skills:
        skill_lower = skill.lower()
        
        # Direct exact match gets highest score
        if skill_lower in candidate_lower:
            scores[skill] = 1.0
            continue
        
        # Fuzzy matching for partial matches and variations
        best_match = 0.0
        candidate_words = candidate_lower.split()
        
        for word in candidate_words:
            # Check similarity with individual words
            similarity = SequenceMatcher(None, skill_lower, word).ratio()
            if similarity > 0.8:  # High similarity threshold
                best_match = max(best_match, similarity)
            
            # Check if skill is contained in longer words (e.g., "java" in "javascript")
            if len(skill_lower) > 3 and skill_lower in word:
                best_match = max(best_match, 0.8)
            
            # Check if word is contained in skill (e.g., "script" matches "javascript")
            if len(word) > 3 and word in skill_lower:
                best_match = max(best_match, 0.7)
        
        if best_match > 0.5:  # Only include meaningful matches
            scores[skill] = best_match
    
    return scores

def extract_experience_years(text: str) -> int:
    """Extract years of experience from candidate text."""
    # Look for patterns like "5 years", "5+ years", "5-7 years"
    patterns = [
        r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
        r'(\d+)\+?\s*years?\s*in',
        r'experience.*?(\d+)\+?\s*years?',
        r'(\d+)\+?\s*yrs?'
    ]
    
    max_years = 0
    text_lower = text.lower()
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            try:
                years = int(match)
                max_years = max(max_years, years)
            except ValueError:
                continue
    
    return max_years

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


def parse_icp_requirements(icp_content: str) -> Dict[str, any]:
    """Parse ICP content to extract structured requirements."""
    requirements = {
        'must_have': [],
        'nice_to_have': [],
        'experience_years': 0,
        'skills': []
    }
    
    lines = icp_content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        line_lower = line.lower()
        
        # Extract experience requirements
        years_match = re.search(r'(\d+)\+?\s*years?', line_lower)
        if years_match:
            requirements['experience_years'] = max(requirements['experience_years'], int(years_match.group(1)))
        
        # Categorize requirements
        if 'must' in line_lower or 'required' in line_lower:
            requirements['must_have'].append(line)
        elif 'should' in line_lower or 'preferred' in line_lower or 'nice' in line_lower:
            requirements['nice_to_have'].append(line)
    
    # Extract skills dynamically from entire content
    requirements['skills'] = extract_skills_from_icp(icp_content)
    
    # Remove duplicates
    for key in requirements:
        if isinstance(requirements[key], list):
            requirements[key] = list(set(requirements[key]))
    
    return requirements

def construct_prompt(icp_content: str, profile_text: str) -> str:
    """
    Enhanced AI prompt with recruiter persona and intelligent evaluation.
    """
    # Parse requirements for structured analysis
    requirements = parse_icp_requirements(icp_content)
    
    # Calculate intelligent scores
    skill_scores = calculate_skill_match_score(requirements['skills'], profile_text)
    experience_years = extract_experience_years(profile_text)
    
    # Build context for AI
    skills_context = ""
    if skill_scores:
        skills_context = "\n\nSKILL ANALYSIS:"
        for skill, score in skill_scores.items():
            if score > 0:
                skills_context += f"\n- {skill}: {score*100:.0f}% match"
    
    experience_context = f"\n\nEXPERIENCE ANALYSIS:\n- Candidate has {experience_years} years of experience\n- Required: {requirements['experience_years']} years"
    
    prompt = f"""You are an expert professional recruiter with 15+ years of experience in talent acquisition across all industries. Your expertise lies in holistic candidate evaluation that goes beyond keyword matching.

ROLE: Senior Professional Recruiter & ICP Specialist
EXPERTISE: Multi-Industry Talent Assessment, Skills Evaluation, Career Progression Analysis

ICP REQUIREMENTS:
{icp_content}

CANDIDATE PROFILE:
{profile_text}{skills_context}{experience_context}

EVALUATION FRAMEWORK:

1. CORE COMPETENCY (40%)
   - Key skills alignment
   - Equivalent experience recognition
   - Domain knowledge understanding

2. EXPERIENCE DEPTH (30%)
   - Years of relevant experience
   - Career progression trajectory
   - Project complexity and impact

3. ROLE ALIGNMENT (20%)
   - Title and seniority match
   - Responsibility scope
   - Leadership/collaboration indicators

4. GROWTH POTENTIAL (10%)
   - Learning agility indicators
   - Adaptability markers
   - Industry evolution awareness

INSTRUCTIONS:
- Evaluate based on OVERALL FIT, not rigid rule-checking
- Consider equivalent skills and transferable experience WITHIN the same or adjacent domains
- Weight recent experience higher than older experience
- Look for evidence-based indicators, not just keywords
- Assess career trajectory and growth potential
- Consider industry context and role requirements
- CRITICAL: Immediately classify candidates from completely unrelated professions as NO FIT
- Use WEAK FIT only for candidates within the same/adjacent domain who lack some requirements

DECISION CRITERIA:
- STRONG FIT: 80%+ alignment with core requirements
- MODERATE FIT: 60-79% alignment, some gaps but strong potential  
- WEAK FIT: 40-59% alignment, significant gaps but within same/adjacent domain
- NO FIT: <40% alignment OR completely different profession/field

CRITICAL: If candidate is from a completely unrelated profession (e.g., doctor, teacher, chef for a tech role), immediately classify as NO FIT regardless of other factors. Do not use WEAK FIT for career changers from entirely different fields.

REQUIRED FORMAT:
[STRONG FIT/MODERATE FIT/WEAK FIT/NO FIT]; [Evidence-based reasoning citing specific examples from candidate's experience, including skill equivalencies considered and growth potential assessment]

Examples:
- "STRONG FIT; Candidate demonstrates 6+ years in senior marketing role with Google Ads and Facebook Ads expertise. MBA from top-tier university aligns with education requirements. Evidence of team leadership managing 5+ person marketing teams and analytics proficiency with Google Analytics shows strategic thinking."
- "MODERATE FIT; Candidate has 4 years marketing experience with digital advertising skills (equivalent to required digital marketing). Strong analytics background with Tableau shows data-driven approach. Missing direct team management but shows leadership potential through project management experience."
- "NO FIT; Candidate is a medical doctor with no software engineering background. No evidence of backend development (Node.js), frontend frameworks (React), database experience, or relevant technical skills. Medical expertise does not translate to software development requirements."

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
            valid_decisions = ['STRONG FIT', 'MODERATE FIT', 'WEAK FIT', 'NO FIT', 'Fit', 'Not Fit']
            if any(valid_decision in decision.upper() for valid_decision in ['STRONG FIT', 'MODERATE FIT', 'WEAK FIT', 'NO FIT']):
                return (decision, reasoning)
            elif decision in ['Fit', 'Not Fit']:  # Backward compatibility
                return (decision, reasoning)
            else:
                return ('Error', f'Invalid decision format received: {decision}. Expected one of: STRONG FIT, MODERATE FIT, WEAK FIT, NO FIT.')
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
            placeholder="Enter your ICP criteria in simple text format. For example:\n\nTitle: Senior Marketing Manager\n\nCriteria:\n- Must have 5+ years of marketing experience\n- Must have digital marketing expertise (Google Ads, Facebook Ads)\n- Must have team management experience\n- Should have analytics skills (Google Analytics)\n- MBA preferred",
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
    
    st.divider()
    
    # Show current input status
    if profile_text.strip():
        st.markdown(f"<div style='color: green;'><i class='fas fa-check icon'></i><b>Profile loaded from:</b> {input_source} ({len(profile_text)} characters)</div>", unsafe_allow_html=True)
    
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
            # Call the evaluation function
            decision, reasoning = evaluate_profile(profile_text, icp_content)
        
        # Display results
        st.markdown("## <i class='fas fa-chart-bar icon'></i>Evaluation Results", unsafe_allow_html=True)
        
        # Enhanced decision display with color coding
        if "STRONG FIT" in decision.upper():
            st.markdown(f"<div style='color: #00C851; font-size: 24px; font-weight: bold;'><i class='fas fa-star icon'></i>{decision}</div>", unsafe_allow_html=True)
        elif "MODERATE FIT" in decision.upper():
            st.markdown(f"<div style='color: #ffbb33; font-size: 22px; font-weight: bold;'><i class='fas fa-thumbs-up icon'></i>{decision}</div>", unsafe_allow_html=True)
        elif "WEAK FIT" in decision.upper():
            st.markdown(f"<div style='color: #ff8800; font-size: 20px; font-weight: bold;'><i class='fas fa-exclamation icon'></i>{decision}</div>", unsafe_allow_html=True)
        elif "NO FIT" in decision.upper():
            st.markdown(f"<div style='color: #ff4444; font-size: 20px; font-weight: bold;'><i class='fas fa-times-circle icon'></i>{decision}</div>", unsafe_allow_html=True)
        elif decision == "Fit":
            st.markdown(f"<div style='color: green; font-size: 20px; font-weight: bold;'><i class='fas fa-check-circle icon'></i>{decision}</div>", unsafe_allow_html=True)
        elif decision == "Not Fit":
            st.markdown(f"<div style='color: red; font-size: 20px; font-weight: bold;'><i class='fas fa-times-circle icon'></i>{decision}</div>", unsafe_allow_html=True)
        else:  # Error case
            st.markdown(f"<div style='color: red; font-size: 20px; font-weight: bold;'><i class='fas fa-exclamation-triangle icon'></i>{decision}</div>", unsafe_allow_html=True)
        
        # Display reasoning
        st.info(f"**Reasoning:** {reasoning}")
        
        
if __name__ == "__main__":
    main()