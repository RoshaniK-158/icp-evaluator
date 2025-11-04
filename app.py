import streamlit as st
import json
import requests
from typing import Tuple


def evaluate_profile(profile_text: str, icp_rules_json: dict) -> Tuple[str, str]:
    """
    Call the custom API backend to evaluate the profile.
    
    Args:
        profile_text (str): The LinkedIn profile about section text
        icp_rules_json (dict): The ICP configuration
        
    Returns:
        Tuple[str, str]: (Decision, Reasoning) where Decision is 'Fit', 'Not Fit', or 'Error'
    """
    try:
        # API endpoint
        api_url = "http://127.0.0.1:8000/evaluate"
        
        # Prepare the request payload
        payload = {
            "profile_text": profile_text,
            "icp_rules_json": icp_rules_json
        }
        
        # Make the API call to our custom backend
        response = requests.post(
            api_url,
            json=payload,
            timeout=30,  # 30 second timeout
            headers={"Content-Type": "application/json"}
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                return (result["decision"], result["reasoning"])
            else:
                return ("Error", result.get("reasoning", "Unknown error occurred"))
        else:
            error_detail = response.json().get("detail", "Unknown API error")
            return ("Error", f"API Error ({response.status_code}): {error_detail}")
            
    except requests.exceptions.ConnectionError:
        return ("Error", "Cannot connect to API backend. Please ensure the API server is running on http://127.0.0.1:8000")
    except requests.exceptions.Timeout:
        return ("Error", "API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        return ("Error", f"Request error: {str(e)}")
    except Exception as e:
        return ("Error", f"Unexpected error: {str(e)}")


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
    
    st.divider()
    
    # File uploader for ICP configuration
    st.subheader("📄 ICP Configuration")
    uploaded_file = st.file_uploader(
        "Upload your ICP configuration JSON file",
        type=['json'],
        help="Upload a JSON file containing your ICP focus and rules"
    )
    
    # Text area for LinkedIn profile
    st.subheader("👤 LinkedIn Profile")
    profile_text = st.text_area(
        "Paste the LinkedIn 'About Section' text here:",
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
            st.success(f"✅ **{decision}**", icon="✅")
        elif decision == "Not Fit":
            st.error(f"❌ **{decision}**", icon="❌")
        else:  # Error case
            st.error(f"🚨 **{decision}**", icon="🚨")
        
        # Display reasoning
        st.info(f"**Reasoning:** {reasoning}", icon="💭")
    
    # Footer with example ICP format
    st.divider()
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
        
    st.markdown("---")
    st.markdown("🔑 **Note:** Make sure the API backend server is running on `http://127.0.0.1:8000` before using this application.")
    st.markdown("💡 **Tip:** Run `python api_backend.py` to start the backend server.")


if __name__ == "__main__":
    main()