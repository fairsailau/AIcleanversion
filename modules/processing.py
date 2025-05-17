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

def get_fields_for_ai_from_template(scope, template_key):
    """
    Extract field definitions from a Box metadata template to prepare for AI extraction
    
    Args:
        scope: The scope of the metadata template (e.g., 'enterprise')
        template_key: The key of the metadata template
    
    Returns:
        List of field definitions formatted for Box AI metadata extraction
        See: https://developer.box.com/guides/box-ai/ai-tutorials/extract-metadata-structured/
    """
    if scope is None or template_key is None:
        logger.error(f"Invalid scope ({scope}) or template_key ({template_key})")
        return None
    
    cache_key = f"{scope}/{template_key}"
    if 'schema_cache' not in st.session_state:
        st.session_state.schema_cache = {}
        
    if cache_key in st.session_state.schema_cache:
        logger.info(f"Using cached schema for {cache_key}")
        schema_details = st.session_state.schema_cache[cache_key]
    else:
        try:
            client = st.session_state.client
            schema = client.metadata_template(scope, template_key).get()
            
            # Convert MetadataTemplate object to Box AI compatible format
            schema_details = {
                'displayName': schema.displayName if hasattr(schema, 'displayName') else template_key,
                'fields': []
            }
            
            if hasattr(schema, 'fields'):
                for field in schema.fields:
                    # Basic field properties
                    field_dict = {
                        'key': field.key,
                        'displayName': getattr(field, 'displayName', field.key)
                    }
                    
                    # Handle field type according to Box metadata types
                    field_type = getattr(field, 'type', 'string')
                    if field_type in ['string', 'float', 'date', 'enum']:
                        field_dict['type'] = field_type
                    else:
                        # Default to string for unknown types
                        field_dict['type'] = 'string'
                        logger.warning(f"Unknown field type '{field_type}' for field '{field.key}', defaulting to string")
                    
                    # Add field description if available - helps Box AI understand context
                    if hasattr(field, 'description') and field.description:
                        field_dict['description'] = field.description
                    
                    # Handle enum options according to Box metadata format
                    if field_type == 'enum' and hasattr(field, 'options'):
                        try:
                            options = []
                            for opt in field.options:
                                if hasattr(opt, 'key'):
                                    options.append(opt.key)
                            if options:
                                field_dict['options'] = options
                        except Exception as e:
                            logger.warning(f"Error processing enum options for field '{field.key}': {e}")
                    
                    # Add prompt for freeform extraction
                    prompt = f"Extract the {field_dict['displayName']}"
                    if field_dict.get('description'):
                        prompt += f" ({field_dict['description']})"
                    if field_dict.get('options'):
                        prompt += f". Valid values are: {', '.join(field_dict['options'])}"
                    field_dict['prompt'] = prompt
                    
                    schema_details['fields'].append(field_dict)
                
                logger.info(f"Processed {len(schema_details['fields'])} fields from metadata template")
            
            st.session_state.schema_cache[cache_key] = schema_details
            logger.info(f"Cached schema for {cache_key}")
            
        except Exception as e:
            logger.error(f"Error fetching metadata schema {scope}/{template_key}: {e}")
            return None
    
    if not isinstance(schema_details, dict) or 'fields' not in schema_details:
        logger.error(f"Invalid schema format for {scope}/{template_key}")
        return None
        
    fields = schema_details['fields']
    if not fields:
        logger.warning(f"No fields found in schema for {scope}/{template_key}")
        return None
    
    # Format fields for Box AI extraction (both structured and freeform)
    ai_fields = []
    freeform_prompts = []
    
    for field in fields:
        if not isinstance(field, dict) or 'key' not in field:
            logger.warning(f"Skipping invalid field format: {field}")
            continue
            
        # Add field for structured extraction
        ai_field = {
            'key': field['key'],
            'type': field['type'],
            'displayName': field['displayName']
        }
        
        # Only include optional fields if they have values
        if field.get('description'):
            ai_field['description'] = field['description']
        if field.get('options'):
            ai_field['options'] = field['options']
            
        ai_fields.append(ai_field)
        
        # Add prompt for freeform extraction
        freeform_prompts.append(field['prompt'])
    
    logger.info(f"Prepared {len(ai_fields)} fields for Box AI extraction")
    
    # Store freeform prompts in session state for use in freeform extraction
    if not hasattr(st.session_state, 'freeform_prompts'):
        st.session_state.freeform_prompts = {}
    st.session_state.freeform_prompts[cache_key] = freeform_prompts
    
    return ai_fields if ai_fields else None

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
                
                logger.info(f"Validating with doc_type={current_doc_type}, doc_category={doc_category}, template_id={template_id_for_validation}")
                
                # Use the enhanced validation method that supports category-template specific rules
                validation_output = st.session_state.validator.validate(
                    ai_response=extracted_metadata, 
                    doc_type=current_doc_type,
                    doc_category=doc_category,
                    template_id=template_id_for_validation
                )
                
                confidence_output = st.session_state.confidence_adjuster.adjust_confidence(extracted_metadata, validation_output)
                overall_status_info = st.session_state.confidence_adjuster.get_overall_document_status(confidence_output, validation_output)

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
                    if isinstance(field_data, dict):
                        value = field_data.get('value', '')
                        confidence = field_data.get('confidence', 'Low')
                    else:
                        value = field_data
                        confidence = 'Low'
                    
                    # Get validation details
                    field_validation = validation_output.get('field_validations', {}).get(field_key, {})
                    validation_status = field_validation.get('status', 'skip')
                    validation_messages = field_validation.get('messages', [])
                    
                    # Get adjusted confidence details
                    adjusted_confidence = confidence_output.get(field_key, {})
                    
                    fields_for_ui[field_key] = {
                        'value': value,
                        'ai_confidence': confidence,
                        'ai_confidence_qualitative': confidence if isinstance(confidence, str) else st.session_state.confidence_adjuster._get_qualitative_confidence(float(confidence)),
                        'validation_status': validation_status,
                        'validation_messages': validation_messages,
                        'adjusted_confidence': adjusted_confidence.get('confidence', 0.0),
                        'adjusted_confidence_qualitative': adjusted_confidence.get('confidence_qualitative', 'Low')
                    }
                
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
                    'overall_confidence_qualitative': overall_confidence_qualitative,
                    'field_count': len(fields_for_ui)
                }

                # Store the results in session state
                st.session_state.extraction_results[file_id] = {
                    "file_name": file_name,
                    "document_type": current_doc_type,
                    "template_id_used_for_extraction": template_id_for_validation,
                    "fields": fields_for_ui,
                    "document_validation_summary": document_summary_for_ui,
                    "raw_ai_response": extraction_output
                }
                
                # Add to processing state results for progress tracking
                if 'results' not in st.session_state.processing_state:
                    st.session_state.processing_state['results'] = {}
                
                selected_template_id_dt = target_template_id  # Use target_template_id instead of undefined template_id
                st.session_state.document_type_to_template[doc_type] = selected_template_id_dt
                
                # Make sure batch size info is included
                if 'batch_size' not in st.session_state.metadata_config:
                    st.session_state.metadata_config['batch_size'] = 5
                
                st.session_state.processing_state['results'][file_id] = {
                    "status": "success",
                    "file_name": file_name, 
                    "document_type": current_doc_type,
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
                
                # Build a simpler UI structure for freeform results
                fields_for_ui_simple = {}
                if isinstance(extracted_metadata, dict):
                    for field_key, value in extracted_metadata.items():
                        if isinstance(value, dict) and "value" in value:
                            # Handle structured response format
                            fields_for_ui_simple[field_key] = {
                                "value": value.get("value"),
                                "ai_confidence": "Medium", 
                                "validations": [],
                                "field_validation_status": "skip",
                                "adjusted_confidence": "Medium",
                                "is_mandatory": False,
                                "is_present": True
                            }
                        else:
                            fields_for_ui_simple[field_key] = {
                                "value": value,
                                "ai_confidence": "Medium", 
                                "validations": [],
                                "field_validation_status": "skip",
                                "adjusted_confidence": "Medium",
                                "is_mandatory": False,
                                "is_present": True
                            }
                
                result_data = {
                    "file_name": file_name,
                    "file_id": file_id,
                    "file_type": file_data.get("type", "unknown"),
                    "document_type": current_doc_type,
                    "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_mode": processing_mode,
                    "raw_extraction": extracted_metadata,
                    "fields": fields_for_ui_simple,
                    "document_summary": {
                        "mandatory_fields_status": "N/A",
                        "missing_mandatory_fields": [],
                        "overall_document_confidence_suggestion": "Medium"
                    }
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
                
            # Build minimal fields display
            simple_fields = {}
            if isinstance(raw_data, dict):
                for field_key, value in raw_data.items():
                    if isinstance(value, dict) and "value" in value:
                        value = value.get("value")
                    
                    simple_fields[field_key] = {
                        "value": value,
                        "ai_confidence": "Low", 
                        "validations": [],
                        "field_validation_status": "skip",
                        "adjusted_confidence": "Low",
                        "is_mandatory": False,
                        "is_present": value is not None and str(value).strip() != ""
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
                "fields": simple_fields,
                "document_summary": {
                    "mandatory_fields_status": "N/A",
                    "missing_mandatory_fields": [],
                    "overall_document_confidence_suggestion": "Low"
                }
            }
            
            st.session_state.extraction_results[file_id] = result_data
            
            # Add to processing state results for progress tracking
            if 'results' not in st.session_state.processing_state:
                st.session_state.processing_state['results'] = {}
                
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
