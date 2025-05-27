# Box Metadata AI: LLM Self-Reporting Confidence Implementation

## Overview

This document provides a comprehensive guide to the implementation of confidence scoring in the Box Metadata AI application. The solution uses Box AI agent overrides to instruct the AI model to self-report confidence levels for each extracted metadata field.

## Implementation Details

### 1. Confidence Scoring Approach

The implementation uses the **LLM Self-Reporting** approach, where we explicitly instruct the Box AI model to:
- Provide a confidence level for each extracted field
- Use a standardized scale of "High", "Medium", or "Low" confidence
- Return both the extracted value and confidence level in a structured format

### 2. Key Components Modified

#### 2.1 Metadata Extraction Module (`metadata_extraction.py`)

- **AI Agent Configuration**: Added system messages to both structured and freeform extraction methods that instruct the AI model to include confidence levels
- **Response Processing**: Added logic to parse the AI responses and extract both values and confidence levels
- **Data Structure**: Modified to store confidence levels alongside extracted values using `field_name_confidence` naming convention
- **Confidence Origin Tracking**: Introduced a `confidence_origin` field for each extracted metadata value. This field tracks the source and rationale behind the assigned confidence score.
- **Defaulting Logic**: If the AI fails to provide a confidence score for a field, or if the provided score is not one of the standard "High", "Medium", or "Low" values, the system defaults the confidence (typically to "Medium") and sets the `confidence_origin` to indicate the reason for this defaulting (e.g., `default_no_confidence`, `default_invalid_confidence`).

```python
# Example of AI agent configuration with confidence instructions
ai_agent = {
    "type": "ai_agent_extract_structured",
    "long_text": {
        "model": ai_model,
        "mode": "default",
        "system_message": "You are an AI assistant specialized in extracting metadata from documents based on provided field definitions. For each field, analyze the document content and extract the corresponding value. CRITICALLY IMPORTANT: Respond for EACH field with a JSON object containing two keys: 1. \"value\": The extracted metadata value as a string. 2. \"confidence\": Your confidence level for this specific extraction, chosen from ONLY these three options: \"High\", \"Medium\", or \"Low\". Base your confidence on how certain you are about the extracted value given the document content and field definition. Example Response for a field: {\"value\": \"INV-12345\", \"confidence\": \"High\"}"
    },
    "basic_text": {
        "model": ai_model,
        "mode": "default",
        "system_message": "You are an AI assistant specialized in extracting metadata from documents based on provided field definitions. For each field, analyze the document content and extract the corresponding value. CRITICALLY IMPORTANT: Respond for EACH field with a JSON object containing two keys: 1. \"value\": The extracted metadata value as a string. 2. \"confidence\": Your confidence level for this specific extraction, chosen from ONLY these three options: \"High\", \"Medium\", or \"Low\". Base your confidence on how certain you are about the extracted value given the document content and field definition. Example Response for a field: {\"value\": \"INV-12345\", \"confidence\": \"High\"}"
    }
}
```

#### 2.2 Results Viewer Module (`results_viewer.py`)

- **Confidence Color Coding**: Added a function to assign colors based on confidence levels (High=green, Medium=orange, Low=red)
- **Confidence Filtering**: Added a multi-select filter to allow users to filter results by confidence level
- **Table View Enhancement**: Added confidence columns next to each field column with appropriate color coding
- **Detailed View Enhancement**: Added color-coded confidence indicators next to each field label
- **Visual Cue for Defaulted Confidence**: In the UI, confidence scores that were defaulted by the script (i.e., where `confidence_origin` is not `ai_provided`) are displayed with an asterisk (e.g., "Medium*") and an explanatory tooltip is available, providing transparency into the confidence score's source.

### 2.3 Understanding Confidence Origin

The `confidence_origin` field, stored alongside each extracted metadata value and its confidence score, provides crucial context about how the confidence level was determined. This helps in interpreting the reliability of the AI's output.

Possible `confidence_origin` values include:

*   `ai_provided`: The confidence score ("High", "Medium", or "Low") was directly provided by the Box AI model as per the instructions.
*   `default_no_confidence`: The AI extracted a value for the field but did not provide any confidence score. The system defaulted the confidence (e.g., to "Medium").
*   `default_invalid_confidence`: The AI provided a confidence score, but it was not one of the expected "High", "Medium", or "Low" values. The system defaulted the confidence (e.g., to "Medium").
*   `default_null_value`: The AI returned a null or empty value for the field, suggesting very low certainty. The system assigned a default confidence (e.g., "Low" or "Medium") and may store the value as null/empty.
*   `default_parsing_fallback`: The AI's response for a field was not in the expected nested `{"value": ..., "confidence": ...}` structure, but the system was able to extract a value. Confidence was defaulted.
*   `default_error_processing`: An error occurred within the script while processing a specific field's data from the AI. Confidence was defaulted, typically to "Low".
*   `error_default`: An error occurred during the overall processing of the file in `modules/processing.py`, leading to a default confidence assignment for any fields that might have been partially processed or are being presented in an error state.
*   `unknown_origin`: A fallback value if the origin could not be determined, indicating a potential gap in origin tracking for a specific scenario.

When reviewing extracted metadata, especially if a confidence score is displayed with an asterisk (e.g., "Medium*") in the UI, checking the `confidence_origin` (if exposed in detailed views or logs) can provide insight into why the score might not directly reflect the AI's explicit rating.

### 3. User Experience Improvements

- **Visual Indicators**: Color-coded confidence levels make it easy to identify fields with varying levels of confidence
- **Filtering Capability**: Users can filter results to focus on fields with specific confidence levels
- **Integrated Display**: Confidence information is seamlessly integrated into both table and detailed views

## How to Use

1. **Process Files**: The extraction process now automatically includes confidence scoring
2. **View Results**: Navigate to the "View Results" page to see extracted metadata with confidence levels
3. **Filter by Confidence**: Use the "Filter by Confidence Level" dropdown to focus on specific confidence levels
4. **Review Detailed Information**: In the detailed view, each field displays its confidence level in color-coded format

## Technical Notes

- The confidence scoring is implemented using Box AI agent overrides, specifically the `system_message` parameter
- The implementation preserves all existing functionality while adding the confidence scoring feature
- Both structured (template-based) and freeform extraction methods support confidence scoring
- The solution is designed to gracefully handle cases where confidence information is not available

## Future Enhancements

Potential future improvements to the confidence scoring feature:

1. **Confidence Thresholds**: Allow users to set minimum confidence thresholds for automatic metadata application
2. **Confidence Aggregation**: Add overall document confidence scores based on individual field confidence
3. **Confidence Improvement Suggestions**: Provide recommendations for improving low-confidence extractions
4. **Confidence Trend Analysis**: Track confidence levels across documents to identify patterns

## Conclusion

The LLM self-reporting confidence implementation enhances the Box Metadata AI application by providing users with transparency into the AI's certainty about extracted metadata. This helps users make more informed decisions about whether to trust and apply the extracted metadata to their Box files.
