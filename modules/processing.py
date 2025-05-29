import streamlit as st
import pandas as pd
import logging
import os
import time
import random
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from modules.metadata_extraction import get_extraction_functions
from modules.validation_engine import ValidationRuleLoader, Validator
from modules.validation_engine import ConfidenceAdjuster

logger = logging.getLogger(__name__)

def map_document_type_to_template(doc_type, template_mappings):
    """Map a document type to its corresponding metadata template"""
    # Check if this document type exists in our mappings
    template_id = template_mappings.get(doc_type)
    if template_id:
        logger.info(f"Found template mapping for document type {doc_type}: {template_id}")
        return template_id
    
    # No mapping found, fallback to default
    logger.warning(f"No template mapping found for document type {doc_type}. Using fallback.")
    return template_mappings.get("Default")

def get_metadata_template_id(file_id, file_name, template_config):
    """
    Determine which metadata template to use for the given file
    
    Args:
        file_id: Box file ID
        file_name: File name for logging
        template_config: Configuration containing template selection strategy
    
    Returns:
        template_id: The determined template ID or None if not applicable
    """
    # First check if we have document categorization results
    doc_type = None
    if 'document_categorization' in st.session_state and 'results' in st.session_state.document_categorization:
        if file_id in st.session_state.document_categorization['results']:
            cat_result = st.session_state.document_categorization['results'][file_id]
            # The category field might be named 'category' or 'document_type' depending on implementation
            doc_type = cat_result.get('category') or cat_result.get('document_type')
            logger.info(f"Found document type for file {file_name}: {doc_type}")
    
    # If we have a document type and document-to-template mappings, use that
    if doc_type and hasattr(st.session_state, 'document_type_to_template'):
        template_id = st.session_state.document_type_to_template.get(doc_type)
        if template_id:
            logger.info(f"Using template for document type {doc_type}: {template_id}")
            return template_id
    
    # Otherwise, use the direct template from metadata_config
    template_id = template_config.get("template_id")
    logger.info(f"Using direct template: {template_id}")
    return template_id
def get_metadata_template_id(file_id, file_name, template_config):
    """
    Determine which metadata template to use for the given file
    
    Args:
        file_id: Box file ID
        file_name: File name for logging
        template_config: Configuration containing template selection strategy
    
    Returns:
        template_id: The determined template ID or None if not applicable
    """
    # First check if we have document categorization results
    doc_type = None
    if 'document_categorization' in st.session_state and 'results' in st.session_state.document_categorization:
        if file_id in st.session_state.document_categorization['results']:
            cat_result = st.session_state.document_categorization['results'][file_id]
            # The category field might be named 'category' or 'document_type' depending on implementation
            doc_type = cat_result.get('category') or cat_result.get('document_type')
            logger.info(f"Found document type for file {file_name}: {doc_type}")
    
    # If we have a document type and document-to-template mappings, use that
    if doc_type and hasattr(st.session_state, 'document_type_to_template'):
        template_id = st.session_state.document_type_to_template.get(doc_type)
        if template_id:
            logger.info(f"Using template for document type {doc_type}: {template_id}")
            return template_id
    
    # Otherwise, use the direct template from metadata_config
    template_id = template_config.get("template_id")
    logger.info(f"Using direct template: {template_id}")
    return template_id

def get_metadata_template_id(file_id, file_name, template_config):
    """
    Determine which metadata template to use for the given file
    
    Args:
        file_id: Box file ID
        file_name: File name for logging
        template_config: Configuration containing template selection strategy
    
    Returns:
        template_id: The determined template ID or None if not applicable
    """
    # First check if we have document categorization results
    doc_type = None
    if 'document_categorization' in st.session_state and 'results' in st.session_state.document_categorization:
        if file_id in st.session_state.document_categorization['results']:
            cat_result = st.session_state.document_categorization['results'][file_id]
            # The category field might be named 'category' or 'document_type' depending on implementation
            doc_type = cat_result.get('category') or cat_result.get('document_type')
            logger.info(f"Found document type for file {file_name}: {doc_type}")
    
    # If we have a document type and document-to-template mappings, use that
    if doc_type and hasattr(st.session_state, 'document_type_to_template'):
        template_id = st.session_state.document_type_to_template.get(doc_type)
        if template_id:
            logger.info(f"Using template for document type {doc_type}: {template_id}")
            return template_id
    
    # Otherwise, use the direct template from metadata_config
    template_id = template_config.get("template_id")
    logger.info(f"Using direct template: {template_id}")
    return template_id

