import streamlit as st
import json
import openai
import os
from typing import Tuple


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


def evaluate_profile(profile_text: str, icp_rules_json: dict) -> Tuple[str, str]:
    """
    Evaluate the profile using OpenAI directly (cloud-compatible version).
    
    Args:
        profile_text (str): The LinkedIn profile about section text
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
    
    # Page title and description
    st.title("🎯 AI ICP Fit Evaluator")
    st.markdown("""
    This application evaluates LinkedIn profiles against your Ideal Customer Profile (ICP) criteria using AI.
    Upload your ICP configuration and paste a LinkedIn "About Section" to get an instant evaluation.
    """)
    
    # Check API key configuration
    client, error = get_openai_client()
    if not client:
        st.error(f"🚨 **Configuration Error**: {error}")
        st.info("💡 **For local development**: Set the `OPENAI_API_KEY` environment variable")
        st.info("☁️ **For Streamlit Cloud**: Configure the API key in the Secrets management section")
        return
    
    st.divider()
    
    # File uploader for ICP configuration
    st.subheader("📄 ICP Configuration")

    with st.expander("📖 ICP Configuration Format Example"):
        st.markdown("Your JSON file should follow this format:")
        example_config = {
            "icp_focus": "Enterprise SaaS Sales Director",
            "rules": [
                "Must be a Director-level or higher.",
                "Must explicitly mention experience selling software or SaaS products.",
                "Must mention keywords like 'quota', 'pipeline management', or 'global teams'."
            ]
        }
        st.json(example_config)
        
    # Add custom CSS for larger, bold labels
    st.markdown("""
    <style>
    .big-label {
        font-size: 18px !important;
        font-weight: bold !important;
        margin-bottom: 8px !important;
        color: rgb(49, 51, 63) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="big-label">Upload your ICP configuration JSON file</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "",
        type=['json'],
        help="Upload a JSON file containing your ICP focus and rules"
    )
    
    # Text area for LinkedIn profile
    st.subheader("👤 LinkedIn Profile")
    
    st.markdown('<div class="big-label">Paste the LinkedIn \'About Section\' text here:</div>', unsafe_allow_html=True)
    
    profile_text = st.text_area(
        "",
        height=200,
        placeholder="Paste the LinkedIn profile's About section content here..."
    )
    
    # Display ICP configuration if uploaded
    icp_rules_json = None
    if uploaded_file is not None:
        try:
            icp_rules_json = json.load(uploaded_file)
            
            with st.expander("📋 View ICP Configuration", expanded=False):
                st.json(icp_rules_json)
                
        except json.JSONDecodeError:
            st.warning("⚠️ Invalid JSON file. Please upload a valid ICP configuration file.")
            icp_rules_json = None
        except Exception as e:
            st.warning(f"⚠️ Error reading file: {str(e)}")
            icp_rules_json = None
    
    st.divider()
    
    # Evaluation button and results
    if st.button("🚀 Run AI Evaluation", type="primary", use_container_width=True):
        # Validate inputs
        if icp_rules_json is None:
            st.warning("⚠️ Please upload a valid ICP configuration JSON file.")
            return
            
        if not profile_text.strip():
            st.warning("⚠️ Please provide the LinkedIn profile text.")
            return
        
        # Show processing spinner
        with st.spinner("🤖 AI is evaluating the profile..."):
            # Call the evaluation function
            decision, reasoning = evaluate_profile(profile_text, icp_rules_json)
        
        # Display results
        st.subheader("📊 Evaluation Results")
        
        if decision == "Fit":
            st.success(f"✅ **{decision}**")
        elif decision == "Not Fit":
            st.error(f"❌ **{decision}**")
        else:  # Error case
            st.error(f"🚨 **{decision}**")
        
        # Display reasoning
        st.info(f"**Reasoning:** {reasoning}")
        
        
if __name__ == "__main__":
    main()