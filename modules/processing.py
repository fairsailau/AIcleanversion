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
    template_selection_method = template_config.get("template_selection_method", "direct")
    logger.debug(f"Template selection method: {template_selection_method}")
    
    if template_selection_method == "direct":
        # Use directly specified template
        selected_template = template_config.get("metadata_template_id")
        logger.info(f"Using directly specified template: {selected_template}")
        return selected_template
    
    elif template_selection_method == "document_type_mapping":
        # First get the document type, then map to template
        doc_type = None
        
        # Check if document has been categorized
        if 'document_categorization' in st.session_state and file_id in st.session_state.document_categorization:
            categorization_data = st.session_state.document_categorization.get(file_id, {})
            doc_type = categorization_data.get('category')
            logger.info(f"Document type from categorization for file {file_name}: {doc_type}")
        
        if not doc_type:
            logger.warning(f"No document type found for file {file_name}. Using default.")
            doc_type = "Default"
        
        # Map document type to template
        template_mappings = template_config.get("template_mappings", {})
        if not template_mappings:
            logger.error("No template mappings defined in configuration!")
            return None
        
        template_id = map_document_type_to_template(doc_type, template_mappings)
        if template_id:
            logger.info(f"File ID {file_id} (type {doc_type}): Using mapped template {template_id}")
        else:
            logger.warning(f"Could not determine template for file {file_name} with type {doc_type}")
        
        return template_id
    
    else:
        logger.error(f"Unknown template selection method: {template_selection_method}")
        return None

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
            schema_details = schema
            
            # Cache the schema
            st.session_state.schema_cache[cache_key] = schema_details
            logger.info(f"Successfully fetched and cached schema (with descriptions) for {cache_key}")
        except Exception as e:
            logger.error(f"Error fetching metadata schema {scope}/{template_key}: {e}")
            return None
    
    # Process the schema to extract fields
    if isinstance(schema_details, dict) and 'fields' in schema_details:
        # Format this as a clean list for the AI model
        ai_fields = []
        for field in schema_details.get('fields', []):
            field_key = field.get('key')
            if not field_key:
                continue  # Skip fields without keys
                
            # Only include essential fields for AI extraction
            field_for_ai = {
                'key': field_key,
                'type': field.get('type', 'string'),
                'displayName': field.get('displayName', field_key)
            }
            
            # Add description if available - helpful context for AI
            if 'description' in field and field['description']:
                field_for_ai['description'] = field['description']
                
            # If enum, include options
            details = field
            if 'options' in details and details['options']:
                field_for_ai['options'] = details['options']
            ai_fields.append(field_for_ai)
        return ai_fields
    elif schema_details is None: # Explicitly handle None case (error fetching schema)
        logger.error(f"Schema for {scope}/{template_key} could not be retrieved (returned None).")
        return None
    else: # Handle empty schema or other unexpected formats
        logger.warning(f"Schema for {scope}/{template_key} is empty or not in expected dict format: {schema_details}")
        return [] # Return empty list if schema is empty but valid, or handle as error if appropriate

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
                
                # Get template key and scope (enterprise_id)
                template_parts = target_template_id.split('_', 1)
                if len(template_parts) == 2:
                    scope = 'enterprise_' + template_parts[0]
                    template_key = template_parts[1]
                else:
                    # Fallback to simple form
                    scope = 'enterprise'  
                    template_key = target_template_id
                
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
                extracted_metadata = extraction_func(file_id=file_id, template_id=target_template_id, template_fields=template_fields)
                
                # Validate the extracted metadata
                
                doc_category = None
                if 'document_categorization' in st.session_state and file_id in st.session_state.document_categorization:
                    doc_category_result = st.session_state.document_categorization.get(file_id, {})
                    doc_category = doc_category_result.get('category')
                
                # Get template ID for validation 
                # (Note: we already have template_id from earlier, but confirming it's the one we want to use)
                # This is the template ID that would be used for metadata application
                template_id_for_validation = target_template_id
                
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
                validation_rules = st.session_state.validator.get_rules_for_category_template(
                    doc_category=doc_category,
                    template_id=template_id_for_validation
                )
                
                fields_for_ui = {}
                raw_ai_data = extracted_metadata if isinstance(extracted_metadata, dict) else {}
                for field_key, ai_field_data in raw_ai_data.items():
                    value = None
                    original_ai_confidence_score = 0.0 # Default
                    original_ai_confidence_qualitative = "Low" # Default

                    if isinstance(ai_field_data, dict):
                        value = ai_field_data.get("value")
                        original_ai_confidence_score = ai_field_data.get("confidenceScore", 0.0)
                        if not isinstance(original_ai_confidence_score, (int, float)):
                            try: original_ai_confidence_score = float(original_ai_confidence_score)
                            except: original_ai_confidence_score = 0.0
                    elif isinstance(ai_field_data, (str, int, float, bool)):
                        value = ai_field_data
                        original_ai_confidence_score = 0.5 # Assign a neutral default for primitives
                    
                    original_ai_confidence_qualitative = st.session_state.confidence_adjuster._get_qualitative_confidence(original_ai_confidence_score)

                    # Get validation details with proper defaults
                    field_validation_details = validation_output.get("field_validations", {}).get(field_key, {"is_valid": True, "status": "skip", "messages": []})
                    
                    # Get adjusted confidence with safe handling
                    field_adjusted_confidence_details = confidence_output.get(field_key, {})
                    
                    # Handle different formats of confidence data
                    adjusted_confidence = original_ai_confidence_qualitative  # Default fallback
                    
                    # Check if it's a dictionary with confidence_qualitative
                    if isinstance(field_adjusted_confidence_details, dict):
                        if "confidence_qualitative" in field_adjusted_confidence_details:
                            adjusted_confidence = field_adjusted_confidence_details["confidence_qualitative"]
                    # Check if it's already a string value
                    elif isinstance(field_adjusted_confidence_details, str):
                        adjusted_confidence = field_adjusted_confidence_details

                    # Build the field data for UI display
                    fields_for_ui[field_key] = {
                        "value": value,
                        "ai_confidence": original_ai_confidence_qualitative,
                        "validations": field_validation_details.get("messages", []),
                        "field_validation_status": field_validation_details.get("status", "skip"),
                        "adjusted_confidence": adjusted_confidence,
                        "is_mandatory": field_key in validation_rules.get("mandatory_fields", []),
                        "is_present": value is not None and str(value).strip() != ""
                    }

                document_summary_for_ui = {
                    "mandatory_fields_status": validation_output.get("mandatory_check", {}).get("status", "N/A"),
                    "missing_mandatory_fields": validation_output.get("mandatory_check", {}).get("missing_fields", []),
                    "overall_document_confidence_suggestion": overall_status_info.get("status", "N/A")
                }

                # Save both in extraction_results and processing_state.results
                if 'extraction_results' not in st.session_state:
                    st.session_state.extraction_results = {}
                
                st.session_state.extraction_results[file_id] = {
                    "file_id": file_id,
                    "file_name": file_name,
                    "file_type": file_data.get("type", "unknown"),  
                    "document_type": current_doc_type,
                    "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_mode": processing_mode,
                    "target_template_id": target_template_id,
                    "template_scope": scope if 'scope' in locals() else None,
                    "template_key": template_key if 'template_key' in locals() else None,
                    "raw_extraction": extracted_metadata,
                    "validation_output": validation_output,
                    "confidence_output": confidence_output,
                    "fields": fields_for_ui,
                    "document_summary": document_summary_for_ui
                }
                
                # Add to processing state results for progress tracking
                if 'results' not in st.session_state.processing_state:
                    st.session_state.processing_state['results'] = {}
                
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
