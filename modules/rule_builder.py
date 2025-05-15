import streamlit as st
import pandas as pd
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from modules.validation_engine import ValidationRuleLoader
from modules.metadata_template_retrieval import get_metadata_templates
from modules.document_categorization import get_document_categories
from modules.category_template_rules import manage_category_template_rules

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Cross-field rule types
CROSS_FIELD_RULE_TYPES = {
    "dependent_existence": {
        "label": "Dependent Field Existence",
        "description": "When one field has a specific value, another field must exist",
        "params": ["dependent_field", "trigger_field", "trigger_value"],
        "param_descriptions": {
            "dependent_field": "Field that must exist",
            "trigger_field": "Field to check for trigger value",
            "trigger_value": "Value that requires dependent field to exist"
        }
    },
    "date_order": {
        "label": "Date Order",
        "description": "Ensure that one date field is before or after another date field",
        "params": ["date_a_key", "date_b_key", "format"],
        "param_descriptions": {
            "date_a_key": "First date field",
            "date_b_key": "Second date field",
            "format": "Date format (e.g., %Y-%m-%d)"
        }
    }
}

def format_rule_for_display(rule, rule_type="field"):
    """Format a rule for display in the UI"""
    rule_type_str = rule.get("type", "unknown")
    
    if rule_type == "field":
        rule_types_dict = FIELD_RULE_TYPES
    else:  # cross_field
        rule_types_dict = CROSS_FIELD_RULE_TYPES
    
    if rule_type_str in rule_types_dict:
        rule_info = rule_types_dict[rule_type_str]
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
    """Main entry point for the Rule Builder - allows selecting between document type rules and category-template rules"""
    st.write("Welcome to the Rule Builder. Here you can manage validation rules for different document types and category-template combinations.")
    
    # Initialize the rule loader if it's not already in the session state
    if 'rule_loader' not in st.session_state:
        st.session_state.rule_loader = ValidationRuleLoader(rules_config_path='config/validation_rules.json')
    
    # Create tabs for the different rule types
    doc_type_tab, category_template_tab = st.tabs(["Document Type Rules", "Category-Template Rules"])
    
    with doc_type_tab:
        show_document_type_rules()
    
    with category_template_tab:
        # Call the category-template rules management function
        manage_category_template_rules()

def show_document_type_rules():
    """Show UI for selecting and managing document type rules"""
    st.subheader("Document Type Rules")
    
    # Load available document types
    doc_types = []
    try:
        # Try to get document types from the validation rules
        if 'rule_loader' in st.session_state:
            doc_types = st.session_state.rule_loader.get_document_types()
        
        if not doc_types:
            st.warning("No document types found in validation rules. Please add one first.")
    except Exception as e:
        st.error(f"Error loading document types: {e}")
        return
    
    # Create a dropdown to select document type
    selected_doc_type_name = st.selectbox(
        "Select Document Type",
        options=[doc_type.get("name", "Unknown") for doc_type in doc_types],
        index=0 if doc_types else None
    )
    
    if selected_doc_type_name and doc_types:
        # Find the selected document type
        selected_doc_type = next((dt for dt in doc_types if dt.get("name") == selected_doc_type_name), None)
        
        if selected_doc_type:
            # Show the rules for the selected document type
            show_doc_type_rule_details(selected_doc_type)
        else:
            st.warning(f"Document type '{selected_doc_type_name}' not found in the rules.")
    
    # Add button to create a new document type
    if st.button("Add New Document Type"):
        st.session_state.show_add_doc_type = True
    
    if st.session_state.get("show_add_doc_type", False):
        with st.form("add_doc_type_form"):
            new_doc_type_name = st.text_input("New Document Type Name")
            submitted = st.form_submit_button("Create Document Type")
            
            if submitted and new_doc_type_name:
                # Add the new document type
                try:
                    st.session_state.rule_loader.add_document_type(new_doc_type_name)
                    st.success(f"Document type '{new_doc_type_name}' created successfully.")
                    st.session_state.show_add_doc_type = False
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error creating document type: {e}")

def show_doc_type_rule_details(doc_type):
    """Show the details of rules for a specific document type"""
    st.header(f"Rules for Document Type: {doc_type.get('name', 'Unknown')}")
    
    # Display Field Rules
    st.subheader("Field Rules")
    field_rules_data = []
    
    for field_def in doc_type.get("fields", []):
        field_key = field_def.get("key", "unknown")
        field_rules = field_def.get("rules", [])
        
        if not field_rules:
            field_rules_data.append({
                "Field": field_key,
                "Rule Type": "No rules defined",
                "Description": "",
                "Field Index": doc_type.get("fields", []).index(field_def),
                "Rule Index": -1
            })
        else:
            for i, rule in enumerate(field_rules):
                field_rules_data.append({
                    "Field": field_key,
                    "Rule Type": rule.get("type", "unknown"),
                    "Description": format_rule_for_display(rule),
                    "Field Index": doc_type.get("fields", []).index(field_def),
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
            field_options = [field.get("key", "unknown") for field in doc_type.get("fields", [])]
            if field_options:
                selected_field = st.selectbox("Select Field", options=field_options)
                selected_field_idx = next((i for i, f in enumerate(doc_type.get("fields", [])) 
                                          if f.get("key") == selected_field), 0)
            else:
                st.warning("No fields found for this document type. Add fields first.")
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
                        
                        # Get the document type's fields
                        fields = doc_type.get("fields", [])
                        
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
        st.info("No field rules defined for this document type. Add a rule by selecting a field and rule type below.")
    
    # Display Mandatory Fields
    st.subheader("Mandatory Fields")
    mandatory_fields = doc_type.get("mandatory_fields", [])
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
