import streamlit as st
import pandas as pd
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from modules.validation_engine import ValidationRuleLoader
from modules.metadata_template_retrieval import get_metadata_templates
from modules.document_categorization import get_document_categories
from modules.category_template_rules import manage_category_template_rules

# Main entry point for the Rule Builder
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
    
    # Add/Remove mandatory fields
    with st.expander("Manage Mandatory Fields"):
        field_options = [field.get("key", "unknown") for field in doc_type.get("fields", [])]
        selected_field = st.selectbox("Select Field", options=field_options, key="mandatory_field_select")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Add as Mandatory") and selected_field:
                if selected_field not in mandatory_fields:
                    mandatory_fields.append(selected_field)
                    st.session_state.rule_loader.save_rules()
                    st.success(f"{selected_field} added to mandatory fields")
                    st.experimental_rerun()
                else:
                    st.warning(f"{selected_field} is already mandatory")
        
        with col2:
            if st.button("Remove from Mandatory") and selected_field:
                if selected_field in mandatory_fields:
                    mandatory_fields.remove(selected_field)
                    st.session_state.rule_loader.save_rules()
                    st.success(f"{selected_field} removed from mandatory fields")
                    st.experimental_rerun()
                else:
                    st.warning(f"{selected_field} is not in mandatory fields")
    
    # Display Cross-Field Rules
    st.subheader("Cross-Field Rules")
    cross_field_rules = doc_type.get("cross_field_rules", [])
    
    if cross_field_rules:
        cross_rules_data = []
        for i, rule in enumerate(cross_field_rules):
            cross_rules_data.append({
                "Rule Type": rule.get("type", "unknown"),
                "Fields": ", ".join(rule.get("fields", [])),
                "Description": format_rule_for_display(rule, rule_type="cross_field"),
                "Rule Index": i
            })
        
        cross_rules_df = pd.DataFrame(cross_rules_data)
        st.dataframe(cross_rules_df.drop(columns=["Rule Index"]), use_container_width=True)
    else:
        st.info("No cross-field rules defined.")
    
    # Add cross-field rule
    with st.expander("Add Cross-Field Rule"):
        with st.form(key="add_cross_field_rule"):
            st.write("Configure Cross-Field Rule")
            
            # Select rule type
            rule_type_options = list(CROSS_FIELD_RULE_TYPES.keys())
            selected_rule_type = st.selectbox("Select Rule Type", options=rule_type_options)
            
            # Select fields
            field_options = [field.get("key", "unknown") for field in doc_type.get("fields", [])]  
            selected_fields = st.multiselect("Select Fields", options=field_options)
            
            # Dynamically generate parameter inputs based on rule type
            param_values = {}
            for param in CROSS_FIELD_RULE_TYPES[selected_rule_type].get("params", []):
                description = CROSS_FIELD_RULE_TYPES[selected_rule_type].get("param_descriptions", {}).get(param, param)
                param_values[param] = st.text_input(f"{description}")
            
            submitted = st.form_submit_button("Add Cross-Field Rule")
            if submitted and selected_fields and len(selected_fields) > 1:
                try:
                    # Construct the rule
                    new_rule = {
                        "type": selected_rule_type,
                        "fields": selected_fields,
                        **param_values
                    }
                    
                    # Add the rule
                    if "cross_field_rules" not in doc_type:
                        doc_type["cross_field_rules"] = []
                    
                    doc_type["cross_field_rules"].append(new_rule)
                    
                    # Save the updated rules
                    st.session_state.rule_loader.save_rules()
                    st.success("Cross-field rule added successfully")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error adding cross-field rule: {e}")
            elif submitted and (not selected_fields or len(selected_fields) <= 1):
                st.error("Please select at least two fields for a cross-field rule.")
    
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
    "min_value": {
        "label": "Minimum Value",
        "description": "Validate that the field value is at least the specified value",
        "params": ["value"],
        "param_descriptions": {
            "value": "Minimum value"
        }
    },
    "max_value": {
        "label": "Maximum Value",
        "description": "Validate that the field value does not exceed the specified value",
        "params": ["value"],
        "param_descriptions": {
            "value": "Maximum value"
        }
    },
    "date_format": {
        "label": "Date Format",
        "description": "Validate that the field value is in the specified date format",
        "params": ["format"],
        "param_descriptions": {
            "format": "Date format (e.g., YYYY-MM-DD)"
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
    "comparison": {
        "label": "Field Comparison",
        "description": "Compare values between fields using specified operator",
        "params": ["operator"],
        "param_descriptions": {
            "operator": "Comparison operator (=, !=, <, >, <=, >=)"
        }
    },
    "conditional_mandatory": {
        "label": "Conditional Mandatory",
        "description": "Make certain fields mandatory based on other field values",
        "params": ["condition_field", "condition_value"],
        "param_descriptions": {
            "condition_field": "Field to check for condition",
            "condition_value": "Value that triggers the mandatory requirement"
        }
    },
    "exclusive": {
        "label": "Mutual Exclusivity",
        "description": "Only one of the specified fields can have a value",
        "params": [],
        "param_descriptions": {}
    },
    "inclusive": {
        "label": "Mutual Inclusivity",
        "description": "If one specified field has a value, all others must also have values",
        "params": [],
        "param_descriptions": {}
    },
    "date_range": {
        "label": "Date Range",
        "description": "Validate that two date fields form a valid range",
        "params": ["min_days", "max_days"],
        "param_descriptions": {
            "min_days": "Minimum days between dates (optional)",
            "max_days": "Maximum days between dates (optional)"
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
    "dataType": {
        "label": "Data Type",
        "description": "Validate that the field value is of a specific data type",
        "params": ["expected", "format"],
        "param_descriptions": {
            "expected": "Expected data type (integer, float, date, boolean)",
            "format": "Format string for date type (e.g., %Y-%m-%d)"
        }
    },
    "length": {
        "label": "Length",
        "description": "Validate that the field value length is within specified limits",
        "params": ["min", "max"],
        "param_descriptions": {
            "min": "Minimum length (leave empty for no minimum)",
            "max": "Maximum length (leave empty for no maximum)"
        }
    },
    "range": {
        "label": "Range",
        "description": "Validate that the field value (numeric) is within a specified range",
        "params": ["min", "max"],
        "param_descriptions": {
            "min": "Minimum value (leave empty for no minimum)",
            "max": "Maximum value (leave empty for no maximum)"
        }
    }
}

CROSS_FIELD_RULE_TYPES = {
    "dependent_existence": {
        "label": "Dependent Field Existence",
        "description": "When one field has a specific value, another field must exist"
    },
    "date_order": {
        "label": "Date Order",
        "description": "Ensure that one date field is before or after another date field"
    }
}

def format_rule_for_display(rule, rule_type):
    """Format a rule for display in the UI"""
    if rule_type == "field":
        rule_type_name = rule.get("type", "unknown")
        if rule_type_name == "regex":
            return f"Pattern: {rule.get('params', {}).get('pattern', 'n/a')}"
        elif rule_type_name == "enum":
            values = rule.get('params', {}).get('values', [])
            return f"Values: {', '.join(values) if values else 'n/a'}"
        elif rule_type_name == "dataType":
            expected = rule.get('params', {}).get('expected', 'n/a')
            format_str = rule.get('params', {}).get('format', '')
            return f"Type: {expected} {f'Format: {format_str}' if format_str else ''}"
        elif rule_type_name == "length":
            min_val = rule.get('params', {}).get('min', 'n/a')
            max_val = rule.get('params', {}).get('max', 'n/a')
            return f"Length: {min_val} to {max_val}"
        elif rule_type_name == "range":
            min_val = rule.get('params', {}).get('min', 'n/a')
            max_val = rule.get('params', {}).get('max', 'n/a')
            return f"Range: {min_val} to {max_val}"
        else:
            return f"Unknown rule type: {rule_type_name}"
    elif rule_type == "cross_field":
        rule_type_name = rule.get("type", "unknown")
        rule_name = rule.get("name", "")
        if rule_type_name == "dependent_existence":
            trigger = rule.get('trigger_field', 'n/a')
            trigger_val = rule.get('trigger_value', 'n/a')
            dependent = rule.get('dependent_field', 'n/a')
            return f"{rule_name}: When {trigger} = '{trigger_val}', {dependent} must exist"
        elif rule_type_name == "date_order":
            date_a = rule.get('date_a_key', 'n/a')
            date_b = rule.get('date_b_key', 'n/a')
            order = rule.get('order', 'a_before_b')
            order_text = "must be before" if order == "a_before_b" else "must be after"
            return f"{rule_name}: {date_a} {order_text} {date_b}"
        else:
            return f"Unknown cross-field rule: {rule_type_name}"
    else:
        return "Unknown rule"

def load_validation_rules():
    """Load validation rules from config"""
    try:
        with open('config/validation_rules.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading validation rules: {e}")
        return {"document_types": [], "category_template_rules": {}}

def save_validation_rules(rules_data):
    """Save validation rules to config"""
    try:
        with open('config/validation_rules.json', 'w') as f:
            json.dump(rules_data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving validation rules: {e}")
        st.error(f"Failed to save rules: {str(e)}")
        return False

def rule_builder_page():
    """Main rule builder page"""
    st.title("Validation Rule Builder")
    st.write("Create and manage validation rules for document types and category-template combinations")
    
    # Initialize session state variables if they don't exist
    if 'validation_rules' not in st.session_state:
        st.session_state.validation_rules = load_validation_rules()
    
    if 'metadata_templates' not in st.session_state:
        st.session_state.metadata_templates = get_metadata_templates()
    
    if 'is_editing_rule' not in st.session_state:
        st.session_state.is_editing_rule = False
        st.session_state.editing_rule_type = ""
        st.session_state.editing_rule_index = -1
        st.session_state.editing_rule_data = {}
    
    # Tabs for document type rules and category-template rules
    tab1, tab2 = st.tabs(["Document Type Rules", "Category-Template Rules"])
    
    with tab1:
        # Document Type Rules
        if st.session_state.is_editing_rule and not st.session_state.editing_rule_data.get("category"):
            # Handle rule editing for document types
            rule_type = st.session_state.editing_rule_type
            doc_type_index = st.session_state.editing_doc_type_index if 'editing_doc_type_index' in st.session_state else 0
            
            if 0 <= doc_type_index < len(st.session_state.validation_rules.get("document_types", [])):
                doc_type = st.session_state.validation_rules["document_types"][doc_type_index]
                
                if rule_type == "field":
                    edit_field_rule(doc_type)
                elif rule_type == "mandatory":
                    edit_mandatory_fields(doc_type)
                elif rule_type == "cross_field":
                    edit_cross_field_rule(doc_type)
                else:
                    st.error(f"Unknown rule type: {rule_type}")
            else:
                st.error("Invalid document type index for editing")
                if st.button("Back to Rules"):
                    st.session_state.is_editing_rule = False
                    st.rerun()
        else:
            # Show list of document types
            st.header("Document Types")
            
            doc_types = st.session_state.validation_rules.get("document_types", [])
            
            if not doc_types:
                st.info("No document types defined. Add a new document type below.")
            else:
                # Display existing document types as selectable buttons
                for i, doc_type in enumerate(doc_types):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        if st.button(f"{doc_type.get('name', 'Unknown')}", key=f"doc_type_{i}", use_container_width=True):
                            st.session_state.editing_doc_type_index = i
                            show_rule_overview(doc_type)
                    
                    with col2:
                        if st.button("Edit", key=f"edit_doc_type_{i}"):
                            st.session_state.editing_doc_type_index = i
                            st.session_state.is_editing_doc_type = True
                            st.rerun()
                    
                    with col3:
                        if st.button("Delete", key=f"delete_doc_type_{i}"):
                            if st.session_state.validation_rules["document_types"][i].get("name") == "default":
                                st.error("Cannot delete the default document type")
                            else:
                                st.session_state.validation_rules["document_types"].pop(i)
                                save_validation_rules(st.session_state.validation_rules)
                                st.success("Document type deleted")
                                st.rerun()
            
            # Add new document type
            st.subheader("Add New Document Type")
            new_doc_type_name = st.text_input("Document Type Name")
            if st.button("Add Document Type") and new_doc_type_name:
                new_doc_type = {
                    "name": new_doc_type_name,
                    "fields": [],
                    "mandatory_fields": [],
                    "cross_field_rules": []
                }
                
                if "document_types" not in st.session_state.validation_rules:
                    st.session_state.validation_rules["document_types"] = []
                
                st.session_state.validation_rules["document_types"].append(new_doc_type)
                save_validation_rules(st.session_state.validation_rules)
                st.success(f"Added document type '{new_doc_type_name}'")
                st.rerun()
    
    with tab2:
        # Category-Template Rules
        if st.session_state.is_editing_rule and st.session_state.editing_rule_data.get("category"):
            # Handle rule editing for category-template combinations
            rule_type = st.session_state.editing_rule_type
            category = st.session_state.editing_rule_data.get("category")
            template_id = st.session_state.editing_rule_data.get("template_id")
            
            # Find the rule set for this category-template combination
            rule_id = f"{category}|{template_id}|base"
            rule_set = st.session_state.validation_rules.get("category_template_rules", {}).get(rule_id, {})
            
            if rule_set:
                if rule_type == "field":
                    edit_category_template_field_rule(rule_set)
                elif rule_type == "mandatory":
                    edit_category_template_mandatory_fields(rule_set)
                elif rule_type == "cross_field":
                    edit_category_template_cross_field_rule(rule_set)
                else:
                    st.error(f"Unknown rule type: {rule_type}")
            else:
                st.error(f"No rule set found for category '{category}' with template '{template_id}'")
                if st.button("Back to Rules"):
                    st.session_state.is_editing_rule = False
                    st.rerun()
        else:
            # Category selection
            st.header("Document Categories")
            categories = get_document_categories()
            
            if not categories:
                st.error("No document categories found. Please define categories first.")
                return
            
            selected_category = st.selectbox(
                "Select Document Category",
                options=["--- Select Category ---"] + categories,
                key="category_selector"
            )
            
            # Template selection (only if category is selected)
            if selected_category != "--- Select Category ---":
                st.header("Metadata Templates")
                
                templates = st.session_state.metadata_templates or {}
                template_options = [(tid, template.get("displayName", tid)) for tid, template in templates.items()]
                
                if not template_options:
                    st.error("No metadata templates found. Please create templates first.")
                    return
                
                template_ids = [t[0] for t in template_options]
                template_names = [t[1] for t in template_options]
                
                selected_template_index = st.selectbox(
                    "Select Metadata Template",
                    options=["--- Select Template ---"] + template_names,
                    key="template_selector"
                )
                
                # Show rule management UI when both category and template are selected
                if selected_template_index != "--- Select Template ---":
                    template_idx = template_names.index(selected_template_index) - 1  # Adjust for the placeholder
                    selected_template_id = template_ids[template_idx]
                    
                    # Check if rules exist for this combination
                    rule_id = f"{selected_category}|{selected_template_id}|base"
                    
                    if "category_template_rules" not in st.session_state.validation_rules:
                        st.session_state.validation_rules["category_template_rules"] = {}
                    
                    # Create empty ruleset if it doesn't exist
                    if rule_id not in st.session_state.validation_rules["category_template_rules"]:
                        st.session_state.validation_rules["category_template_rules"][rule_id] = {
                            "category": selected_category,
                            "template_id": selected_template_id,
                            "fields": [],
                            "mandatory_fields": [],
                            "cross_field_rules": []
                        }
                        save_validation_rules(st.session_state.validation_rules)
                    
                    rule_set = st.session_state.validation_rules["category_template_rules"][rule_id]
                    show_category_template_rule_overview(rule_set)

def show_rule_overview(doc_type: Dict[str, Any]):
    """Show an overview of all rules for a document type"""
    st.header(f"Document Type: {doc_type['name']}")
    
    # 1. Field Rules
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
                "Index": -1
            })
        else:
            for i, rule in enumerate(field_rules):
                field_rules_data.append({
                    "Field": field_key,
                    "Rule Type": rule.get("type", "unknown"),
                    "Description": format_rule_for_display(rule, "field"),
                    "Index": i
                })
    
    field_rules_df = pd.DataFrame(field_rules_data)
    
    if not field_rules_df.empty:
        # Add action buttons
        edit_col, delete_col = st.columns([3, 1])
        with edit_col:
            add_field_rule_key = st.selectbox(
                "Add rule for field",
                options=["--- Select Field ---"] + [field["key"] for field in doc_type.get("fields", [])],
                key="add_field_rule_key"
            )
        
        with delete_col:
            if add_field_rule_key != "--- Select Field ---":
                if st.button("Add Rule", key="add_field_rule_btn"):
                    st.session_state.is_editing_rule = True
                    st.session_state.editing_rule_type = "field"
                    st.session_state.editing_rule_index = -1
                    st.session_state.editing_rule_data = {"field_key": add_field_rule_key}
                    st.rerun()
        
        # Display the field rules in a table
        st.dataframe(field_rules_df[["Field", "Rule Type", "Description"]])
        
        # Edit and delete buttons below the table
        edit_field_col, delete_field_col = st.columns(2)
        with edit_field_col:
            edit_field_rule_index = st.number_input(
                "Rule index to edit", 
                min_value=0, 
                max_value=len(field_rules_data)-1 if field_rules_data else 0,
                value=0,
                key="edit_field_rule_index",
                step=1
            )
            if st.button("Edit Rule", key="edit_field_rule_btn"):
                if field_rules_data:
                    selected_row = field_rules_data[int(edit_field_rule_index)]
                    if selected_row["Rule Type"] != "No rules defined":
                        field_key = selected_row["Field"]
                        rule_index = selected_row["Index"]
                        st.session_state.is_editing_rule = True
                        st.session_state.editing_rule_type = "field"
                        st.session_state.editing_rule_index = rule_index
                        st.session_state.editing_rule_data = {"field_key": field_key}
                        st.rerun()
        
        with delete_field_col:
            delete_field_rule_index = st.number_input(
                "Rule index to delete", 
                min_value=0, 
                max_value=len(field_rules_data)-1 if field_rules_data else 0,
                value=0,
                key="delete_field_rule_index",
                step=1
            )
            if st.button("Delete Rule", key="delete_field_rule_btn"):
                if field_rules_data:
                    selected_row = field_rules_data[int(delete_field_rule_index)]
                    if selected_row["Rule Type"] != "No rules defined":
                        field_key = selected_row["Field"]
                        rule_index = selected_row["Index"]
                        
                        # Find the field definition and delete the rule
                        for field_def in doc_type.get("fields", []):
                            if field_def.get("key") == field_key:
                                if 0 <= rule_index < len(field_def.get("rules", [])):
                                    field_def["rules"].pop(rule_index)
                                    save_validation_rules(st.session_state.validation_rules)
                                    st.success(f"Deleted rule {rule_index} from field '{field_key}'")
                                    st.rerun()
    else:
        st.info("No field rules defined. Use 'Add New Field' to create field rules.")
    
    st.divider()
    
    # 2. Mandatory Fields
    st.subheader("Mandatory Fields")
    mandatory_fields = doc_type.get("mandatory_fields", [])
    
    if mandatory_fields:
        st.write(f"Mandatory fields: {', '.join(mandatory_fields)}")
    else:
        st.info("No mandatory fields defined.")
    
    if st.button("Edit Mandatory Fields"):
        st.session_state.is_editing_rule = True
        st.session_state.editing_rule_type = "mandatory"
        st.rerun()
    
    st.divider()
    
    # 3. Cross-field Rules
    st.subheader("Cross-field Rules")
    cross_field_rules = doc_type.get("cross_field_rules", [])
    
    if cross_field_rules:
        for i, rule in enumerate(cross_field_rules):
            rule_display = format_rule_for_display(rule, "cross_field")
            st.write(f"{i}. {rule_display}")
        
        # Edit and delete buttons
        edit_cross_col, delete_cross_col = st.columns(2)
        with edit_cross_col:
            edit_cross_rule_index = st.number_input(
                "Rule index to edit", 
                min_value=0, 
                max_value=len(cross_field_rules)-1 if cross_field_rules else 0,
                value=0,
                key="edit_cross_rule_index",
                step=1
            )
            if st.button("Edit Cross-field Rule"):
                st.session_state.is_editing_rule = True
                st.session_state.editing_rule_type = "cross_field"
                st.session_state.editing_rule_index = edit_cross_rule_index
                st.rerun()
        
        with delete_cross_col:
            delete_cross_rule_index = st.number_input(
                "Rule index to delete", 
                min_value=0, 
                max_value=len(cross_field_rules)-1 if cross_field_rules else 0,
                value=0,
                key="delete_cross_rule_index",
                step=1
            )
            if st.button("Delete Cross-field Rule"):
                if 0 <= delete_cross_rule_index < len(cross_field_rules):
                    cross_field_rules.pop(delete_cross_rule_index)
                    save_validation_rules(st.session_state.validation_rules)
                    st.success(f"Deleted cross-field rule at index {delete_cross_rule_index}")
                    st.rerun()
    else:
        st.info("No cross-field rules defined.")
    
    if st.button("Add New Cross-field Rule"):
        st.session_state.is_editing_rule = True
        st.session_state.editing_rule_type = "cross_field"
        st.session_state.editing_rule_index = -1
        st.rerun()
    
    # Add new field definition
    st.divider()
    st.subheader("Add New Field Definition")
    new_field_key = st.text_input("Field Key")
    if st.button("Add Field") and new_field_key:
        # Check if field already exists
        existing_fields = [field["key"] for field in doc_type.get("fields", [])]
        if new_field_key in existing_fields:
            st.error(f"Field '{new_field_key}' already exists.")
        else:
            doc_type["fields"].append({"key": new_field_key, "rules": []})
            save_validation_rules(st.session_state.validation_rules)
            st.success(f"Added field '{new_field_key}'")
            st.rerun()

def edit_field_rule(doc_type: Dict[str, Any]):
    """Edit or create a field validation rule"""
    is_new_rule = st.session_state.editing_rule_index == -1
    field_key = st.session_state.editing_rule_data.get("field_key")
    
    # Find the field definition
    field_def = None
    for fd in doc_type.get("fields", []):
        if fd.get("key") == field_key:
            field_def = fd
            break
    
    if not field_def:
        st.error(f"Field '{field_key}' not found.")
        if st.button("Back"):
            st.session_state.is_editing_rule = False
            st.rerun()
        return
    
    st.header(f"{'Add' if is_new_rule else 'Edit'} Field Rule for '{field_key}'")
    
    # Get existing rule if editing
    rule_data = {}
    if not is_new_rule and 0 <= st.session_state.editing_rule_index < len(field_def.get("rules", [])):
        rule_data = field_def["rules"][st.session_state.editing_rule_index]
    
    # Rule type selection
    rule_type = st.selectbox(
        "Rule Type",
        options=list(FIELD_RULE_TYPES.keys()),
        format_func=lambda x: FIELD_RULE_TYPES[x]["label"],
        index=list(FIELD_RULE_TYPES.keys()).index(rule_data.get("type", "regex")) if rule_data.get("type") in FIELD_RULE_TYPES else 0
    )
    
    st.write(FIELD_RULE_TYPES[rule_type]["description"])
    
    # Rule parameters form
    params = {}
    rule_type_info = FIELD_RULE_TYPES[rule_type]
    
    for param in rule_type_info["params"]:
        desc = rule_type_info["param_descriptions"].get(param, "")
        
        if param == "values" and rule_type == "enum":
            # Handle list values for enum
            values_str = st.text_input(
                f"{param} ({desc})",
                value=",".join(rule_data.get("params", {}).get(param, [])) if isinstance(rule_data.get("params", {}).get(param, []), list) else ""
            )
            values_list = [v.strip() for v in values_str.split(",") if v.strip()]
            params[param] = values_list
        elif param == "expected" and rule_type == "dataType":
            # Data type dropdown
            data_types = ["integer", "float", "date", "boolean"]
            params[param] = st.selectbox(
                f"{param} ({desc})",
                options=data_types,
                index=data_types.index(rule_data.get("params", {}).get(param, "integer")) if rule_data.get("params", {}).get(param) in data_types else 0
            )
        elif param == "format" and rule_type == "dataType":
            # Only show format if data type is date
            if params.get("expected") == "date":
                params[param] = st.text_input(
                    f"{param} ({desc})",
                    value=rule_data.get("params", {}).get(param, "%Y-%m-%d")
                )
        else:
            # General parameter input
            params[param] = st.text_input(
                f"{param} ({desc})",
                value=str(rule_data.get("params", {}).get(param, ""))
            )
    
    # Error message
    message = st.text_input(
        "Custom Error Message (optional)",
        value=rule_data.get("message", "")
    )
    
    # Save or cancel
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Rule"):
            new_rule = {
                "type": rule_type,
                "params": params
            }
            if message:
                new_rule["message"] = message
            
            if is_new_rule:
                if "rules" not in field_def:
                    field_def["rules"] = []
                field_def["rules"].append(new_rule)
            else:
                field_def["rules"][st.session_state.editing_rule_index] = new_rule
            
            save_validation_rules(st.session_state.validation_rules)
            st.success(f"{'Added' if is_new_rule else 'Updated'} rule for field '{field_key}'")
            st.session_state.is_editing_rule = False
            st.rerun()
    
    with col2:
        if st.button("Cancel"):
            st.session_state.is_editing_rule = False
            st.rerun()

def edit_mandatory_fields(doc_type: Dict[str, Any]):
    """Edit the list of mandatory fields"""
    st.header(f"Edit Mandatory Fields for '{doc_type['name']}'")
    
    # Get all available fields
    all_fields = [field["key"] for field in doc_type.get("fields", [])]
    current_mandatory = doc_type.get("mandatory_fields", [])
    
    # Multi-select for mandatory fields
    selected_mandatory = st.multiselect(
        "Select Mandatory Fields",
        options=all_fields,
        default=current_mandatory
    )
    
    # Save or cancel
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Mandatory Fields"):
            doc_type["mandatory_fields"] = selected_mandatory
            save_validation_rules(st.session_state.validation_rules)
            st.success(f"Updated mandatory fields for '{doc_type['name']}'")
            st.session_state.is_editing_rule = False
            st.rerun()
    
    with col2:
        if st.button("Cancel"):
            st.session_state.is_editing_rule = False
            st.rerun()

def edit_cross_field_rule(doc_type: Dict[str, Any]):
    """Edit or create a cross-field validation rule"""
    is_new_rule = st.session_state.editing_rule_index == -1
    
    # Get existing rule if editing
    rule_data = {}
    if not is_new_rule and 0 <= st.session_state.editing_rule_index < len(doc_type.get("cross_field_rules", [])):
        rule_data = doc_type["cross_field_rules"][st.session_state.editing_rule_index]
    
    st.header(f"{'Add' if is_new_rule else 'Edit'} Cross-field Rule")
    
    # Rule name
    rule_name = st.text_input(
        "Rule Name",
        value=rule_data.get("name", "")
    )
    
    # Rule type selection
    rule_type = st.selectbox(
        "Rule Type",
        options=list(CROSS_FIELD_RULE_TYPES.keys()),
        format_func=lambda x: CROSS_FIELD_RULE_TYPES[x]["label"],
        index=list(CROSS_FIELD_RULE_TYPES.keys()).index(rule_data.get("type", "dependent_existence")) if rule_data.get("type") in CROSS_FIELD_RULE_TYPES else 0
    )
    
    st.write(CROSS_FIELD_RULE_TYPES[rule_type]["description"])
    
    # Get all available fields
    all_fields = [field["key"] for field in doc_type.get("fields", [])]
    
    # Rule parameters form
    rule_type_info = CROSS_FIELD_RULE_TYPES[rule_type]
    params = {}
    
    if rule_type == "dependent_existence":
        # Fields for dependent_existence rule
        trigger_field = st.selectbox(
            "Trigger Field",
            options=all_fields,
            index=all_fields.index(rule_data.get("trigger_field", all_fields[0])) if rule_data.get("trigger_field") in all_fields else 0
        )
        
        trigger_value = st.text_input(
            "Trigger Value",
            value=rule_data.get("trigger_value", "")
        )
        
        dependent_field = st.selectbox(
            "Dependent Field",
            options=all_fields,
            index=all_fields.index(rule_data.get("dependent_field", all_fields[0])) if rule_data.get("dependent_field") in all_fields else 0
        )
        
        params = {
            "trigger_field": trigger_field,
            "trigger_value": trigger_value,
            "dependent_field": dependent_field
        }
    
    elif rule_type == "date_order":
        # Fields for date_order rule
        date_a_key = st.selectbox(
            "First Date Field",
            options=all_fields,
            index=all_fields.index(rule_data.get("date_a_key", all_fields[0])) if rule_data.get("date_a_key") in all_fields else 0
        )
        
        date_b_key = st.selectbox(
            "Second Date Field",
            options=all_fields,
            index=all_fields.index(rule_data.get("date_b_key", all_fields[0])) if rule_data.get("date_b_key") in all_fields else 0
        )
        
        date_format = st.text_input(
            "Date Format",
            value=rule_data.get("format", "%Y-%m-%d")
        )
        
        order = st.selectbox(
            "Order Relationship",
            options=["a_before_b", "b_before_a"],
            format_func=lambda x: "First date must be before second date" if x == "a_before_b" else "Second date must be before first date",
            index=0 if rule_data.get("order") != "b_before_a" else 1
        )
        
        params = {
            "date_a_key": date_a_key,
            "date_b_key": date_b_key,
            "format": date_format,
            "order": order
        }
    
    # Save or cancel
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Rule"):
            new_rule = {
                "type": rule_type,
                "name": rule_name,
                **params
            }
            
            if is_new_rule:
                if "cross_field_rules" not in doc_type:
                    doc_type["cross_field_rules"] = []
                doc_type["cross_field_rules"].append(new_rule)
            else:
                doc_type["cross_field_rules"][st.session_state.editing_rule_index] = new_rule
            
            save_validation_rules(st.session_state.validation_rules)
            st.success(f"{'Added' if is_new_rule else 'Updated'} cross-field rule")
            st.session_state.is_editing_rule = False
            st.rerun()
    
    with col2:
        if st.button("Cancel"):
            st.session_state.is_editing_rule = False
            st.rerun()
