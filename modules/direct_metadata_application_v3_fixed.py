import streamlit as st
import logging
import json
from boxsdk import Client, exception
from boxsdk.object.metadata import MetadataUpdate
from dateutil import parser
from datetime import timezone
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
if 'template_schema_cache' not in st.session_state:
    st.session_state.template_schema_cache = {}

class ConversionError(ValueError):
    pass

def get_template_schema(client, full_scope, template_key):
    """
    Fetches the metadata template schema from Box API (compatible with SDK v3.x).
    Uses a cache to avoid redundant API calls.
    Uses FULL scope (e.g., "enterprise_12345") and simple template key.
    
    Args:
        client: Box client object
        full_scope (str): The full scope identifier (e.g., "enterprise_12345" or "global").
        template_key (str): The key of the template (e.g., "homeLoan").
        
    Returns:
        dict: A dictionary mapping field keys to their types, or None if error.
    """
    cache_key = f'{full_scope}_{template_key}'
    if cache_key in st.session_state.template_schema_cache:
        logger.info(f'Using cached schema for {full_scope}/{template_key}')
        return st.session_state.template_schema_cache[cache_key]
    try:
        logger.info(f'Fetching template schema for {full_scope}/{template_key}')
        template = client.metadata_template(full_scope, template_key).get()
        if template and hasattr(template, 'fields') and template.fields:
            schema_map = {field['key']: field['type'] for field in template.fields}
            st.session_state.template_schema_cache[cache_key] = schema_map
            logger.info(f'Successfully fetched and cached schema for {full_scope}/{template_key}')
            return schema_map
        else:
            logger.warning(f'Template {full_scope}/{template_key} found but has no fields or is invalid.')
            st.session_state.template_schema_cache[cache_key] = {}
            return {}
    except exception.BoxAPIException as e:
        logger.error(f'Box API Error fetching template schema for {full_scope}/{template_key}: Status={e.status}, Code={e.code}, Message={e.message}')
        st.session_state.template_schema_cache[cache_key] = None
        return None
    except Exception as e:
        logger.exception(f'Unexpected error fetching template schema for {full_scope}/{template_key}: {e}')
        st.session_state.template_schema_cache[cache_key] = None
        return None

def convert_value_for_template(key, value, field_type):
    if value is None:
        return None
    original_value_repr = repr(value)
    try:
        if field_type == 'float':
            if isinstance(value, str):
                cleaned_value = value.replace('$', '').replace(',', '')
                try:
                    return float(cleaned_value)
                except ValueError:
                    raise ConversionError(f"Could not convert string '{value}' to float for key '{key}'.")
            elif isinstance(value, (int, float)):
                return float(value)
            else:
                raise ConversionError(f"Value {original_value_repr} for key '{key}' is not a string or number, cannot convert to float.")
        elif field_type == 'date':
            if isinstance(value, str):
                try:
                    dt = parser.parse(value)
                    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except (parser.ParserError, ValueError) as e:
                    raise ConversionError(f"Could not parse date string '{value}' for key '{key}': {e}.")
            else:
                raise ConversionError(f"Value {original_value_repr} for key '{key}' is not a string, cannot convert to date.")
        elif field_type == 'string' or field_type == 'enum':
            if not isinstance(value, str):
                logger.info(f"Converting value {original_value_repr} to string for key '{key}' (type {field_type}).")
            return str(value)
        elif field_type == 'multiSelect':
            if isinstance(value, list):
                converted_list = [str(item) for item in value]
                if converted_list != value:
                    logger.info(f"Converting items in list {original_value_repr} to string for key '{key}' (type multiSelect).")
                return converted_list
            elif isinstance(value, str):
                logger.info(f"Converting string value {original_value_repr} to list of strings for key '{key}' (type multiSelect).")
                return [value]
            else:
                logger.info(f"Converting value {original_value_repr} to list of strings for key '{key}' (type multiSelect).")
                return [str(value)]
        else:
            logger.warning(f"Unknown field type '{field_type}' for key '{key}'. Cannot convert value {original_value_repr}.")
            raise ConversionError(f"Unknown field type '{field_type}' for key '{key}'.")
    except ConversionError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error converting value {original_value_repr} for key '{key}' (type {field_type}): {e}.")
        raise ConversionError(f"Unexpected error converting value for key '{key}': {e}")

