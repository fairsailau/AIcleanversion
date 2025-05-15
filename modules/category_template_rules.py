"""
Template-specific rule functions for integration with rule_builder.py.
This contains the implementation for working with validation rules that apply
to specific metadata templates.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any
import json

def show_template_rule_overview(rule_set: Dict[str, Any]):
    """Show an overview of all rules for a template"""
    template_id = rule_set.get("template_id", "Unknown Template")
    
    # Get template name for display
    template_name = template_id
    if "metadata_templates" in st.session_state and template_id in st.session_state.metadata_templates:
        template = st.session_state.metadata_templates[template_id]
        template_name = template.get("displayName", template_id)
    
    st.header(f"Rules for Template: {template_name}")
    
    # Get template fields if available
    template_fields = []
    if "metadata_templates" in st.session_state and template_id in st.session_state.metadata_templates:
        template = st.session_state.metadata_templates[template_id]
        template_fields = [field.get("key", "unknown") for field in template.get("fields", [])]
    
    # 1. Field Rules
    st.subheader("Field Rules")
    field_rules_data = []
    
    for field_def in rule_set.get("fields", []):
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
    
    # Field selector - prioritize template fields if available
    available_fields = template_fields if template_fields else ["custom_field_1", "custom_field_2"]
    
    # Get existing field keys to avoid duplicates
    existing_field_keys = [field.get("key", "") for field in rule_set.get("fields", [])]
    available_fields = [f for f in available_fields if f not in existing_field_keys]
    
    # Add field selector
    add_col1, add_col2 = st.columns([3, 1])
    with add_col1:
        new_field_key = st.selectbox(
            "Select field to add rules for",
            options=["--- Select Field ---"] + available_fields,
            key="new_category_template_field"
        )
    
    with add_col2:
        if new_field_key != "--- Select Field ---":
            if st.button("Add Field", key="add_category_template_field_btn"):
                if "fields" not in rule_set:
                    rule_set["fields"] = []
                    
                rule_set["fields"].append({"key": new_field_key, "rules": []})
                save_validation_rules(st.session_state.validation_rules)
                st.success(f"Added field '{new_field_key}'")
                st.rerun()
    
    # Add rule for existing field
    if existing_field_keys:
        add_rule_col1, add_rule_col2 = st.columns([3, 1])
        with add_rule_col1:
            add_rule_field = st.selectbox(
                "Add rule for existing field",
                options=["--- Select Field ---"] + existing_field_keys,
                key="add_rule_for_field"
            )
        
        with add_rule_col2:
            if add_rule_field != "--- Select Field ---":
                if st.button("Add Rule", key="add_field_rule_to_existing"):
                    st.session_state.is_editing_rule = True
                    st.session_state.editing_rule_type = "field"
                    st.session_state.editing_rule_index = -1
                    st.session_state.editing_rule_data = {
                        "field_key": add_rule_field,
                        "category": category,
                        "template_id": template_id
                    }
                    st.rerun()
    
    # Display existing field rules
    if not field_rules_df.empty:
        st.dataframe(field_rules_df[["Field", "Rule Type", "Description"]])
        
        # Edit and delete buttons
        edit_rule_col, delete_rule_col = st.columns(2)
        with edit_rule_col:
            if len(field_rules_data) > 0:
                edit_rule_index = st.number_input(
                    "Rule index to edit", 
                    min_value=0, 
                    max_value=len(field_rules_data)-1,
                    value=0,
                    key="edit_category_template_rule_index",
                    step=1
                )
                if st.button("Edit Rule", key="edit_category_template_rule_btn"):
                    selected_row = field_rules_data[int(edit_rule_index)]
                    if selected_row["Rule Type"] != "No rules defined":
                        field_key = selected_row["Field"]
                        rule_index = selected_row["Index"]
                        st.session_state.is_editing_rule = True
                        st.session_state.editing_rule_type = "field"
                        st.session_state.editing_rule_index = rule_index
                        st.session_state.editing_rule_data = {
                            "field_key": field_key,
                            "category": category,
                            "template_id": template_id
                        }
                        st.rerun()
        
        with delete_rule_col:
            if len(field_rules_data) > 0:
                delete_rule_index = st.number_input(
                    "Rule index to delete", 
                    min_value=0, 
                    max_value=len(field_rules_data)-1,
                    value=0,
                    key="delete_category_template_rule_index",
                    step=1
                )
                if st.button("Delete Rule", key="delete_category_template_rule_btn"):
                    selected_row = field_rules_data[int(delete_rule_index)]
                    if selected_row["Rule Type"] != "No rules defined":
                        field_key = selected_row["Field"]
                        rule_index = selected_row["Index"]
                        
                        # Find the field definition and delete the rule
                        for field_def in rule_set.get("fields", []):
                            if field_def.get("key") == field_key:
                                if 0 <= rule_index < len(field_def.get("rules", [])):
                                    field_def["rules"].pop(rule_index)
                                    save_validation_rules(st.session_state.validation_rules)
                                    st.success(f"Deleted rule {rule_index} from field '{field_key}'")
                                    st.rerun()
    else:
        st.info("No field rules defined yet. Add fields and rules above.")
    
    st.divider()
    
    # 2. Mandatory Fields
    st.subheader("Mandatory Fields")
    mandatory_fields = rule_set.get("mandatory_fields", [])
    
    if mandatory_fields:
        st.write(f"Mandatory fields: {', '.join(mandatory_fields)}")
    else:
        st.info("No mandatory fields defined.")
    
    if st.button("Edit Mandatory Fields", key="edit_category_template_mandatory"):
        st.session_state.is_editing_rule = True
        st.session_state.editing_rule_type = "mandatory"
        st.session_state.editing_rule_data = {
            "category": category,
            "template_id": template_id
        }
        st.rerun()
    
    st.divider()
    
    # 3. Cross-field Rules
    st.subheader("Cross-field Rules")
    cross_field_rules = rule_set.get("cross_field_rules", [])
    
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
                key="edit_category_template_cross_rule_index",
                step=1
            )
            if st.button("Edit Cross-field Rule", key="edit_category_template_cross_rule_btn"):
                st.session_state.is_editing_rule = True
                st.session_state.editing_rule_type = "cross_field"
                st.session_state.editing_rule_index = edit_cross_rule_index
                st.session_state.editing_rule_data = {
                    "category": category,
                    "template_id": template_id
                }
                st.rerun()
        
        with delete_cross_col:
            delete_cross_rule_index = st.number_input(
                "Rule index to delete", 
                min_value=0, 
                max_value=len(cross_field_rules)-1 if cross_field_rules else 0,
                value=0,
                key="delete_category_template_cross_rule_index",
                step=1
            )
            if st.button("Delete Cross-field Rule", key="delete_category_template_cross_rule_btn"):
                if 0 <= delete_cross_rule_index < len(cross_field_rules):
                    cross_field_rules.pop(delete_cross_rule_index)
                    save_validation_rules(st.session_state.validation_rules)
                    st.success(f"Deleted cross-field rule at index {delete_cross_rule_index}")
                    st.rerun()
    else:
        st.info("No cross-field rules defined.")
    
    if st.button("Add New Cross-field Rule", key="add_category_template_cross_rule_btn"):
        st.session_state.is_editing_rule = True
        st.session_state.editing_rule_type = "cross_field"
        st.session_state.editing_rule_index = -1
        st.session_state.editing_rule_data = {
            "category": category,
            "template_id": template_id
        }
        st.rerun()

def edit_category_template_field_rule(rule_set: Dict[str, Any]):
    """Edit or create a field validation rule for a category-template combination"""
    is_new_rule = st.session_state.editing_rule_index == -1
    field_key = st.session_state.editing_rule_data.get("field_key")
    category = st.session_state.editing_rule_data.get("category")
    template_id = st.session_state.editing_rule_data.get("template_id")
    
    # Find the field definition
    field_def = None
    for fd in rule_set.get("fields", []):
        if fd.get("key") == field_key:
            field_def = fd
            break
    
    if not field_def:
        st.error(f"Field '{field_key}' not found.")
        if st.button("Back"):
            st.session_state.is_editing_rule = False
            st.rerun()
        return
    
    # Get template name for display
    template_name = template_id
    if "metadata_templates" in st.session_state and template_id in st.session_state.metadata_templates:
        template = st.session_state.metadata_templates[template_id]
        template_name = template.get("displayName", template_id)
    
    st.header(f"{'Add' if is_new_rule else 'Edit'} Field Rule")
    st.subheader(f"Category: {category}, Template: {template_name}, Field: {field_key}")
    
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

def edit_category_template_mandatory_fields(rule_set: Dict[str, Any]):
    """Edit the list of mandatory fields for a category-template combination"""
    category = rule_set.get("category", "Unknown Category")
    template_id = rule_set.get("template_id", "Unknown Template")
    
    # Get template name for display
    template_name = template_id
    if "metadata_templates" in st.session_state and template_id in st.session_state.metadata_templates:
        template = st.session_state.metadata_templates[template_id]
        template_name = template.get("displayName", template_id)
    
    st.header(f"Edit Mandatory Fields")
    st.subheader(f"Category: {category}, Template: {template_name}")
    
    # Get all available fields
    all_fields = [field["key"] for field in rule_set.get("fields", [])]
    
    # Add template fields if available
    if "metadata_templates" in st.session_state and template_id in st.session_state.metadata_templates:
        template = st.session_state.metadata_templates[template_id]
        template_fields = [field.get("key", "unknown") for field in template.get("fields", [])]
        for field in template_fields:
            if field not in all_fields:
                all_fields.append(field)
    
    current_mandatory = rule_set.get("mandatory_fields", [])
    
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
            rule_set["mandatory_fields"] = selected_mandatory
            save_validation_rules(st.session_state.validation_rules)
            st.success(f"Updated mandatory fields for {category} with template {template_name}")
            st.session_state.is_editing_rule = False
            st.rerun()
    
    with col2:
        if st.button("Cancel"):
            st.session_state.is_editing_rule = False
            st.rerun()

def edit_category_template_cross_field_rule(rule_set: Dict[str, Any]):
    """Edit or create a cross-field validation rule for a category-template combination"""
    is_new_rule = st.session_state.editing_rule_index == -1
    category = rule_set.get("category", "Unknown Category")
    template_id = rule_set.get("template_id", "Unknown Template")
    
    # Get template name for display
    template_name = template_id
    if "metadata_templates" in st.session_state and template_id in st.session_state.metadata_templates:
        template = st.session_state.metadata_templates[template_id]
        template_name = template.get("displayName", template_id)
    
    # Get existing rule if editing
    rule_data = {}
    if not is_new_rule and 0 <= st.session_state.editing_rule_index < len(rule_set.get("cross_field_rules", [])):
        rule_data = rule_set["cross_field_rules"][st.session_state.editing_rule_index]
    
    st.header(f"{'Add' if is_new_rule else 'Edit'} Cross-field Rule")
    st.subheader(f"Category: {category}, Template: {template_name}")
    
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
    
    # Get all available fields from both the rule set and the template
    all_fields = [field["key"] for field in rule_set.get("fields", [])]
    
    # Add template fields if available
    if "metadata_templates" in st.session_state and template_id in st.session_state.metadata_templates:
        template = st.session_state.metadata_templates[template_id]
        template_fields = [field.get("key", "unknown") for field in template.get("fields", [])]
        for field in template_fields:
            if field not in all_fields:
                all_fields.append(field)
    
    if not all_fields:
        all_fields = ["field1", "field2"]  # Fallback
    
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
                if "cross_field_rules" not in rule_set:
                    rule_set["cross_field_rules"] = []
                rule_set["cross_field_rules"].append(new_rule)
            else:
                rule_set["cross_field_rules"][st.session_state.editing_rule_index] = new_rule
            
            save_validation_rules(st.session_state.validation_rules)
            st.success(f"{'Added' if is_new_rule else 'Updated'} cross-field rule")
            st.session_state.is_editing_rule = False
            st.rerun()
    
    with col2:
        if st.button("Cancel"):
            st.session_state.is_editing_rule = False
            st.rerun()

def manage_template_rules():
    """Main entry point for managing validation rules for templates."""
    st.subheader("Template Rules")
    st.write("Manage validation rules specific to metadata templates.")
    
    # Initialize the rule loader if it's not already in the session state
    if 'rule_loader' not in st.session_state:
        from modules.validation_engine import ValidationRuleLoader
        st.session_state.rule_loader = ValidationRuleLoader(rules_config_path='config/validation_rules.json')
    
    # Initialize validation_rules in session state if not present
    if 'validation_rules' not in st.session_state:
        if hasattr(st.session_state.rule_loader, 'rules'):
            st.session_state.validation_rules = st.session_state.rule_loader.rules
        else:
            st.session_state.validation_rules = {"template_rules": []}
    
    # Get metadata templates
    templates = []
    if 'metadata_templates' in st.session_state:
        templates = list(st.session_state.metadata_templates.items())
    
    if not templates:
        st.warning("No metadata templates found. Please configure metadata templates first.")
        return
    
    # Allow user to select template
    selected_template = st.selectbox(
        "Select Metadata Template",
        options=[f"{template[1].get('displayName', template[0])} ({template[0]})" for template in templates],
        index=0 if templates else None
    )
    
    if selected_template:
        # Extract template_id from the selection string
        template_id = selected_template.split("(")[-1].rstrip(")")
        
        # Get existing rule set or create new one
        template_rules = []
        if "template_rules" in st.session_state.validation_rules:
            template_rules = st.session_state.validation_rules["template_rules"]
        
        template_rule = next((rule for rule in template_rules if rule.get("template_id") == template_id), None)
        
        if not template_rule:
            # Create new rule set for this template
            template_rule = {
                "template_id": template_id,
                "fields": [],
                "mandatory_fields": []
            }
            template_rules.append(template_rule)
            st.session_state.validation_rules["template_rules"] = template_rules
        
        # Show the rule set overview
        show_template_rule_overview(template_rule)
    else:
        st.warning("Please select a metadata template to manage rules.")
    
    # Add button to save rules
    if st.button("Save Template Rules"):
        try:
            save_validation_rules(st.session_state.validation_rules)
            st.success("Template rules saved successfully.")
        except Exception as e:
            st.error(f"Error saving rules: {e}")

# Note: Main entry point functions are now defined in rule_builder.py
# This file is only for category-template specific rule management functions

# Backward compatibility functions to avoid import errors in deployment
def manage_category_template_rules():
    """Backward compatibility wrapper for manage_template_rules"""
    return manage_template_rules()

def show_category_template_rule_overview(rule_set):
    """Backward compatibility wrapper for show_template_rule_overview"""
    return show_template_rule_overview(rule_set)
