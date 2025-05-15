"""
Template-specific rule functions for integration with rule_builder.py.
This contains the implementation for working with validation rules that apply
to specific metadata templates.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any
import json

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

def save_validation_rules(rules_data):
    """Save validation rules to config file"""
    try:
        # Ensure we have rule_loader in session state
        if 'rule_loader' not in st.session_state:
            from modules.validation_engine import ValidationRuleLoader
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

def show_template_rule_overview(rule_set: Dict[str, Any]):
    """Show an overview of all rules for a template"""
    template_id = rule_set.get("template_id")
    template_fields = rule_set.get("fields", [])
    mandatory_fields = rule_set.get("mandatory_fields", [])
    
    st.subheader(f"Rules for Template: {template_id}")
    
    # Field Rules Section
    template_field_objects = []
    if "metadata_templates" in st.session_state and template_id in st.session_state.metadata_templates:
        template = st.session_state.metadata_templates[template_id]
        template_field_objects = template.get("fields", [])
        template_fields = [field.get("key", "unknown") for field in template_field_objects]
    
    # 1. Field Rules
    st.subheader("Field Rules")
    field_rules_data = []
    
    # Initialize fields in rule_set if they don't already exist
    if "fields" not in rule_set:
        rule_set["fields"] = []
    
    # Ensure all template fields are represented in the rule set
    existing_field_keys = [field.get("key") for field in rule_set.get("fields", [])]
    for field_key in template_fields:
        if field_key not in existing_field_keys:
            # Add field to rule set
            rule_set["fields"].append({"key": field_key, "rules": []})
    
    # Display field rules
    for field_def in rule_set.get("fields", []):
        field_key = field_def.get("key", "unknown")
        field_rules = field_def.get("rules", [])
        
        if not field_rules:
            field_rules_data.append({
                "Field": field_key,
                "Rule Type": "No rules defined",
                "Description": ""
            })
        else:
            for i, rule in enumerate(field_rules):
                field_rules_data.append({
                    "Field": field_key,
                    "Rule Type": rule.get("type", "unknown"),
                    "Description": format_rule_for_display(rule),
                    "Index": i
                })
    
    if field_rules_data:
        df = pd.DataFrame(field_rules_data)
        st.dataframe(df)
        
        # Add UI to add rules
        col1, col2 = st.columns(2)
        with col1:
            # Select field
            field_to_select = st.selectbox(
                "Select field to add rules for",
                options=template_fields,
                key="field_selector"
            )
        
        with col2:
            # Add field button
            add_field_button = st.button("Add Rule", key="add_field_button")
            if add_field_button and field_to_select:
                st.session_state.editing_field_key = field_to_select
                st.session_state.editing_rule_index = -1
                st.session_state.is_editing_rule = True
                st.rerun()
                
    else:
        st.info("No field rules defined yet. Add rules to fields below.")
        
        # Add a field
        selected_field = st.selectbox("Select field to add rules for", options=template_fields)
        
        if selected_field and st.button("Add Rule for Field"):
            st.session_state.editing_field_key = selected_field
            st.session_state.editing_rule_index = -1
            st.session_state.is_editing_rule = True
            st.rerun()
    
    # Handle rule editing UI
    if st.session_state.get("is_editing_rule", False):
        field_key = st.session_state.editing_field_key
        rule_index = st.session_state.editing_rule_index
        
        st.subheader(f"{'Edit' if rule_index >= 0 else 'Add'} Rule for Field: {field_key}")
        
        # Find the field definition
        field_def = next((f for f in rule_set.get("fields", []) if f.get("key") == field_key), None)
        
        if not field_def:
            # Field doesn't exist yet, create it
            field_def = {"key": field_key, "rules": []}
            rule_set["fields"].append(field_def)
        
        # Get existing rule if editing
        existing_rule = {}
        if rule_index >= 0 and "rules" in field_def and rule_index < len(field_def["rules"]):
            existing_rule = field_def["rules"][rule_index]
        
        # Rule type selection
        rule_type_options = list(FIELD_RULE_TYPES.keys())
        rule_type = st.selectbox(
            "Rule Type",
            options=rule_type_options,
            index=rule_type_options.index(existing_rule.get("type", "regex")) if existing_rule.get("type") in rule_type_options else 0
        )
        
        # Rule parameters based on selected type
        rule_params = {}
        rule_type_info = FIELD_RULE_TYPES.get(rule_type, {})
        
        for param in rule_type_info.get("params", []):
            param_desc = rule_type_info.get("param_descriptions", {}).get(param, param)
            rule_params[param] = st.text_input(
                f"{param} ({param_desc})",
                value=existing_rule.get(param, ""),
                key=f"param_{param}"
            )
        
        # Error message
        error_message = st.text_area(
            "Error Message (shown when validation fails)",
            value=existing_rule.get("message", f"Invalid {field_key}"),
            key="error_message"
        )
        
        # Buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Save Rule"):
                # Create the rule
                new_rule = {
                    "type": rule_type,
                    "message": error_message,
                    **rule_params
                }
                
                # Update or add the rule
                if rule_index >= 0 and "rules" in field_def and rule_index < len(field_def["rules"]):
                    field_def["rules"][rule_index] = new_rule
                else:
                    if "rules" not in field_def:
                        field_def["rules"] = []
                    field_def["rules"].append(new_rule)
                
                # Save the updated validation rules
                save_validation_rules(st.session_state.validation_rules)
                
                # Reset editing state
                st.session_state.is_editing_rule = False
                st.success(f"{'Updated' if rule_index >= 0 else 'Added'} rule for field '{field_key}'")
                st.rerun()
        
        with col2:
            if st.button("Cancel"):
                st.session_state.is_editing_rule = False
                st.rerun()
    
    # Add rule deletion UI
    if field_rules_data and not st.session_state.get("is_editing_rule", False):
        st.subheader("Delete Rules")
        
        # Get fields that have rules
        fields_with_rules = []
        field_rule_counts = {}
        
        for data in field_rules_data:
            if data["Rule Type"] != "No rules defined":
                field_key = data["Field"]
                if field_key not in fields_with_rules:
                    fields_with_rules.append(field_key)
                    field_rule_counts[field_key] = 1
                else:
                    field_rule_counts[field_key] += 1
        
        if fields_with_rules:
            col1, col2 = st.columns(2)
            
            with col1:
                # Select field to delete rules from
                selected_field = st.selectbox(
                    "Select Field",
                    options=fields_with_rules,
                    key="delete_field_selector"
                )
                
                # Get the number of rules for this field
                rule_count = field_rule_counts.get(selected_field, 0)
                
                if rule_count > 0:
                    rule_index = st.number_input(
                        "Rule Index",
                        min_value=0,
                        max_value=rule_count - 1,
                        value=0,
                        key="delete_rule_index"
                    )
                else:
                    st.info(f"No rules to delete for field '{selected_field}'")
            
            with col2:
                if rule_count > 0 and st.button("Delete Rule"):
                    # Find the field and delete the rule
                    field_def = next((f for f in rule_set.get("fields", []) if f.get("key") == selected_field), None)
                    
                    if field_def and "rules" in field_def and 0 <= rule_index < len(field_def["rules"]):
                        field_def["rules"].pop(int(rule_index))
                        save_validation_rules(st.session_state.validation_rules)
                        st.success(f"Deleted rule {rule_index} from field '{selected_field}'")
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
    
    # Add UI to manage mandatory fields
    col1, col2 = st.columns(2)
    
    with col1:
        field_options = [f for f in template_fields if f not in mandatory_fields]
        if field_options:
            field_to_add = st.selectbox("Add Mandatory Field", options=field_options, key="mandatory_field_add")
            if st.button("Add as Mandatory"):
                mandatory_fields.append(field_to_add)
                rule_set["mandatory_fields"] = mandatory_fields
                save_validation_rules(st.session_state.validation_rules)
                st.success(f"Added '{field_to_add}' as mandatory field")
                st.rerun()
        else:
            st.info("All fields are already marked as mandatory")
    
    with col2:
        if mandatory_fields:
            field_to_remove = st.selectbox("Remove Mandatory Field", options=mandatory_fields, key="mandatory_field_remove")
            if st.button("Remove from Mandatory"):
                mandatory_fields.remove(field_to_remove)
                rule_set["mandatory_fields"] = mandatory_fields
                save_validation_rules(st.session_state.validation_rules)
                st.success(f"Removed '{field_to_remove}' from mandatory fields")
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