def fix_metadata_format(metadata_values):
    formatted_metadata = {}
    for key, value in metadata_values.items():
        if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
            try:
                json_compatible_str = value.replace("'", '"')
                parsed_value = json.loads(json_compatible_str)
                formatted_metadata[key] = parsed_value
            except json.JSONDecodeError:
                formatted_metadata[key] = value
        else:
            formatted_metadata[key] = value
    return formatted_metadata

def flatten_metadata_for_template(metadata_values):
    flattened_metadata = {}
    if 'answer' in metadata_values and isinstance(metadata_values['answer'], dict):
        for key, value in metadata_values['answer'].items():
            flattened_metadata[key] = value
    else:
        flattened_metadata = metadata_values.copy()
    keys_to_remove = ['ai_agent_info', 'created_at', 'completion_reason', 'answer']
    for key in keys_to_remove:
        if key in flattened_metadata:
            del flattened_metadata[key]
    return flattened_metadata

def filter_confidence_fields(metadata_values):
    return {key: value for key, value in metadata_values.items() if not key.endswith('_confidence')}

def parse_template_id(template_id_full):
    if not template_id_full or '_' not in template_id_full:
        raise ValueError(f'Invalid template ID format: {template_id_full}')
    last_underscore_index = template_id_full.rfind('_')
    if last_underscore_index == 0 or last_underscore_index == len(template_id_full) - 1:
        raise ValueError(f'Template ID format incorrect, expected scope_templateKey: {template_id_full}')
    full_scope = template_id_full[:last_underscore_index]
    template_key = template_id_full[last_underscore_index + 1:]
    if not full_scope.startswith('enterprise_') and full_scope != 'global':
        if not full_scope == 'enterprise':
            logger.warning(f"Scope format '{full_scope}' might be unexpected. Expected 'enterprise_...' or 'global'.")
    logger.debug(f"Parsed template ID '{template_id_full}' -> full_scope='{full_scope}', template_key='{template_key}'")
    return (full_scope, template_key)

def apply_metadata_to_file_direct_worker(client, file_id, file_name, metadata_values, full_scope, template_key):
    logger.info(f'Starting metadata application for file ID {file_id} ({file_name}) with template {full_scope}/{template_key}')
    try:
        filtered_metadata = filter_confidence_fields(metadata_values)
        logger.debug(f'File ID {file_id}: Filtered metadata (no confidence): {filtered_metadata}')
        template_schema = get_template_schema(client, full_scope, template_key)
        if template_schema is None:
            error_msg = f'Could not retrieve template schema for {full_scope}/{template_key}. Cannot apply metadata to file {file_id} ({file_name}).'
            return (False, error_msg)
        if not template_schema:
            logger.warning(f'Template schema for {full_scope}/{template_key} is empty. No fields to apply for file {file_id} ({file_name}).')
            return (True, 'Template schema is empty, nothing to apply.')
        metadata_to_apply = {}
        conversion_errors = []
        for key, field_type in template_schema.items():
            if key in filtered_metadata:
                value = filtered_metadata[key]
                try:
                    converted_value = convert_value_for_template(key, value, field_type)
                    if converted_value is not None:
                        metadata_to_apply[key] = converted_value
                    else:
                        logger.info(f"Value for key '{key}' is None after conversion. Skipping for file {file_id}.")
                except ConversionError as e:
                    error_msg = f"Conversion error for key '{key}' (expected type '{field_type}', value: {repr(value)}): {e}. Field skipped."
                    logger.warning(error_msg)
                    conversion_errors.append(error_msg)
                except Exception as e:
                    error_msg = f"Unexpected error processing key '{key}' for file {file_id}: {e}. Field skipped."
                    logger.error(error_msg)
                    conversion_errors.append(error_msg)
            else:
                logger.info(f"Template field '{key}' not found in extracted metadata for file {file_id}. Skipping field.")
        if not metadata_to_apply:
            if conversion_errors:
                warn_msg = f"Metadata application skipped for file {file_name}: No fields could be successfully converted. Errors: {'; '.join(conversion_errors)}"
                logger.warning(warn_msg)
                return (False, f"No valid metadata fields to apply after conversion errors: {'; '.join(conversion_errors)}")
            else:
                info_msg = f'No matching metadata fields found or all values were None for file {file_name}. Nothing to apply.'
                logger.info(info_msg)
                return (True, 'No matching fields to apply')
        logger.info(f'Attempting to apply metadata to file {file_id} using operations: {metadata_to_apply}')
        try:
            metadata_instance = client.file(file_id).metadata(scope=full_scope, template=template_key)
            try:
                existing_data = metadata_instance.get()
                logger.info(f'File ID {file_id}: Existing metadata found for {full_scope}/{template_key}. Updating.')
                updated_instance = metadata_instance.update(metadata_to_apply)
                logger.info(f"File ID {file_id}: Successfully updated metadata instance. ETag: {(updated_instance.etag if hasattr(updated_instance, 'etag') else 'N/A')}")
            except exception.BoxAPIException as e:
                if e.status == 404:
                    logger.info(f'File ID {file_id}: No existing metadata for {full_scope}/{template_key}. Creating.')
                    created_instance = metadata_instance.create(metadata_to_apply)
                    logger.info(f"File ID {file_id}: Successfully created metadata instance. ETag: {(created_instance.etag if hasattr(created_instance, 'etag') else 'N/A')}")
                else:
                    raise
            return (True, f'Metadata successfully applied to {file_name} using template {template_key}.')
        except exception.BoxAPIException as e:
            error_message = f'Box API Error applying metadata to {file_name} (ID: {file_id}) for template {full_scope}/{template_key}: Status={e.status}, Code={e.code}, Message={e.message}, Details: {e.context_info}'
            logger.error(error_message)
            return (False, error_message)
        except Exception as e:
            error_message = f'Unexpected error applying metadata to {file_name} (ID: {file_id}): {e}'
            logger.exception(error_message)
            return (False, error_message)
    except Exception as e:
        critical_error_msg = f'Critical unexpected error during metadata application process for file {file_name} (ID: {file_id}): {str(e)}'
        logger.exception(critical_error_msg)
        return (False, critical_error_msg)