def get_fields_for_ai_from_template(scope, template_key):
    """
    Extract field definitions from a Box metadata template to prepare for AI extraction
    
    Returns:
        List of field definitions to pass to AI model
    """
    if scope is None or template_key is None:
        logger.error(f"Invalid scope ({scope}) or template_key ({template_key})")
        return None
    
    # Get schema with descriptions for AI context
    schema_details = None 
    
    # Check if we have a cached schema for this template
    cache_key = f"{scope}/{template_key}"
    if 'schema_cache' not in st.session_state:
        st.session_state.schema_cache = {}
        
    if cache_key in st.session_state.schema_cache:
        logger.info(f"Using cached schema for {cache_key}")
        schema_details = st.session_state.schema_cache[cache_key]
    else:
        # Fetch schema from Box
        try:
            client = st.session_state.client
            schema = client.metadata_template(scope, template_key).get()
            
            # Box API returns a MetadataTemplate object that needs conversion to dictionary
            if hasattr(schema, 'fields') and not isinstance(schema, dict):
                # Convert MetadataTemplate object to dictionary format expected by the rest of the code
                temp_fields = []
                for field_item in schema.fields: # field_item is an item from schema.fields
                    field_dict_to_add = {}
                    attributes_to_copy = ['key', 'type', 'displayName', 'description', 'options']

                    if isinstance(field_item, dict): # If the item from schema.fields is already a dictionary
                        for attr_key in attributes_to_copy:
                            if attr_key in field_item:
                                field_dict_to_add[attr_key] = field_item[attr_key]
                        if not field_dict_to_add.get('key'): # Check if key was actually copied
                             logger.warning(f"Item from schema.fields was a dict but missing 'key': {str(field_item)[:500]}. Template: '{template_key}'.")
                    elif hasattr(field_item, '_response_object') and isinstance(field_item._response_object, dict): # It's an SDK obj with _response_object
                        source_dict = field_item._response_object
                        for attr_key in attributes_to_copy:
                            if attr_key in source_dict:
                                field_dict_to_add[attr_key] = source_dict[attr_key]
                        if not field_dict_to_add.get('key'):
                             logger.warning(f"SDK object's _response_object missing 'key': {str(source_dict)[:500]}. Template: '{template_key}'.")
                    # Fallback for SDK objects that might not use _response_object but have direct attributes
                    elif not isinstance(field_item, dict): # Ensure it's not a dict before trying general hasattr/getattr
                         for attr_key in attributes_to_copy:
                            if hasattr(field_item, attr_key): # Check direct attribute
                                field_dict_to_add[attr_key] = getattr(field_item, attr_key)
                         if not field_dict_to_add.get('key'):
                             logger.warning(f"SDK object did not yield a 'key' through direct attributes. Item type: {type(field_item)}. Template: '{template_key}'.")
                    else: # Should not be reached if above logic is comprehensive for dict/SDK obj
                        logger.warning(f"Unrecognized item type '{type(field_item)}' in schema.fields. Item: {str(field_item)[:1000]}. Template: '{template_key}'.")
                    
                    temp_fields.append(field_dict_to_add)
                
                schema_details = {
                    'displayName': getattr(schema, 'displayName', template_key),
                    'fields': temp_fields
                }
                logger.info(f"Converted MetadataTemplate object to dictionary with {len(temp_fields)} fields")
            else:
                # It's already a dictionary or some other format
                schema_details = schema
            
            # Cache the schema
            st.session_state.schema_cache[cache_key] = schema_details
            logger.info(f"Successfully fetched and cached schema (with descriptions) for {cache_key}")
        except Exception as e:
            logger.error(f"Error fetching metadata schema {scope}/{template_key}: {e}")
            return None
    
    # Process the schema to extract fields
    if schema_details is None:
        logger.error(f"Schema for {scope}/{template_key} is None (either from cache or post-fetch).")
        return None

    # Check if schema_details is a processable type (dict with 'fields' or object with 'fields')
    is_dict_with_fields = isinstance(schema_details, dict) and 'fields' in schema_details
    is_object_with_fields = hasattr(schema_details, 'fields') and not isinstance(schema_details, dict)

    if is_dict_with_fields or is_object_with_fields:
        logger.info(f"Processing schema for {scope}/{template_key}: Type: {type(schema_details)}")
        ai_fields = [] 
        fields_list_to_iterate = []

        if is_dict_with_fields:
            fields_list_to_iterate = schema_details.get('fields', [])
            logger.info(f"Schema is a dict. Found {len(fields_list_to_iterate)} potential fields in schema_details['fields'].")
        elif is_object_with_fields: 
            fields_list_to_iterate = schema_details.fields
            logger.info(f"Schema is an object. Found {len(fields_list_to_iterate)} potential fields in schema_details.fields.")
            
        for field_obj in fields_list_to_iterate:
            # field_for_ai = {} # Removed unconditional initialization

            if isinstance(field_obj, dict):
                field_key = field_obj.get('key') 
                if not field_key: 
                    logger.warning(f"Skipping a field (from dict) due to missing 'key': {str(field_obj)[:500]}. Template: '{template_key}'.") 
                    continue
                
                field_for_ai = {'key': field_key} # Initialize here
                
                attributes_to_copy = ['type', 'displayName', 'description', 'options']
                for attr_to_copy in attributes_to_copy:
                    if attr_to_copy in field_obj:
                        field_for_ai[attr_to_copy] = field_obj[attr_to_copy]
                
                if 'displayName' not in field_for_ai:
                    field_for_ai['displayName'] = field_key
                if 'type' not in field_for_ai:
                    field_for_ai['type'] = 'string'
                
                ai_fields.append(field_for_ai) # Append here, inside the if block

            elif hasattr(field_obj, 'key'): # Handles SDK objects or other objects with direct attributes
                field_key = getattr(field_obj, 'key', None)
                if not field_key:
                   logger.warning(f"Skipping SDK object field due to missing 'key': {str(field_obj)[:500]}. Template: '{template_key}'.")
                   continue
                field_for_ai = {'key': field_key}
                attributes_to_copy = ['type', 'displayName', 'description', 'options']
                for attr_to_copy in attributes_to_copy:
                   if hasattr(field_obj, attr_to_copy):
                       field_for_ai[attr_to_copy] = getattr(field_obj, attr_to_copy)
                if 'displayName' not in field_for_ai:
                   field_for_ai['displayName'] = field_key
                if 'type' not in field_for_ai:
                   field_for_ai['type'] = 'string'
                ai_fields.append(field_for_ai)
            else: 
                logger.warning(f"Skipping field due to unrecognized format or it's not a dict/SDK object with a key. Type: {type(field_obj)}, Content: {str(field_obj)[:500]}. Template: '{template_key}'.")
                # No append here, as field_for_ai was not successfully populated.
                
        if not ai_fields and fields_list_to_iterate: # Log if fields were present but none were suitable for AI
            logger.warning(f"Template {scope}/{template_key} had {len(fields_list_to_iterate)} items in its fields list, but no AI-suitable fields were extracted. Check field structure and logs.")
        elif not fields_list_to_iterate: # Log if the schema itself had no fields defined
             logger.warning(f"Template {scope}/{template_key} had no fields in its definition (fields_list was empty).")

        logger.info(f"Extracted {len(ai_fields)} AI fields from template schema {scope}/{template_key}: {json.dumps(ai_fields, indent=2)}")
        return ai_fields
    
    else: # Handles cases where schema_details is not None, but not processable (e.g., empty dict, unexpected type)
        logger.warning(f"Schema for {scope}/{template_key} is present but not in a processable format (e.g., empty dict, wrong type). Schema content: {schema_details}")
        # Return a placeholder field instead of empty list to prevent processing from stopping
        return [{'key': 'placeholder', 'type': 'string', 'displayName': 'Placeholder Field'}]

