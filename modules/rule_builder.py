import streamlit as st
import pandas as pd
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from modules.validation_engine import ValidationRuleLoader
from modules.metadata_template_retrieval import get_metadata_templates
# Import the template-based rule functions
from modules.category_template_rules import manage_template_rules, show_template_rule_overview

# Define save_validation_rules here if it's not in the deployed version
def save_validation_rules(rules_data):
    """Save validation rules to config file"""
    try:
        # Ensure we have rule_loader in session state
        if 'rule_loader' not in st.session_state:
            st.session_state.rule_loader = ValidationRuleLoader(rules_config_path='config/validation_rules.json')
        
        # Update the rules in the rule loader
        st.session_state.rule_loader.rules = rules_data
        
        # Save to file
        config_path = st.session_state.rule_loader.rules_config_path
        with open(config_path, 'w') as f:
            json.dump(rules_data, f, indent=2)
        
        return True
    except Exception as e:
        st.error(f"Error saving validation rules: {e}")
        return False

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

def format_rule_for_display(rule, rule_type="field"):
    """Format a rule for display in the UI"""
    rule_type_str = rule.get("type", "unknown")
    
    if rule_type_str in FIELD_RULE_TYPES:
        rule_info = FIELD_RULE_TYPES[rule_type_str]
        display_parts = [rule_info.get("label", rule_type_str)]
        
        # Add params
        for param in rule_info.get("params", []):
            if param in rule:
                param_display = f"{param}: {rule[param]}"
                display_parts.append(param_display)
        
        return " | ".join(display_parts)
    else:
        # Fallback for unknown rule types
        return f"Type: {rule_type_str} | Params: {', '.join([f'{k}:{v}' for k, v in rule.items() if k != 'type'])}"

# For backward compatibility with app.py import
def show_rule_builder():
    """Alias for show_rule_overview for backward compatibility"""
    show_rule_overview()

def show_rule_overview():
    """Main entry point for the Rule Builder"""
    st.title('Rule Builder')
    st.write('Create and manage validation rules for metadata templates.')
    
    # Initialize resources needed for the rule builder
    initialize_rule_builder()
    
    # Manage template rules
    manage_template_rules()
    
    # Display Field Rules
    st.subheader("Field Rules")
    field_rules_data = []
    
    for field_def in template_rule.get("fields", []):
        field_key = field_def.get("key", "unknown")
        field_rules = field_def.get("rules", [])
        
        if not field_rules:
            field_rules_data.append({
                "Field": field_key,
                "Rule Type": "No rules defined",
                "Description": "",
                "Field Index": template_rule.get("fields", []).index(field_def),
                "Rule Index": -1
            })
        else:
            for i, rule in enumerate(field_rules):
                field_rules_data.append({
                    "Field": field_key,
                    "Rule Type": rule.get("type", "unknown"),
                    "Description": format_rule_for_display(rule),
                    "Field Index": template_rule.get("fields", []).index(field_def),
                    "Rule Index": i
                })
    
    if field_rules_data:
        field_rules_df = pd.DataFrame(field_rules_data)
        st.dataframe(field_rules_df.drop(columns=["Field Index", "Rule Index"]), use_container_width=True)
        
        # Add field rule
        st.subheader("Add or Edit Field Rule")
        col1, col2 = st.columns(2)
        with col1:
            # Select field
            field_options = [field.get("key", "unknown") for field in template_rule.get("fields", [])]
            if field_options:
                selected_field = st.selectbox("Select Field", options=field_options)
                selected_field_idx = next((i for i, f in enumerate(template_rule.get("fields", [])) 
                                          if f.get("key") == selected_field), 0)
            else:
                st.warning("No fields found for this template rule. Add fields first.")
                selected_field = None
                selected_field_idx = -1
        
        with col2:
            # Select rule type
            rule_type_options = list(FIELD_RULE_TYPES.keys())
            selected_rule_type = st.selectbox("Select Rule Type", options=rule_type_options)
        
        if selected_field and selected_rule_type:
            # Show rule parameters form
            with st.form(key=f"add_field_rule_{selected_field}_{selected_rule_type}"):
                st.write(f"Configure {FIELD_RULE_TYPES[selected_rule_type]['label']} Rule for {selected_field}")
                
                # Dynamically generate parameter inputs based on rule type
                param_values = {}
                for param in FIELD_RULE_TYPES[selected_rule_type].get("params", []):
                    description = FIELD_RULE_TYPES[selected_rule_type].get("param_descriptions", {}).get(param, param)
                    param_values[param] = st.text_input(f"{description}")
                
                submitted = st.form_submit_button("Add Rule")
                if submitted:
                    try:
                        # Construct the rule
                        new_rule = {
                            "type": selected_rule_type,
                            **param_values
                        }
                        
                        # Get the template rule's fields
                        fields = template_rule.get("fields", [])
                        
                        # Add rule to the selected field
                        if selected_field_idx >= 0 and selected_field_idx < len(fields):
                            if "rules" not in fields[selected_field_idx]:
                                fields[selected_field_idx]["rules"] = []
                            
                            fields[selected_field_idx]["rules"].append(new_rule)
                            
                            # Save the updated rules
                            st.session_state.rule_loader.save_rules()
                            st.success(f"Rule added successfully for field {selected_field}")
                            st.experimental_rerun()
                        else:
                            st.error("Invalid field index")
                    except Exception as e:
                        st.error(f"Error adding rule: {e}")
    else:
        st.info("No field rules defined for this template rule. Add a rule by selecting a field and rule type below.")
    
    # Display Mandatory Fields
    st.subheader("Mandatory Fields")
    mandatory_fields = template_rule.get("mandatory_fields", [])
    if mandatory_fields:
        st.write("The following fields are mandatory:")
        for field in mandatory_fields:
            st.write(f"- {field}")
    else:
        st.info("No mandatory fields defined.")
    
    # Add fields to document type
    st.subheader("Add Field to Document Type")
    with st.form(key="add_field"):
        new_field_key = st.text_input("Field Key")
        new_field_type = st.selectbox("Field Type", options=["text", "number", "date", "boolean", "enum"])
        
        submitted = st.form_submit_button("Add Field")
        if submitted and new_field_key:
            try:
                # Check if field already exists
                existing_field_keys = [field.get("key", "") for field in doc_type.get("fields", [])]
                if new_field_key in existing_field_keys:
                    st.error(f"Field {new_field_key} already exists")
                else:
                    # Add the new field
                    if "fields" not in doc_type:
                        doc_type["fields"] = []
                    
                    doc_type["fields"].append({
                        "key": new_field_key,
                        "type": new_field_type
                    })
                    
                    # Save the updated rules
                    st.session_state.rule_loader.save_rules()
                    st.success(f"Field {new_field_key} added successfully")
                    st.experimental_rerun()
            except Exception as e:
                st.error(f"Error adding field: {e}")
