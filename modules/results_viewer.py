import streamlit as st
import pandas as pd
from typing import Dict, List, Any
import json
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_confidence_color(confidence_level):
    """Get color based on confidence level."""
    if confidence_level == 'High':
        return 'green'
    elif confidence_level == 'Medium':
        return 'orange'
    elif confidence_level == 'Low':
        return 'red'
    else:
        return 'gray'

def view_results():
    """
    View and manage extraction results - ENHANCED WITH CONFIDENCE SCORES
    """
    st.title('View Results')
    if not hasattr(st.session_state, 'authenticated') or not hasattr(st.session_state, 'client') or (not st.session_state.authenticated) or (not st.session_state.client):
        st.error('Please authenticate with Box first')
        return
    if not hasattr(st.session_state, 'extraction_results'):
        st.session_state.extraction_results = {}
        logger.info('Initialized extraction_results in view_results')
    if not hasattr(st.session_state, 'selected_result_ids'):
        st.session_state.selected_result_ids = []
        logger.info('Initialized selected_result_ids in view_results')
    if not hasattr(st.session_state, 'metadata_config'):
        st.session_state.metadata_config = {'extraction_method': 'freeform', 'freeform_prompt': 'Extract key metadata from this document.', 'use_template': False, 'template_id': '', 'custom_fields': [], 'ai_model': 'azure__openai__gpt_4o_mini', 'batch_size': 5}
        logger.info('Initialized metadata_config in view_results')
    if not hasattr(st.session_state, 'extraction_results') or not st.session_state.extraction_results:
        st.warning('No extraction results available. Please process files first.')
        if st.button('Go to Process Files', key='go_to_process_files_btn'):
            st.session_state.current_page = 'Process Files'
            st.rerun()
        return
    st.write('Review and manage the metadata extraction results.')
    if not hasattr(st.session_state, 'results_filter'):
        st.session_state.results_filter = ''
    if not hasattr(st.session_state, 'confidence_filter'):
        st.session_state.confidence_filter = ['High', 'Medium', 'Low']
    st.subheader('Filter Results')
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.results_filter = st.text_input('Filter by file name', value=st.session_state.results_filter, key='filter_input')
    with col2:
        st.session_state.confidence_filter = st.multiselect('Filter by Confidence Level', options=['High', 'Medium', 'Low'], default=st.session_state.confidence_filter, key='confidence_filter_select')
    filtered_results = {}
    for file_id, result in st.session_state.extraction_results.items():
        processed_result = {'file_id': file_id, 'file_name': 'Unknown', 'result_data': {}, 'confidence_levels': {}}
        if hasattr(st.session_state, 'selected_files'):
            for file in st.session_state.selected_files:
                if file['id'] == file_id:
                    processed_result['file_name'] = file['name']
                    break
        logger.info(f'Processing result for file_id {file_id}: {(json.dumps(result) if isinstance(result, dict) else str(result))}')
        if isinstance(result, dict):
            processed_result['original_data'] = result
            if 'answer' in result:
                answer = result['answer']
                logger.info(f"Found 'answer' field in result: {answer}")
                if isinstance(answer, str):
                    try:
                        parsed_answer = json.loads(answer)
                        if isinstance(parsed_answer, dict):
                            logger.info(f'Successfully parsed answer as JSON dictionary: {parsed_answer}')
                            for key, value in parsed_answer.items():
                                if isinstance(value, dict) and 'value' in value and ('confidence' in value):
                                    processed_result['result_data'][key] = value['value']
                                    processed_result['confidence_levels'][key] = value['confidence']
                                    logger.info(f"Extracted field {key} with value '{value['value']}' and confidence '{value['confidence']}'")
                                else:
                                    processed_result['result_data'][key] = value
                                    processed_result['confidence_levels'][key] = 'Medium'
                                    logger.info(f"Field {key} doesn't have expected structure, using value '{value}' with default Medium confidence")
                        else:
                            logger.warning(f'Parsed answer is not a dictionary: {parsed_answer}')
                            processed_result['result_data'] = {'extracted_text': answer}
                    except json.JSONDecodeError as e:
                        logger.warning(f'Failed to parse answer as JSON: {e}. Using raw text.')
                        processed_result['result_data'] = {'extracted_text': answer}
                elif isinstance(answer, dict):
                    logger.info(f'Answer is already a dictionary: {answer}')
                    for key, value in answer.items():
                        if isinstance(value, dict) and 'value' in value and ('confidence' in value):
                            processed_result['result_data'][key] = value['value']
                            processed_result['confidence_levels'][key] = value['confidence']
                            logger.info(f"Extracted field {key} with value '{value['value']}' and confidence '{value['confidence']}'")
                        else:
                            processed_result['result_data'][key] = value
                            processed_result['confidence_levels'][key] = 'Medium'
                            logger.info(f"Field {key} doesn't have expected structure, using value '{value}' with default Medium confidence")
                else:
                    logger.warning(f'Answer is neither string nor dictionary: {type(answer)}. Using as is.')
                    processed_result['result_data'] = {'extracted_text': str(answer)}
            elif 'items' in result and isinstance(result['items'], list) and (len(result['items']) > 0):
                item = result['items'][0]
                logger.info(f"Found 'items' array in result, processing first item: {item}")
                if isinstance(item, dict) and 'answer' in item:
                    answer = item['answer']
                    logger.info(f"Found 'answer' field in item: {answer}")
                    if isinstance(answer, str):
                        try:
                            parsed_answer = json.loads(answer)
                            if isinstance(parsed_answer, dict):
                                logger.info(f'Successfully parsed item answer as JSON dictionary: {parsed_answer}')
                                for key, value in parsed_answer.items():
                                    if isinstance(value, dict) and 'value' in value and ('confidence' in value):
                                        processed_result['result_data'][key] = value['value']
                                        processed_result['confidence_levels'][key] = value['confidence']
                                        logger.info(f"Extracted field {key} with value '{value['value']}' and confidence '{value['confidence']}'")
                                    else:
                                        processed_result['result_data'][key] = value
                                        processed_result['confidence_levels'][key] = 'Medium'
                                        logger.info(f"Field {key} doesn't have expected structure, using value '{value}' with default Medium confidence")
                            else:
                                logger.warning(f'Parsed item answer is not a dictionary: {parsed_answer}')
                                processed_result['result_data'] = {'extracted_text': answer}
                        except json.JSONDecodeError as e:
                            logger.warning(f'Failed to parse item answer as JSON: {e}. Using raw text.')
                            processed_result['result_data'] = {'extracted_text': answer}
                    elif isinstance(answer, dict):
                        logger.info(f'Item answer is already a dictionary: {answer}')
                        for key, value in answer.items():
                            if isinstance(value, dict) and 'value' in value and ('confidence' in value):
                                processed_result['result_data'][key] = value['value']
                                processed_result['confidence_levels'][key] = value['confidence']
                                logger.info(f"Extracted field {key} with value '{value['value']}' and confidence '{value['confidence']}'")
                            else:
                                processed_result['result_data'][key] = value
                                processed_result['confidence_levels'][key] = 'Medium'
                                logger.info(f"Field {key} doesn't have expected structure, using value '{value}' with default Medium confidence")
                    else:
                        logger.warning(f'Item answer is neither string nor dictionary: {type(answer)}. Using as is.')
                        processed_result['result_data'] = {'extracted_text': str(answer)}
            elif any((key.endswith('_confidence') for key in result.keys())):
                logger.info(f'Found fields with _confidence suffix in result')
                confidence_fields = [key for key in result.keys() if key.endswith('_confidence')]
                logger.info(f'Confidence fields: {confidence_fields}')
                for key, value in result.items():
                    if key.endswith('_confidence'):
                        base_key = key[:-len('_confidence')]
                        if base_key in result:
                            processed_result['result_data'][base_key] = result[base_key]
                            processed_result['confidence_levels'][base_key] = value
                            logger.info(f"Extracted field {base_key} with value '{result[base_key]}' and confidence '{value}'")
                    elif not key.startswith('_') and (not any((key == field[:-len('_confidence')] for field in confidence_fields))):
                        processed_result['result_data'][key] = value
                        processed_result['confidence_levels'][key] = 'Medium'
                        logger.info(f"Field {key} has no confidence field, using value '{value}' with default Medium confidence")
            if not processed_result['result_data']:
                logger.warning(f'No structured data found in result, looking for alternative fields')
                for key in ['extracted_data', 'data', 'result', 'metadata']:
                    if key in result and result[key]:
                        logger.info(f"Found potential data in field '{key}': {result[key]}")
                        if isinstance(result[key], dict):
                            processed_result['result_data'] = result[key]
                            for field_key in result[key].keys():
                                if field_key not in processed_result['confidence_levels']:
                                    processed_result['confidence_levels'][field_key] = 'Medium'
                            break
                        elif isinstance(result[key], str):
                            try:
                                parsed_data = json.loads(result[key])
                                if isinstance(parsed_data, dict):
                                    processed_result['result_data'] = parsed_data
                                    for field_key in parsed_data.keys():
                                        if field_key not in processed_result['confidence_levels']:
                                            processed_result['confidence_levels'][field_key] = 'Medium'
                                    break
                            except json.JSONDecodeError:
                                processed_result['result_data'] = {'extracted_text': result[key]}
                                processed_result['confidence_levels']['extracted_text'] = 'Medium'
                                break
                if not processed_result['result_data']:
                    logger.warning(f'No structured data found in any expected fields, using entire result')
                    processed_result['result_data'] = result
                    for field_key in result.keys():
                        if not field_key.startswith('_') and (not field_key.endswith('_confidence')):
                            processed_result['confidence_levels'][field_key] = 'Medium'
        else:
            logger.warning(f'Result is not a dictionary: {type(result)}. Using as text.')
            processed_result['result_data'] = {'extracted_text': str(result)}
            processed_result['confidence_levels']['extracted_text'] = 'Medium'
        if st.session_state.results_filter.lower() in processed_result['file_name'].lower():
            if not st.session_state.confidence_filter:
                filtered_results[file_id] = processed_result
            else:
                has_matching_confidence = False
                for confidence in processed_result['confidence_levels'].values():
                    if confidence in st.session_state.confidence_filter:
                        has_matching_confidence = True
                        break
                if has_matching_confidence:
                    filtered_results[file_id] = processed_result
    table_data = []
    for file_id, data in filtered_results.items():
        row = {'File Name': data['file_name'], 'File ID': file_id}
        for key, value in data['result_data'].items():
            if not key.startswith('_') and key != 'extracted_text':
                row[key] = value
                confidence_key = f'{key} Confidence'
                row[confidence_key] = data['confidence_levels'].get(key, 'N/A')
        table_data.append(row)
    df = pd.DataFrame(table_data)
    if not df.empty:
        base_cols = ['File Name', 'File ID']
        field_cols = sorted([col for col in df.columns if col not in base_cols and (not col.endswith(' Confidence'))])
        ordered_cols = base_cols + [item for field in field_cols for item in (field, f'{field} Confidence') if item in df.columns]
        df = df[ordered_cols]
    st.subheader('Extraction Results')
    tab1, tab2 = st.tabs(['Table View', 'Detailed View'])
    final_filtered_results = filtered_results
    with tab1:
        st.write(f'Showing {len(df)} of {len(st.session_state.extraction_results)} results')
        if not df.empty:
            st.dataframe(df.style.applymap(lambda x: f'color: {get_confidence_color(x)}', subset=[col for col in df.columns if col.endswith(' Confidence')]), use_container_width=True, hide_index=True)
            col1, col2 = st.columns(2)
            with col1:
                if st.button('Export as CSV', use_container_width=True, key='export_csv_btn'):
                    pass
            with col2:
                if st.button('Export as Excel', use_container_width=True, key='export_excel_btn'):
                    st.info('Excel export would be implemented in the full app')
        else:
            st.info('No results match the current filter')
    with tab2:
        file_options = [(file_id, result_data.get('file_name', 'Unknown')) for file_id, result_data in final_filtered_results.items()]
        if not file_options:
            st.info('No results match the current filter')
        else:
            file_options = [('', 'Select a file...')] + file_options
            selected_file_id_name = st.selectbox('Select a file to view details', options=file_options, format_func=lambda x: x[1], key='file_selector')
            selected_file_id = selected_file_id_name[0] if selected_file_id_name[0] else None
            if selected_file_id and selected_file_id in final_filtered_results:
                result_data = final_filtered_results[selected_file_id]
                st.write('### File Information')
                st.write(f"**File:** {result_data.get('file_name', 'Unknown')}")
                st.write(f'**File ID:** {selected_file_id}')
                st.write('### Extracted Metadata')
                extracted_data = {}
                confidence_levels = result_data.get('confidence_levels', {})
                if 'result_data' in result_data and result_data['result_data']:
                    if isinstance(result_data['result_data'], dict):
                        for key, value in result_data['result_data'].items():
                            if not key.startswith('_') and key != 'extracted_text':
                                extracted_data[key] = value
                        if 'extracted_text' in result_data['result_data']:
                            st.write('#### Extracted Text')
                            st.write(result_data['result_data']['extracted_text'])
                    elif isinstance(result_data['result_data'], str):
                        st.write('#### Extracted Text')
                        st.write(result_data['result_data'])
                if extracted_data:
                    st.write('#### Key-Value Pairs')
                    for key, value in extracted_data.items():
                        confidence = confidence_levels.get(key, 'N/A')
                        confidence_color = get_confidence_color(confidence)
                        col_input, col_confidence = st.columns([3, 1])
                        with col_input:
                            if isinstance(value, list):
                                new_value = st.multiselect(key, options=value + ['Option 1', 'Option 2', 'Option 3'], default=value, key=f'edit_{selected_file_id}_{key}', help=f'Edit the value for {key}')
                            else:
                                new_value = st.text_input(key, value=str(value) if value is not None else '', key=f'edit_{selected_file_id}_{key}', help=f'Edit the value for {key}')
                        with col_confidence:
                            st.markdown(f"<span style='color:{confidence_color}; font-weight:bold;'>({confidence})</span>", unsafe_allow_html=True)
                        if new_value != value:
                            if selected_file_id in st.session_state.extraction_results:
                                original_result = st.session_state.extraction_results[selected_file_id]
                                if 'result_data' in result_data and isinstance(result_data['result_data'], dict):
                                    result_data['result_data'][key] = new_value
                                logger.info(f'Value for {key} in file {selected_file_id} changed to {new_value}')
                else:
                    st.write('No structured data extracted')
                if 'original_data' in result_data:
                    st.write('### Raw Result Data (Debug View)')
                    with st.expander('Show Raw Data'):
                        st.json(result_data['original_data'])
    st.subheader('Batch Operations')
    displayed_file_ids = list(final_filtered_results.keys())
    col1, col2 = st.columns(2)
    with col1:
        if st.button('Select All', use_container_width=True, key='select_all_btn'):
            st.session_state.selected_result_ids = displayed_file_ids
            st.rerun()
    with col2:
        if st.button('Deselect All', use_container_width=True, key='deselect_all_btn'):
            st.session_state.selected_result_ids = []
            st.rerun()
    st.write(f'Selected {len(st.session_state.selected_result_ids)} of {len(displayed_file_ids)} results')
    if st.button('Apply Metadata', use_container_width=True, key='apply_metadata_btn'):
        if not st.session_state.selected_result_ids:
            st.warning('Please select at least one file to apply metadata.')
        else:
            from modules.direct_metadata_application_enhanced_fixed import apply_metadata_direct
            apply_metadata_direct()