def process_files_with_progress(files_to_process: List[Dict[str, Any]], extraction_functions: Dict[str, Any], batch_size: int, processing_mode: str):
    """
    Processes files, calling the appropriate extraction function with targeted template info.
    Updates st.session_state.extraction_results and st.session_state.processing_state.
    """
    total_files = len(files_to_process)
    st.session_state.processing_state['total_files'] = total_files
    processed_count = 0
    client = st.session_state.client
    metadata_config = st.session_state.get('metadata_config', {})
    ai_model = metadata_config.get('ai_model', 'azure__openai__gpt_4o_mini') # Default model

    for i, file_data in enumerate(files_to_process):
        if not st.session_state.processing_state.get('is_processing', False):
            logger.info('Processing cancelled by user during extraction.')
            break
        
        file_id = str(file_data['id'])
        file_name = file_data.get('name', f'File {file_id}')
        st.session_state.processing_state['current_file_index'] = i
        st.session_state.processing_state['current_file'] = file_name
        logger.info(f'Starting extraction for file {i + 1}/{total_files}: {file_name} (ID: {file_id})')

        current_doc_type = None
        # Check for document categorization results directly in session_state
        categorization_results = st.session_state.get('document_categorization', {}).get('results', {}) # Corrected to get nested results
        cat_result = categorization_results.get(file_id)
        if cat_result:
            current_doc_type = cat_result.get('category')
            logger.debug(f"Found document type for file {file_id}: {current_doc_type}")
        
        try:
            # Determine target template (if applicable)
            target_template_id = None
            
            if processing_mode == 'structured':
                # For structured mode, we need to have a metadata template
                target_template_id = get_metadata_template_id(file_id, file_name, metadata_config)
                if not target_template_id:
                    logger.error(f"Failed to determine metadata template for file {file_name}. Skipping file.")
                    continue
                
                # Parse template ID to extract scope and key
                # Template IDs from Box are in format: enterprise_<ID>_<template_key>
                # But metadata API requires scope and template_key separately
                
                logger.info(f"Processing template ID: {target_template_id}")
                
                if target_template_id.startswith('enterprise_'):
                    # For enterprise_336904155_tax format
                    try:
                        # Format is enterprise_ID_key
                        parts = target_template_id.split('_', 2)
                        if len(parts) >= 3:
                            scope = 'enterprise'
                            template_key = parts[2]  # Just the key part
                        else:
                            # If we can't split it correctly, use defaults
                            scope = 'enterprise'
                            template_key = target_template_id
                    except Exception as e:
                        logger.error(f"Error parsing template ID {target_template_id}: {e}")
                        scope = 'enterprise'
                        template_key = target_template_id
                else:
                    # For any other format
                    scope = 'enterprise'
                    template_key = target_template_id
                
                logger.info(f"Using scope: {scope}, template_key: {template_key}")
                
                # Get fields from template
                template_fields = get_fields_for_ai_from_template(scope, template_key)
                if not template_fields:
                    logger.error(f"Failed to extract fields from template {target_template_id} for file {file_name}. Skipping.")
                    continue
                
                logger.info(f"File {file_name}: Extracting structured data using template {target_template_id} with fields: {template_fields}")
                
                # Use appropriate extraction function if available
                extraction_func = extraction_functions.get('structured')
                if not extraction_func:
                    logger.error(f"No extraction function for structured mode. Skipping file {file_name}.")
                    continue
                    
                # Perform the extraction
                # Fix parameter names to match the function signature in metadata_extraction.py
                metadata_template = {
                    'scope': scope,
                    'template_key': template_key,
                    'id': target_template_id
                }
                extracted_metadata = extraction_func(
                    client=client,
                    file_id=file_id, 
                    fields=template_fields,
                    metadata_template=metadata_template,
                    ai_model=ai_model
                )
                logger.info(f"File {file_name} ({file_id}): Raw extracted metadata with confidences: {json.dumps(extracted_metadata, indent=2)}")
                
                # Validate the extracted metadata
                
                doc_category = None
                if 'document_categorization' in st.session_state and file_id in st.session_state.document_categorization:
                    doc_category_result = st.session_state.document_categorization.get(file_id, {})
                    doc_category = doc_category_result.get('category')
                
                # Ensure template_id_for_validation is properly defined
                template_id_for_validation = None
                if processing_mode == 'structured':
                    template_id_for_validation = target_template_id  # Set the template_id_for_validation here
                
                logger.info(f"Validating with template_id={template_id_for_validation}, doc_category={doc_category}")
                
                # Use the enhanced validation method that supports category-template specific rules
                validation_output = st.session_state.validator.validate(
                    ai_response=extracted_metadata,
                    doc_type=None,  # doc_type is no longer used in validation
                    doc_category=doc_category,
                    template_id=template_id_for_validation
                )
                
                logger.info(f"File {file_name} ({file_id}): Data before confidence adjustment: {json.dumps(extracted_metadata, indent=2)}")
                logger.info(f"File {file_name} ({file_id}): Validation output for confidence adjustment: {json.dumps(validation_output, indent=2)}")

                # --- Restructure extracted_metadata for ConfidenceAdjuster (Issue 1) ---
                data_for_adjuster = {}
                if isinstance(extracted_metadata, dict):
                    for temp_field_key, temp_field_val in extracted_metadata.items():
                        if not temp_field_key.endswith("_confidence"): # Process only primary data fields
                            value_str = str(temp_field_val) # Ensure value is string
                            confidence_key_for_field = f"{temp_field_key}_confidence"
                            confidence_str = str(extracted_metadata.get(confidence_key_for_field, "Low"))
                            if not confidence_str: confidence_str = "Low" # Handle empty string

                            data_for_adjuster[temp_field_key] = {
                                "value": value_str,
                                "confidence": confidence_str 
                            }
                
                logger.info(f"File {file_name} ({file_id}): Data structured for confidence adjuster: {json.dumps(data_for_adjuster, indent=2)}")
                
                confidence_output = st.session_state.confidence_adjuster.adjust_confidence(data_for_adjuster, validation_output)
                logger.info(f"File {file_name} ({file_id}): Adjusted confidence output from adjuster: {json.dumps(confidence_output, indent=2)}")
                overall_status_info = st.session_state.confidence_adjuster.get_overall_document_status(confidence_output, validation_output) 

                # --- Populate fields_for_ui and then st.session_state.extraction_results (Issue 2) ---
                extraction_output = extracted_metadata if isinstance(extracted_metadata, dict) else {} # Original flat AI response
                fields_for_ui = {}

                for field_key, raw_field_value in extraction_output.items():
                    if field_key.startswith('_'): # Skip any internal/meta fields from AI response
                        continue
                    
                    current_field_value_str = str(raw_field_value)

                    # Determine AI-reported confidence string for this field_key
                    ai_confidence_str = "Low" # Default
                    if field_key.endswith("_confidence"):
                        # This field *is* a confidence field (e.g., "invoiceNumber_confidence").
                        # Its value *is* its AI confidence string.
                        ai_confidence_str = current_field_value_str if current_field_value_str else "Low"
                    else:
                        # This is a primary data field (e.g., "invoiceNumber").
                        # Look for its associated _confidence field in the original extraction_output.
                        associated_confidence_key = f"{field_key}_confidence"
                        ai_confidence_str = str(extraction_output.get(associated_confidence_key, "Low"))
                        if not ai_confidence_str: ai_confidence_str = "Low" # Handle empty string

                    # Get validation details for the current field_key from validation_output
                    validation_details = validation_output.get('field_validations', {}).get(field_key, {})
                    validation_status_str = validation_details.get('status', 'skip')
                    validation_messages_list = validation_details.get('messages', [])
                    
                    # Determine final adjusted confidence (qualitative and numeric) for UI
                    adjusted_qualitative_str = "Low"
                    adjusted_numeric_score = 0.0

                    if field_key.endswith("_confidence"):
                        # For _confidence fields, adjusted confidence mirrors AI confidence.
                        adjusted_qualitative_str = ai_confidence_str
                        if ai_confidence_str == "High": adjusted_numeric_score = 0.9
                        elif ai_confidence_str == "Medium": adjusted_numeric_score = 0.5
                        elif ai_confidence_str == "Low": adjusted_numeric_score = 0.1
                        else:
                            logger.warning(f"Unexpected AI confidence string for _confidence field {field_key}: '{ai_confidence_str}'. Defaulting adjusted to Low (0.1).")
                            adjusted_qualitative_str = "Low" 
                            adjusted_numeric_score = 0.1
                    else:
                        # For primary data fields, get adjusted confidence from confidence_output.
                        primary_field_adj_details = confidence_output.get(field_key, {})
                        adjusted_qualitative_str = primary_field_adj_details.get('confidence_qualitative', 'Low')
                        adjusted_numeric_score = primary_field_adj_details.get('confidence', 0.0)
                    
                    fields_for_ui[field_key] = {
                        'value': current_field_value_str,
                        'ai_confidence': ai_confidence_str,
                        'validation_status': validation_status_str,
                        'validation_messages': validation_messages_list,
                        'adjusted_confidence': adjusted_numeric_score, # Numeric score
                        'adjusted_confidence_qualitative': adjusted_qualitative_str # Qualitative string
                    }
                
                # The 'overall_status_info' dictionary is already calculated.
                logger.info(f"File {file_name} ({file_id}): Overall status info for document summary: {json.dumps(overall_status_info, indent=2)}")

                st.session_state.extraction_results[file_id] = {
                    "file_name": file_name,
                    "document_type": current_doc_type,
                    "template_id_used_for_extraction": template_id_for_validation,
                    "fields": {
                        f_key: {
                            "value": f_data.get('value'),
                            "ai_confidence": f_data.get('ai_confidence'), 
                            "adjusted_confidence": f_data.get('adjusted_confidence_qualitative'), # Display qualitative
                            "field_validation_status": f_data.get('validation_status', 'skip').lower(),
                            "validations": [ 
                                {
                                    "rule_type": "field_validation", 
                                    "status": f_data.get('validation_status', 'skip'),
                                    "message": ". ".join(f_data.get('validation_messages', [])),
                                    "confidence_impact": f_data.get('adjusted_confidence') # Store numeric here
                                }
                            ]
                        }
                        for f_key, f_data in fields_for_ui.items() 
                    },
                    "document_validation_summary": { 
                        "mandatory_fields_status": validation_output.get('mandatory_check', {}).get('status', 'fail').lower(),
                        "missing_mandatory_fields": validation_output.get('mandatory_check', {}).get('missing_fields', []),
                        "cross_field_status": overall_status_info.get('cross_field_status', "pass").lower(), 
                        "overall_document_confidence_suggestion": overall_status_info.get('status', 'Low')
                    },
                    "raw_ai_response": extracted_metadata, 
                    "data_sent_to_adjuster": data_for_adjuster, 
                    "confidence_adjuster_output": confidence_output 
                }
                
                # Add to processing state results for progress tracking
                if 'results' not in st.session_state.processing_state:
                    st.session_state.processing_state['results'] = {}
                
                # Store the template mapping if we have a document type
                if 'current_doc_type' in locals() and current_doc_type:
                    if not hasattr(st.session_state, 'document_type_to_template'):
                        st.session_state.document_type_to_template = {}
                    st.session_state.document_type_to_template[current_doc_type] = target_template_id
                
                # Make sure batch size info is included
                if 'batch_size' not in st.session_state.metadata_config:
                    st.session_state.metadata_config['batch_size'] = 5
                
                st.session_state.processing_state['results'][file_id] = {
                    "status": "success",
                    "file_name": file_name, 
                    "document_type": current_doc_type if 'current_doc_type' in locals() else None,
                    "message": f"Successfully processed {file_name}"
                }
                
            elif processing_mode == 'freeform':
                # Generic unstructured extraction
                extraction_func = extraction_functions.get('freeform')
                if not extraction_func:
                    logger.error(f"No extraction function for freeform mode. Skipping file {file_name}.")
                    continue
                
                # Perform the extraction
                extracted_metadata = extraction_func(file_id=file_id)
                
                # Build UI structure for freeform results with consistent format
                fields_for_ui = {}
                if isinstance(extracted_metadata, dict):
                    for field_key, value in extracted_metadata.items():
                        field_value = value.get("value", value) if isinstance(value, dict) else value
                        fields_for_ui[field_key] = {
                            "value": field_value,
                            "ai_confidence": "Medium",
                            "adjusted_confidence": "Medium",
                            "field_validation_status": "skip",
                            "validations": [
                                {
                                    "rule_type": "field_validation",
                                    "status": "skip",
                                    "message": "",
                                    "confidence_impact": 0.0
                                }
                            ]
                        }
                
                # Create result data with consistent structure
                result_data = {
                    "file_name": file_name,
                    "file_id": file_id,
                    "file_type": file_data.get("type", "unknown"),
                    "document_type": current_doc_type,
                    "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_mode": processing_mode,
                    "raw_extraction": extracted_metadata,
                    "fields": fields_for_ui,
                    "document_validation_summary": {
                        "mandatory_fields_status": "pass",
                        "missing_mandatory_fields": [],
                        "cross_field_status": "pass",
                        "overall_document_confidence_suggestion": "Medium"
                    },
                    "raw_ai_response": extracted_metadata
                }
                
                # Save in session state
                if 'extraction_results' not in st.session_state:
                    st.session_state.extraction_results = {}
                st.session_state.extraction_results[file_id] = result_data
                
                # Also save to processing state
                if 'results' not in st.session_state.processing_state:
                    st.session_state.processing_state['results'] = {}
                st.session_state.processing_state['results'][file_id] = {
                    "status": "success",
                    "file_name": file_name,
                    "document_type": current_doc_type,
                    "message": f"Successfully processed {file_name}"
                }
            
            processed_count += 1
            st.session_state.processing_state['successful_count'] = processed_count
            logger.info(f"Successfully processed {file_name} - {processed_count}/{total_files}")
            
        except Exception as e:
            logger.error(f"Error during validation/confidence processing for {file_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Still try to save some minimal metadata for this file
            # Basic information for failed files - this lets us still display them in the results
            if 'extraction_results' not in st.session_state:
                st.session_state.extraction_results = {}
                
            # Use raw extraction if available, otherwise empty
            raw_data = {}
            try:
                # Try to get any extracted data we have
                if 'extracted_metadata' in locals() and extracted_metadata is not None:
                    raw_data = extracted_metadata
            except:
                pass
                
            # Build fields with consistent format for error case
            fields_for_ui = {}
            if isinstance(raw_data, dict):
                for field_key, value in raw_data.items():
                    field_value = value.get("value", value) if isinstance(value, dict) else value
                    fields_for_ui[field_key] = {
                        "value": field_value,
                        "ai_confidence": "Low",
                        "adjusted_confidence": "Low",
                        "field_validation_status": "skip",
                        "validations": [
                            {
                                "rule_type": "field_validation",
                                "status": "error",
                                "message": f"Processing error: {str(e)}",
                                "confidence_impact": 0.0
                            }
                        ]
                    }
                
                result_data = {
                    "file_name": file_name,
                    "file_id": file_id,
                    "file_type": file_data.get("type", "unknown"),
                    "document_type": current_doc_type,
                    "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_mode": processing_mode,
                    "raw_extraction": raw_data,
                    "error": str(e),
                    "fields": fields_for_ui,
                    "document_validation_summary": {
                        "mandatory_fields_status": "fail",
                        "missing_mandatory_fields": [],
                        "cross_field_status": "fail",
                        "overall_document_confidence_suggestion": "Low"
                    },
                    "raw_ai_response": raw_data
                }
                
                # Save in session state
                if 'extraction_results' not in st.session_state:
                    st.session_state.extraction_results = {}
                st.session_state.extraction_results[file_id] = result_data
            st.session_state.processing_state['results'][file_id] = {
                "status": "error",
                "file_name": file_name,
                "document_type": current_doc_type,
                "message": f"Error processing {file_name}: {str(e)}"
            }
            
            # Increment error count
            error_count = st.session_state.processing_state.get('error_count', 0) + 1
            st.session_state.processing_state['error_count'] = error_count
            
            logger.warning(f"Used simplified storage for {file_name} due to validation error: {e}")
    
    # Final check before exiting
    logger.info(f"FINAL CHECK before exiting process_files_with_progress: st.session_state.extraction_results contains {len(st.session_state.extraction_results)} items.")
    logger.info(f"Metadata extraction process finished for all selected files.")
    st.session_state.processing_state['is_processing'] = False

def process_files():
    """
    Streamlit interface for processing files with metadata extraction.
    This is a wrapper function for process_files_with_progress that handles
    the Streamlit UI components and configuration.
    """
    st.title("Process Files")
    
    # Ensure we have the required session state variables
    if 'selected_files' not in st.session_state or not st.session_state.selected_files:
        st.warning("Please select files in the File Browser first.")
        return
    
    if 'metadata_config' not in st.session_state:
        st.warning("Please configure metadata extraction parameters first.")
        return
    
    # Get extraction functions
    extraction_functions = get_extraction_functions()
    
    # Initialize validator and confidence adjuster if not already done
    if 'validator' not in st.session_state:
        st.session_state.validator = Validator()
        st.session_state.rule_loader = ValidationRuleLoader(rules_config_path='config/validation_rules.json')
        
    if 'confidence_adjuster' not in st.session_state:
        st.session_state.confidence_adjuster = ConfidenceAdjuster()
    
    # Get configuration
    metadata_config = st.session_state.metadata_config
    processing_mode = metadata_config.get('extraction_method', 'freeform')
    batch_size = metadata_config.get('batch_size', 5)
    
    # Ensure batch size is properly set
    if not batch_size or batch_size < 1:
        batch_size = 5
        metadata_config['batch_size'] = batch_size
    
    # Validate metadata configuration and show warnings for missing templates
    if processing_mode == 'structured':
        # Check both possible key names for the template ID
        template_id = metadata_config.get('metadata_template_id') or metadata_config.get('template_id')
        if not template_id:
            template_selection_method = metadata_config.get('template_selection_method', 'direct')
            if template_selection_method == 'direct':
                st.warning("⚠️ No metadata template selected. Please select a template in the Metadata Configuration page.")
                st.error("Cannot process files in structured mode without a template. Please go back to Metadata Configuration.")
                if st.button("Go to Metadata Configuration"):
                    st.session_state.current_page = "Metadata Configuration"
                    st.rerun()
                return
            elif template_selection_method == 'document_type_mapping':
                # Check if we have valid mappings
                template_mappings = metadata_config.get('template_mappings', {})
                if not template_mappings:
                    st.warning("⚠️ No template mappings defined. Please configure template mappings in the Metadata Configuration page.")
                    if st.button("Go to Metadata Configuration"):
                        st.session_state.current_page = "Metadata Configuration"
                        st.rerun()
                    return
    
    # Initialize or reset processing state
    if 'processing_state' not in st.session_state:
        st.session_state.processing_state = {
            'is_processing': False,
            'current_file_index': 0,
            'current_file': "",
            'total_files': 0,
            'successful_count': 0,
            'error_count': 0,
            'results': {}
        }
    
    # Display status and controls
    st.subheader("Extraction Status")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.write(f"Files selected for processing: {len(st.session_state.selected_files)}")
        st.write(f"Extraction method: {processing_mode.capitalize()}")
        
        if processing_mode == 'structured':
            # Display template information
            template_id = metadata_config.get('metadata_template_id') or metadata_config.get('template_id')
            if template_id:
                st.write(f"Using template: {template_id}")
                
    with col2:
        # Add batch size configuration
        batch_size = st.number_input("Batch Size", min_value=1, max_value=20, value=batch_size, key="batch_size_input")
        st.session_state.metadata_config['batch_size'] = batch_size
        st.write(f"Processing {batch_size} files at a time")
    
    # Display template mappings if available     
    if processing_mode == 'structured':
        template_map_str = ""
        if 'template_mappings' in metadata_config:
            for doc_type, template in metadata_config['template_mappings'].items():
                template_map_str += f"- {doc_type}: {template}\n"
        
        if template_map_str:
            with st.expander("Template Mappings"):
                st.markdown(template_map_str)
    
    with col3:
        if st.session_state.processing_state.get('is_processing', False):
            # Display progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_files = st.session_state.processing_state.get('total_files', 0)
            current_index = st.session_state.processing_state.get('current_file_index', 0)
            
            if total_files > 0:
                progress_bar.progress(min(1.0, current_index / total_files))
                
            status_text.write(f"Processing file {current_index + 1} of {total_files}: {st.session_state.processing_state.get('current_file', '')}")
            
            # Cancel button
            if st.button("Cancel Processing"):
                st.session_state.processing_state['is_processing'] = False
                st.success("Cancelled processing.")
                st.rerun()
        else:
            # Start button
            if st.button("Start Processing"):
                # Reset processing state
                st.session_state.processing_state = {
                    'is_processing': True,
                    'current_file_index': 0,
                    'current_file': "",
                    'total_files': len(st.session_state.selected_files),
                    'successful_count': 0,
                    'error_count': 0,
                    'results': {}
                }
                
                # Call the processing function
                process_files_with_progress(
                    files_to_process=st.session_state.selected_files,
                    extraction_functions=extraction_functions,
                    batch_size=batch_size,
                    processing_mode=processing_mode
                )
                
                # Update UI
                st.success(f"Processing complete! Processed {st.session_state.processing_state.get('successful_count', 0)} files successfully.")
                st.session_state.processing_state['is_processing'] = False
                time.sleep(1)  # Give a moment for the success message to be visible
                st.rerun()
    
    # Show results summary if available
    if hasattr(st.session_state, 'extraction_results') and st.session_state.extraction_results:
        st.subheader("Processing Results Summary")
        
        results_df = pd.DataFrame([{
            "File Name": data.get("file_name", "Unknown"),
            "Status": st.session_state.processing_state.get('results', {}).get(file_id, {}).get("status", "unknown"),
            "Document Type": data.get("document_type", "Unknown"),
            "Field Count": len(data.get("fields", {}))
        } for file_id, data in st.session_state.extraction_results.items()])
        
        st.dataframe(results_df)
        
        if st.button("View Detailed Results"):
            # Navigate to results page
            st.session_state.current_page = "View Results"
            st.rerun()