def apply_metadata_direct():
    st.title('Apply Metadata')
    if not st.session_state.get('authenticated') or not st.session_state.get('client'):
        st.error('Authentication required. Please login first.')
        if st.button('Go to Login'):
            st.session_state.current_page = 'Home'
            st.rerun()
        return
    client = st.session_state.client
    selected_result_ids = st.session_state.get('selected_result_ids', [])
    extraction_results = st.session_state.get('extraction_results', {})
    all_files_info = st.session_state.get('all_files_info', {})
    global_template_id = st.session_state.metadata_config.get('template_id')
    extraction_method = st.session_state.metadata_config.get('extraction_method', 'structured')
    if not selected_result_ids:
        st.info("No results selected for metadata application. Please select results in the 'View Results' page or ensure files were processed.")
        return
    if not extraction_results or not any((file_id in extraction_results for file_id in selected_result_ids)):
        st.warning('Selected results are not found in the extraction data. Please re-process files or check selections.')
        return
    if not global_template_id:
        logger.info('No global template_id found in metadata_config. Application will rely on per-file templates from document categorization if available.')
    if 'application_state' not in st.session_state or not isinstance(st.session_state.application_state, dict):
        st.session_state.application_state = {'is_applying': False, 'applied_files': 0, 'total_files_for_application': 0, 'results': {}, 'errors': {}, 'current_batch_progress': 0, 'total_batches': 0, 'current_batch_num': 0}
    if not st.session_state.application_state.get('is_applying', False):
        if st.button('Apply Selected Metadata', key='apply_selected_metadata_button', use_container_width=True):
            st.session_state.application_state['is_applying'] = True
            st.session_state.application_state['applied_files'] = 0
            st.session_state.application_state['total_files_for_application'] = len(selected_result_ids)
            st.session_state.application_state['results'] = {}
            st.session_state.application_state['errors'] = {}
            st.rerun()
        return
    if st.session_state.application_state.get('is_applying', False):
        total_files_to_apply = st.session_state.application_state['total_files_for_application']
        files_processed_count = st.session_state.application_state['applied_files']
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        status_text.text(f'Preparing to apply metadata to {total_files_to_apply} files...')
        batch_size = 5
        batches = [selected_result_ids[i:i + batch_size] for i in range(0, len(selected_result_ids), batch_size)]
        st.session_state.application_state['total_batches'] = len(batches)
        for i, batch_chunk in enumerate(batches):
            st.session_state.application_state['current_batch_num'] = i + 1
            st.session_state.application_state['current_batch_progress'] = 0
            for file_id_in_batch_idx, file_id in enumerate(batch_chunk):
                if not st.session_state.application_state['is_applying']:
                    st.warning('Metadata application cancelled.')
                    return
                file_info = all_files_info.get(str(file_id), {'name': f'File ID {file_id}', 'type': 'file'})
                file_name_display = file_info.get('name', f'File ID {file_id}')
                metadata_values_for_file = extraction_results.get(file_id)
                status_text.text(f'Batch {i + 1}/{len(batches)}: Applying to {file_name_display} ({file_id_in_batch_idx + 1}/{len(batch_chunk)})... Overall: {files_processed_count + 1}/{total_files_to_apply}')
                if not metadata_values_for_file:
                    logger.warning(f'No extraction results found for file ID {file_id} ({file_name_display}). Skipping application.')
                    st.session_state.application_state['errors'][file_id] = 'No extraction results found.'
                    st.session_state.application_state['applied_files'] += 1
                    files_processed_count = st.session_state.application_state['applied_files']
                    progress_bar.progress(files_processed_count / total_files_to_apply if total_files_to_apply > 0 else 0)
                    continue
                file_specific_template_id = st.session_state.document_categorization.get('results', {}).get(file_id, {}).get('template_id')
                template_id_for_file = file_specific_template_id or global_template_id
                if not template_id_for_file:
                    error_detail = "a target template must be selected in 'Metadata Configuration' or assigned by document categorization to apply the results."
                    if extraction_method == 'freeform':
                        current_error_message = f'File {file_name_display}: For freeform extraction, {error_detail}'
                    else:
                        current_error_message = f'File {file_name_display}: For structured extraction, {error_detail}'
                    st.error(current_error_message)
                    logger.error(f"File ID {file_id} ({file_name_display}): No template_id found for application. Global: '{global_template_id}', File-specific: '{file_specific_template_id}', Method: {extraction_method}")
                    st.session_state.application_state['results'][file_id] = {'status': 'error', 'message': 'No template specified for application.'}
                    st.session_state.application_state['errors'][file_id] = 'No template specified for application.'
                    st.session_state.application_state['applied_files'] += 1
                    files_processed_count = st.session_state.application_state['applied_files']
                    progress_bar.progress(files_processed_count / total_files_to_apply if total_files_to_apply > 0 else 0)
                    continue
                try:
                    full_scope, template_key = parse_template_id(template_id_for_file)
                except ValueError as e:
                    st.error(f"File {file_name_display}: Invalid template ID format '{template_id_for_file}': {e}")
                    logger.error(f"File ID {file_id} ({file_name_display}): Invalid template ID format '{template_id_for_file}': {e}")
                    st.session_state.application_state['results'][file_id] = {'status': 'error', 'message': f'Invalid template ID format: {e}'}
                    st.session_state.application_state['errors'][file_id] = f'Invalid template ID format: {e}'
                    st.session_state.application_state['applied_files'] += 1
                    files_processed_count = st.session_state.application_state['applied_files']
                    progress_bar.progress(files_processed_count / total_files_to_apply if total_files_to_apply > 0 else 0)
                    continue
                success, message = apply_metadata_to_file_direct_worker(client=client, file_id=str(file_id), file_name=file_name_display, metadata_values=metadata_values_for_file, full_scope=full_scope, template_key=template_key)
                st.session_state.application_state['results'][file_id] = {'status': 'success' if success else 'error', 'message': message}
                if not success:
                    st.session_state.application_state['errors'][file_id] = message
                st.session_state.application_state['applied_files'] += 1
                files_processed_count = st.session_state.application_state['applied_files']
                progress_bar.progress(files_processed_count / total_files_to_apply if total_files_to_apply > 0 else 0)
            st.session_state.application_state['current_batch_progress'] = 1.0
        st.session_state.application_state['is_applying'] = False
        status_text.text(f'Metadata application process completed for {total_files_to_apply} files.')
        st.success(f'Finished applying metadata. Processed {files_processed_count} files.')
        if st.session_state.application_state['errors']:
            st.error('Some files encountered errors during metadata application:')
            for fid, err_msg in st.session_state.application_state['errors'].items():
                fname = all_files_info.get(str(fid), {}).get('name', f'File ID {fid}')
                st.write(f'- {fname}: {err_msg}')
        st.button('Clear Results and Go Back', on_click=lambda: setattr(st.session_state, 'current_page', 'View Results') or st.session_state.pop('application_state', None))
        st.rerun()
    elif st.session_state.application_state.get('is_applying', False) and total_files_to_apply == 0:
        st.session_state.application_state['is_applying'] = False
        st.warning('No files were set for application. Please check selections.')
        st.rerun()