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
            if hasattr(schema, 'fields') and not isinstance(schema, dict): # This condition correctly identifies SDK object paths
                temp_fields = []
                for field_data_dict in schema.fields: # field_data_dict is expected to be a dict here based on logs
                    field_dict = {}
                    try:
                        # Use dictionary access for items from schema.fields
                        # Ensure a 'key' exists and is not empty before proceeding
                        key_value = field_data_dict.get('key')
                        if not key_value:
                            logger.warning(f"Field data dictionary is missing 'key' or key is empty. Data: {field_data_dict}")
                            continue # Skip this field_data_dict

                        field_dict['key'] = key_value
                        field_dict['type'] = field_data_dict.get('type', 'string') # Default type to string if missing
                        field_dict['displayName'] = field_data_dict.get('displayName', key_value) # Default displayName to key if missing
                        
                        description = field_data_dict.get('description')
                        if description is not None: # Add description only if it exists (even if empty string)
                            field_dict['description'] = description
                        
                        options_data = field_data_dict.get('options')
                        if options_data is not None: # Add options only if it exists (even if empty list)
                            field_dict['options'] = options_data
                        
                        temp_fields.append(field_dict)

                    except TypeError as te: # Handles if field_data_dict is not a dict, though schema.fields should yield dicts
                         logger.error(f"TypeError: Expected a dictionary for field_data_dict but got {type(field_data_dict)}. Error: {te}. Data: {field_data_dict}")
                    except Exception as e:
                        logger.error(f"Unexpected error processing field data dictionary: {e}. Data: {field_data_dict}")
                
                schema_details = {
                    'displayName': getattr(schema, 'displayName', template_key), 
                    'fields': temp_fields
                }
                logger.info(f"Converted MetadataTemplate SDK object to dictionary. Found {len(temp_fields)} fields from schema.fields.")
            else:
                # This is the path if 'schema' is already a dict. This part should be mostly correct.
                schema_details = schema 
                if isinstance(schema_details, dict) and 'fields' in schema_details and isinstance(schema_details['fields'], list):
                     logger.info("Schema is already a dictionary. Using its 'fields' attribute directly for fields_list.")
                else:
                     logger.warning(f"Schema was expected to be a dictionary with a 'fields' list, but it's not. Type: {type(schema_details)}. Cannot determine fields_list.")
            
            # Cache the schema
            st.session_state.schema_cache[cache_key] = schema_details
            logger.info(f"Successfully fetched and cached schema (with descriptions) for {cache_key}")
        except Exception as e:
            logger.error(f"Error fetching metadata schema {scope}/{template_key}: {e}")
            return None
    
    # Process the schema to extract fields
    logger.info(f"Processing schema for {scope}/{template_key}: {type(schema_details)}")
    if isinstance(schema_details, dict):
        # Log the schema structure to help debug the issue
        logger.info(f"Schema keys: {schema_details.keys()}")
        
        # Check if 'fields' is in the schema or if we need to access it differently
        fields_list = []
        if 'fields' in schema_details:
            fields_list = schema_details.get('fields', [])
            logger.info(f"Found {len(fields_list)} fields in schema['fields']")
        elif hasattr(schema_details, 'fields'):
            # Try to access fields as an attribute
            fields_list = schema_details.fields
            logger.info(f"Found fields as an attribute with {len(fields_list)} items")
        
        # Format this as a clean list for the AI model
        ai_fields = []
        if isinstance(fields_list, list): # Ensure fields_list is actually a list
            for field in fields_list:
                if isinstance(field, dict):
                    try:
                        field_key = field['key'] # Direct access
                        if not field_key:
                            logger.warning(f"Skipping field in schema because 'key' is missing or empty. Field data: {field}")
                            continue
                    except KeyError:
                        logger.warning(f"Skipping field in schema because 'key' attribute is missing. Field data: {field}")
                        continue

                    # Proceed to build field_for_ai as before
                    field_for_ai = {
                        'key': field_key,
                        'type': field.get('type', 'string'), # .get() is fine for optional/defaulted attributes
                        'displayName': field.get('displayName', field_key)
                    }
                    if 'description' in field and field.get('description'): # Ensure description has content
                        field_for_ai['description'] = field['description']
                    
                    # For options, ensure they are only added if type is enum/multiSelect and options are non-empty
                    field_type = field.get('type')
                    if field_type in ['enum', 'multiSelect'] and 'options' in field and field.get('options'):
                        field_for_ai['options'] = field['options']
                    
                    ai_fields.append(field_for_ai)
                elif hasattr(field, 'key') and getattr(field, 'key', None): # Ensure getattr has a default for safety
                    # This is the alternative path for SDK-like objects, ensure similar robustness if taken.
                    # For now, primary focus is the dict path as logs suggest conversion to dict happens.
                    # If this path needs changes, it would mirror the dict path's robustness.
                    # Keeping original logic for this branch for now unless it's identified as the one being taken.
                    field_key = getattr(field, 'key')
                    field_for_ai = {
                        'key': field_key,
                        'type': getattr(field, 'type', 'string'),
                        'displayName': getattr(field, 'displayName', field_key)
                    }
                    if hasattr(field, 'description') and getattr(field, 'description', None):
                        field_for_ai['description'] = getattr(field, 'description')
                    
                    sdk_field_type = getattr(field, 'type', None)
                    if sdk_field_type in ['enum', 'multiSelect'] and hasattr(field, 'options') and getattr(field, 'options', None):
                        field_for_ai['options'] = getattr(field, 'options')
                    ai_fields.append(field_for_ai)
                else:
                    logger.warning(f"Skipping field in schema due to unexpected type or missing key. Field data: {field}")
        else:
            logger.warning(f"fields_list is not a list, it's a {type(fields_list)}. Cannot process for AI fields. Schema details: {schema_details}")

        logger.info(f"Extracted {len(ai_fields)} AI fields from template schema. Original schema fields count: {len(fields_list) if isinstance(fields_list, list) else 'N/A'}") # Original log line
        if ai_fields: # If any fields were successfully processed
            return ai_fields
        else:
            # If fields_list was originally empty, or all fields from it were skipped
            # The check 'isinstance(fields_list, list)' is important because fields_list might not be a list if schema parsing failed earlier
            if not isinstance(fields_list, list) or not fields_list: 
                 logger.warning(f"Schema's fields_list was empty or not a list (type: {type(fields_list)}). No fields to process. Schema details: {schema_details}")
                 return [] # Return empty list if schema had no fields or fields_list was malformed
            else: # fields_list had items, but none were convertible to ai_fields
                 logger.warning(f"No AI fields could be extracted from the {len(fields_list)} fields in the schema. Returning empty list for AI call. Fields list from schema: {fields_list}")
                 return [] # CRITICAL: Return empty list, not placeholder, if schema had fields but we failed to process them.
    elif schema_details is None: # Explicitly handle None case (error fetching schema)
        logger.error(f"Schema for {scope}/{template_key} could not be retrieved (returned None).")
        return None # Returning None indicates an error in fetching schema, distinct from empty fields
    else: # Handle empty schema or other unexpected formats (schema_details is not a dict)
        logger.warning(f"Schema for {scope}/{template_key} is not in expected dict format: {type(schema_details)}. Raw schema_details: {schema_details}")
        # If schema_details itself is not a dict, it implies a more fundamental issue than just empty fields.
        return [] # Return empty list; avoid placeholder. Let AI decide what to do with no specific fields.

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
                
                # Create a temporary flat dictionary for the validator
                flat_metadata_for_validation = {
                    key: data['value'] for key, data in extracted_metadata.items() 
                    if isinstance(data, dict) and 'value' in data and not key.startswith('_')
                }
                logger.info(f"Flat metadata for validation: {flat_metadata_for_validation}")

                # Use the enhanced validation method that supports category-template specific rules
                validation_output = st.session_state.validator.validate(
                    ai_response=flat_metadata_for_validation, # Pass the flat dictionary
                    doc_type=None,  # doc_type is no longer used in validation
                    doc_category=doc_category,
                    template_id=template_id_for_validation
                )
                
                confidence_output = st.session_state.confidence_adjuster.adjust_confidence(extracted_metadata, validation_output)
                overall_status_info = st.session_state.confidence_adjuster.get_overall_document_status(confidence_output, validation_output)
                logger.info(f"PROC_LOG_overall_status_info_RECEIVED: {overall_status_info}")

                # --- Restructure results to match results_viewer.py expectations ---
                # Get the validation rules for mandatory field checks
                validation_rules = st.session_state.rule_loader.get_rules_for_category_template(
                    doc_category=doc_category,
                    template_id=template_id_for_validation
                )
                
                extraction_output = extracted_metadata if isinstance(extracted_metadata, dict) else {}
                
                # Process each field for UI display
                fields_for_ui = {}
                for field_key, field_data in extraction_output.items():
                    if field_key.startswith('_'):
                        continue
                        
                    # Get field value and confidence
                    # Get field value, confidence, and origin
                    value = field_data.get('value', '') # field_data is from extraction_output (extracted_metadata)
                    ai_confidence_qualitative = field_data.get('confidence', 'Low')
                    ai_confidence_origin = field_data.get('confidence_origin', 'unknown_origin')
                    
                    # Get validation details
                    field_validation = validation_output.get('field_validations', {}).get(field_key, {})
                    validation_status = field_validation.get('status', 'skip')
                    validation_messages = field_validation.get('messages', [])
                    
                    # Get adjusted confidence details from confidence_output (output of ConfidenceAdjuster)
                    adjusted_confidence_details = confidence_output.get(field_key, {})
                    
                    fields_for_ui[field_key] = {
                        'value': value,
                        'ai_confidence_qualitative': ai_confidence_qualitative, # Already qualitative from extraction
                        'ai_confidence_origin': ai_confidence_origin, # Newly added
                        'validation_status': validation_status,
                        'validation_messages': validation_messages,
                        'adjusted_confidence_numeric': adjusted_confidence_details.get('confidence', 0.0),
                        'adjusted_confidence_qualitative': adjusted_confidence_details.get('confidence_qualitative', 'Low')
                    }
                    logger.info(
                        f"Field Confidence Journey for '{field_key}' in file '{file_name}': "
                        f"Initial AI Confidence: '{ai_confidence_qualitative}' (Origin: '{ai_confidence_origin}'), "
                        f"Validation Status: '{validation_status}', "
                        f"Adjusted Confidence (Numeric): {adjusted_confidence_details.get('confidence', 0.0):.2f}, "
                        f"Adjusted Confidence (Qualitative): '{adjusted_confidence_details.get('confidence_qualitative', 'Low')}'"
                    )
                
                # Calculate document-level validation summary
                mandatory_check = validation_output.get('mandatory_check', {})
                mandatory_status = mandatory_check.get('status', 'Failed')
                missing_fields = mandatory_check.get('missing_fields', [])
                
                # Calculate overall confidence
                confidence_values = [
                    float(field_data.get('adjusted_confidence', 0.0))
                    for field_data in confidence_output.values()
                    if isinstance(field_data, dict)
                ]
                
                avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
                overall_confidence_qualitative = st.session_state.confidence_adjuster._get_qualitative_confidence(avg_confidence)
                
                document_summary_for_ui = {
                    'status': validation_output.get('status', 'Failed'),
                    'mandatory_status': mandatory_status,
                    'missing_fields': missing_fields,
                    'overall_confidence': avg_confidence,
                    'overall_confidence_qualitative': overall_status_info.get('status', 'Low'), # Ensure this matches how overall_status_info is structured
                    'field_count': len(fields_for_ui)
                }
                logger.info(f"PROC_LOG_document_summary_for_ui_CREATED: {document_summary_for_ui}")

                # As per instructions, use a temporary variable for logging then assignment:
                val_to_store_for_overall_sugg = document_summary_for_ui.get('overall_confidence_qualitative', 'Low') 
                logger.info(f"PROC_LOG_STORING_overall_suggestion_AS: {val_to_store_for_overall_sugg}")
                
                # Store the results in session state with the structure expected by results_viewer.py
                st.session_state.extraction_results[file_id] = {
                    "file_name": file_name,
                    "document_type": current_doc_type,
                    "template_id_used_for_extraction": template_id_for_validation,
                    "fields": {
                        # field_key_from_ui is 'field_key', data_from_ui is 'field_data' in this context
                        field_key: {
                            "value": field_data.get('value', ''),
                            "ai_confidence": field_data.get('ai_confidence_qualitative', 'Low'), # Using the qualitative AI confidence
                            "ai_confidence_origin": field_data.get('ai_confidence_origin', 'unknown_origin'), # NEW
                            "adjusted_confidence": field_data.get('adjusted_confidence_qualitative', 'Low'), # Using the qualitative adjusted confidence
                            "field_validation_status": field_data.get('validation_status', 'skip').lower(),
                            "validations": [
                                {
                                    "rule_type": "field_validation", # This could be more dynamic if rules have types
                                    "status": field_data.get('validation_status', 'skip'),
                                    "message": ". ".join(field_data.get('validation_messages', [])),
                                    # Storing numeric adjusted confidence here if needed, or qualitative impact
                                    "confidence_impact_numeric": field_data.get('adjusted_confidence_numeric', 0.0) 
                                }
                            ]
                        }
                        for field_key, field_data in fields_for_ui.items() # Iterating through the previously prepared fields_for_ui
                    },
                    "document_validation_summary": {
                        "mandatory_fields_status": document_summary_for_ui.get('mandatory_status', 'fail').lower(),
                        "missing_mandatory_fields": document_summary_for_ui.get('missing_fields', []),
                        "cross_field_status": "pass",  # Default to pass if not using cross-field validation
                        "overall_document_confidence_suggestion": val_to_store_for_overall_sugg, # Corrected usage
                    },
                    "raw_ai_response": extracted_metadata  # Store the raw response for reference
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
                
                # Determine the Correct Prompt for freeform extraction
                # Default prompt from metadata_config or a fallback
                default_prompt = metadata_config.get('freeform_prompt', 'Extract key metadata from this document including dates, names, amounts, and other important information.')
                current_prompt_to_use = default_prompt
                
                if current_doc_type: # current_doc_type is determined earlier in the loop
                    doc_specific_prompts = metadata_config.get('document_type_prompts', {})
                    current_prompt_to_use = doc_specific_prompts.get(current_doc_type, default_prompt)
                
                logger.info(f"Using prompt for freeform extraction on file {file_name} (doc type: {current_doc_type}): {current_prompt_to_use}")
                
                # Perform the extraction with all required arguments
                extracted_metadata = extraction_func(
                    client=client,
                    file_id=file_id,
                    prompt=current_prompt_to_use,
                    ai_model=ai_model
                )
                
                # Build UI structure for freeform results with consistent format
                fields_for_ui = {}
                if isinstance(extracted_metadata, dict):
                    for field_key, field_data_from_extraction in extracted_metadata.items():
                        if field_key.startswith('_'): # Skip internal keys like _raw_answer
                            continue
                        
                        # field_data_from_extraction is expected to be {'value': ..., 'confidence': ..., 'confidence_origin': ...}
                        value = field_data_from_extraction.get('value', field_data_from_extraction) # Fallback if not dict
                        ai_confidence_qualitative = field_data_from_extraction.get('confidence', 'Medium')
                        ai_confidence_origin = field_data_from_extraction.get('confidence_origin', 'unknown_origin')

                        fields_for_ui[field_key] = {
                            "value": value,
                            "ai_confidence": ai_confidence_qualitative, # Using this key for consistency
                            "ai_confidence_origin": ai_confidence_origin,
                            "adjusted_confidence": ai_confidence_qualitative, # In freeform, adjusted is same as AI
                            "field_validation_status": "skip", # No validation in freeform
                            "validations": [ # Placeholder for consistent structure
                                {
                                    "rule_type": "field_validation",
                                    "status": "skip",
                                    "message": "",
                                    "confidence_impact_numeric": 0.0 
                                }
                            ]
                        }
                        logger.info(
                            f"Field Confidence Journey for '{field_key}' in file '{file_name}' (Freeform): "
                            f"Initial AI Confidence: '{ai_confidence_qualitative}' (Origin: '{ai_confidence_origin}'), "
                            f"Validation Status: 'skip' (Freeform), "
                            f"Adjusted Confidence (Qualitative): '{ai_confidence_qualitative}'" # Mirrored from AI for freeform
                        )
                
                # Create result data with consistent structure
                result_data = {
                    "file_name": file_name,
                    "file_id": file_id,
                    "file_type": file_data.get("type", "unknown"),
                    "document_type": current_doc_type,
                    "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_mode": processing_mode,
                    "raw_extraction": extracted_metadata, # This is the full structured response from extraction
                    "fields": { # This structure should match the one in structured path for consistency in results_viewer
                        key: {
                            "value": data.get("value", ""),
                            "ai_confidence": data.get("ai_confidence", "Medium"),
                            "ai_confidence_origin": data.get("ai_confidence_origin", "unknown_origin"),
                            "adjusted_confidence": data.get("adjusted_confidence", "Medium"), # Usually same as AI for freeform
                            "field_validation_status": data.get("field_validation_status", "skip").lower(),
                            "validations": data.get("validations", [])
                        }
                        for key, data in fields_for_ui.items()
                    },
                    "document_validation_summary": {
                        "mandatory_fields_status": "pass", # Default for freeform
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
            if isinstance(raw_data, dict): # raw_data is extracted_metadata in this context
                for field_key, field_data_from_extraction in raw_data.items():
                    if field_key.startswith('_'): # Skip internal keys
                        continue

                    # field_data_from_extraction is expected to be {'value': ..., 'confidence': ..., 'confidence_origin': ...}
                    # or it could be a simple value if extraction failed very early or returned unexpected format
                    value = field_data_from_extraction.get('value', field_data_from_extraction) if isinstance(field_data_from_extraction, dict) else field_data_from_extraction
                    ai_confidence_qualitative = field_data_from_extraction.get('confidence', 'Low') if isinstance(field_data_from_extraction, dict) else 'Low'
                    ai_confidence_origin = field_data_from_extraction.get('confidence_origin', 'error_default') if isinstance(field_data_from_extraction, dict) else 'error_default'
                    
                    fields_for_ui[field_key] = {
                        "value": value,
                        "ai_confidence": ai_confidence_qualitative, 
                        "ai_confidence_origin": ai_confidence_origin,
                        "adjusted_confidence": ai_confidence_qualitative, # Adjusted is same as AI in error/freeform
                        "field_validation_status": "error", # Mark as error
                        "validations": [
                            {
                                "rule_type": "processing_error",
                                "status": "error",
                                "message": f"Processing error: {str(e)}",
                                "confidence_impact_numeric": 0.0
                            }
                        ]
                    }
                
                result_data = {
                    "file_name": file_name,
                    "file_id": file_id,
                    "file_type": file_data.get("type", "unknown"),
                    "document_type": current_doc_type, # This might be None if categorization also failed or wasn't run
                    "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_mode": processing_mode,
                    "raw_extraction": raw_data, # Full original extraction attempt
                    "error": str(e),
                    "fields": { # This structure should match the one in structured/freeform paths
                        key: {
                            "value": data.get("value", ""),
                            "ai_confidence": data.get("ai_confidence", "Low"),
                            "ai_confidence_origin": data.get("ai_confidence_origin", "error_default"),
                            "adjusted_confidence": data.get("adjusted_confidence", "Low"),
                            "field_validation_status": data.get("field_validation_status", "error").lower(),
                            "validations": data.get("validations", [])
                        }
                        for key, data in fields_for_ui.items()
                    },
                    "document_validation_summary": {
                        "mandatory_fields_status": "fail", # Default for error
                        "missing_mandatory_fields": [], # Unknown in error cases often
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
