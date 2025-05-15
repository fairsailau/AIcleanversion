import streamlit as st
import pandas as pd
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from modules.validation_engine import ValidationRuleLoader
from modules.metadata_template_retrieval import get_metadata_templates
# Import the template-based rule functions
from modules.category_template_rules import manage_template_rules, show_template_rule_overview, save_validation_rules

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize common resources
def initialize_rule_builder():
    """Initialize resources needed for the rule builder"""
    # Initialize rule loader
    if 'rule_loader' not in st.session_state:
        st.session_state.rule_loader = ValidationRuleLoader(rules_config_path='config/validation_rules.json')
        if hasattr(st.session_state.rule_loader, 'rules'):
            st.session_state.validation_rules = st.session_state.rule_loader.rules
        else:
            st.session_state.validation_rules = {"template_rules": []}
    
    # Load metadata templates if not already loaded
    if 'metadata_templates' not in st.session_state:
        try:
            templates = get_metadata_templates()
            st.session_state.metadata_templates = templates
        except Exception as e:
            st.error(f"Error loading metadata templates: {e}")
            st.session_state.metadata_templates = {}
            
    # Initialize UI state variables if needed
    if 'is_editing_rule' not in st.session_state:
        st.session_state.is_editing_rule = False
    if 'editing_field_key' not in st.session_state:
        st.session_state.editing_field_key = None
    if 'editing_rule_index' not in st.session_state:
        st.session_state.editing_rule_index = -1

# Constants for rule types
FIELD_RULE_TYPES = {
    "regex": {
        "label": "Regular Expression",
        "description": "Validate that the field value matches a regular expression pattern",
        "params": ["pattern"],
        "param_descriptions": {
            "pattern": "Regular expression pattern to match"
        }
    },
    "enum": {
        "label": "Enumeration",
        "description": "Validate that the field value is one of a list of allowed values",
        "params": ["values"],
        "param_descriptions": {
            "values": "Comma-separated list of allowed values"
        }
    },
    "min_length": {
        "label": "Minimum Length",
        "description": "Validate that the field value has at least the specified length",
        "params": ["length"],
        "param_descriptions": {
            "length": "Minimum length (integer)"
        }
    },
    "max_length": {
        "label": "Maximum Length",
        "description": "Validate that the field value does not exceed the specified length",
        "params": ["length"],
        "param_descriptions": {
            "length": "Maximum length (integer)"
        }
    },
    "dataType": {
        "label": "Data Type",
        "description": "Validate that the field value is of a specific data type",
        "params": ["type"],
        "param_descriptions": {
            "type": "Data type (string, number, boolean, date)"
        }
    }
}

# Helper function to format rule for display
def format_rule_for_display(rule):
    """Format a rule for display in the rule builder UI"""
    rule_type = rule.get("type", "unknown")
    if rule_type in FIELD_RULE_TYPES:
        rule_info = FIELD_RULE_TYPES[rule_type]
        # Start with the label
        display = rule_info["label"]
        
        # Add parameters
        for param in rule_info.get("params", []):
            if param in rule:
                display += f" | {param}: {rule[param]}"
        return display
    else:
        return f"Rule of type '{rule_type}'"

def show_rule_overview():
    """Main entry point for the Rule Builder"""
    st.title('Validation Rule Builder')
    st.write('Create and manage validation rules for metadata templates.')
    
    # Initialize resources needed for the rule builder
    initialize_rule_builder()
    
    # Manage template rules - this function handles displaying and editing field rules
    # as well as mandatory fields and other rule types
    manage_template_rules()

# For backward compatibility with app.py import
def show_rule_builder():
    """Alias for show_rule_overview for backward compatibility"""
    show_rule_overview()
