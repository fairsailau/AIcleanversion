# modules/validation_engine.py
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union


logger = logging.getLogger(__name__)

class ValidationRuleLoader:
    def __init__(self, rules_config_path: str):
        self.rules_config_path = rules_config_path
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        try:
            with open(self.rules_config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Successfully loaded validation rules from {self.rules_config_path}")
                return {doc_type["name"]: doc_type for doc_type in config.get("document_types", [])}
        except FileNotFoundError:
            logger.error(f"Validation rules file not found at {self.rules_config_path}. Using empty ruleset.")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.rules_config_path}. Using empty ruleset.")
            return {}
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading validation rules: {e}. Using empty ruleset.")
            return {}

    def get_rules_for_doc_type(self, doc_type_name: Optional[str]) -> Dict[str, Any]:
        if not doc_type_name:
            doc_type_name = "Default"
        
        specific_rules = self.rules.get(doc_type_name)
        if specific_rules:
            logger.debug(f"Found specific rules for document type: {doc_type_name}")
            return specific_rules
        
        default_rules = self.rules.get("Default")
        if default_rules:
            logger.debug(f"No specific rules for {doc_type_name}, using 'Default' rules.")
            return default_rules
            
        logger.warning(f"No validation rules found for document type '{doc_type_name}' or 'Default'. Returning empty rules.")
        return {"fields": [], "mandatory_fields": [], "cross_field_rules": []}

class Validator:
    def __init__(self):
        pass

    def _validate_field(self, field_key: str, value: Any, rules: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        is_valid = True
        messages = []
        if value is None or (isinstance(value, str) and value == ""):
            return True, [] 

        for rule_detail in rules:
            rule_type = rule_detail.get("type")
            params = rule_detail.get("params", {})
            message = rule_detail.get("message", f"Validation failed for {rule_type}")

            if rule_type == "regex" and isinstance(value, str):
                if not re.match(params.get("pattern", ""), value):
                    is_valid = False
                    messages.append(message)
            elif rule_type == "minLength" and isinstance(value, str):
                if len(value) < params.get("limit", 0):
                    is_valid = False
                    messages.append(message)
            elif rule_type == "maxLength" and isinstance(value, str):
                if len(value) > params.get("limit", float('inf')):
                    is_valid = False
                    messages.append(message)
            elif rule_type == "dataType":
                expected_type = params.get("expected")
                if expected_type == "integer":
                    if not isinstance(value, int) and not (isinstance(value, str) and value.isdigit()):
                        is_valid = False
                        messages.append(message)
                elif expected_type == "float":
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        is_valid = False
                        messages.append(message)
                elif expected_type == "date":
                    date_format = params.get("format", "%Y-%m-%d")
                    try:
                        datetime.strptime(str(value), date_format)
                    except (ValueError, TypeError):
                        is_valid = False
                        messages.append(message)
                elif expected_type == "boolean":
                    if not isinstance(value, bool) and str(value).lower() not in ['true', 'false', 'yes', 'no', '1', '0']:
                        is_valid = False
                        messages.append(message)
            elif rule_type == "enum":
                allowed_values = params.get("values", [])
                if value not in allowed_values:
                    is_valid = False
                    messages.append(message)
        return is_valid, messages

    def _check_mandatory_fields(self, ai_response: Dict[str, Any], mandatory_fields: List[str]) -> Tuple[bool, List[str]]:
        missing = []
        for field_key in mandatory_fields:
            field_data_item = ai_response.get(field_key)
            value_to_check = None
            if isinstance(field_data_item, dict):
                value_to_check = field_data_item.get("value")
            elif isinstance(field_data_item, (str, int, float, bool)):
                value_to_check = field_data_item
            
            if value_to_check is None or (isinstance(value_to_check, str) and str(value_to_check).strip() == ""):
                missing.append(field_key)
        return not missing, missing
        
    def _check_cross_field_rules(self, ai_response: Dict[str, Any], cross_field_rules: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        all_passed = True
        failed_rules_details = []
        for rule in cross_field_rules:
            rule_name = rule.get("name", "Unnamed Cross-field Rule")
            if rule.get("type") == "dependent_existence":
                dependent_field_key = rule.get("dependent_field")
                trigger_field_key = rule.get("trigger_field")
                expected_trigger_value = rule.get("trigger_value")

                trigger_field_item = ai_response.get(trigger_field_key)
                actual_trigger_value = None
                if isinstance(trigger_field_item, dict):
                    actual_trigger_value = trigger_field_item.get("value")
                elif isinstance(trigger_field_item, (str, int, float, bool)):
                    actual_trigger_value = trigger_field_item
                
                if actual_trigger_value == expected_trigger_value:
                    dependent_field_item = ai_response.get(dependent_field_key)
                    actual_dependent_value = None
                    if isinstance(dependent_field_item, dict):
                        actual_dependent_value = dependent_field_item.get("value")
                    elif isinstance(dependent_field_item, (str, int, float, bool)):
                        actual_dependent_value = dependent_field_item
                        
                    if actual_dependent_value is None or (isinstance(actual_dependent_value, str) and str(actual_dependent_value).strip() == ""):
                        all_passed = False
                        failed_rules_details.append(f"{rule_name}: {dependent_field_key} must exist when {trigger_field_key} is {expected_trigger_value}.")
            elif rule.get("type") == "date_order":
                date_a_key = rule.get("date_a_key")
                date_b_key = rule.get("date_b_key")
                date_format = rule.get("format", "%Y-%m-%d")

                date_a_item = ai_response.get(date_a_key)
                date_b_item = ai_response.get(date_b_key)
                actual_date_a_val = None
                actual_date_b_val = None

                if isinstance(date_a_item, dict): actual_date_a_val = date_a_item.get("value")
                elif isinstance(date_a_item, (str, int, float, bool)): actual_date_a_val = date_a_item
                
                if isinstance(date_b_item, dict): actual_date_b_val = date_b_item.get("value")
                elif isinstance(date_b_item, (str, int, float, bool)): actual_date_b_val = date_b_item

                if actual_date_a_val and actual_date_b_val:
                    try:
                        date_a = datetime.strptime(str(actual_date_a_val), date_format)
                        date_b = datetime.strptime(str(actual_date_b_val), date_format)
                        if date_a >= date_b:
                            all_passed = False
                            failed_rules_details.append(f"{rule_name}: {date_a_key} ({actual_date_a_val}) must be before {date_b_key} ({actual_date_b_val}).")
                    except ValueError:
                        logger.warning(f"Could not compare dates for rule '{rule_name}' due to format issues.")
        return all_passed, failed_rules_details

    def validate(self, ai_response: Dict[str, Any], doc_rules: Dict[str, Any], doc_type: Optional[str]) -> Dict[str, Any]:
        field_validations = {}
        if not isinstance(ai_response, dict):
            logger.warning(f"AI response is not a dictionary for doc_type {doc_type}. Cannot perform validation.")
            return {
                "field_validations": {},
                "mandatory_check": {"status": "Error", "message": "AI response not a dict"},
                "cross_field_check": {"status": "Error", "message": "AI response not a dict"}
            }

        for field_key, field_data_item in ai_response.items():
            value_to_validate = None
            if isinstance(field_data_item, dict):
                value_to_validate = field_data_item.get("value")
            elif isinstance(field_data_item, (str, int, float, bool)):
                value_to_validate = field_data_item
            else:
                logger.warning(f"Field {field_key} has unexpected data type {type(field_data_item)}. Skipping validation for this field's value.")
                field_validations[field_key] = {"is_valid": False, "messages": ["Unexpected data type from AI for this field."]}
                continue

            field_specific_rules = []
            for fr in doc_rules.get("fields", []):
                if fr.get("key") == field_key:
                    field_specific_rules = fr.get("rules", [])
                    break
            is_valid, messages = self._validate_field(field_key, value_to_validate, field_specific_rules)
            field_validations[field_key] = {"is_valid": is_valid, "messages": messages}
        
        mandatory_fields_list = doc_rules.get("mandatory_fields", [])
        mandatory_passed, missing_fields = self._check_mandatory_fields(ai_response, mandatory_fields_list)
        mandatory_check_result = {
            "status": "Passed" if mandatory_passed else "Failed",
            "missing_fields": missing_fields
        }
        
        cross_field_rules_list = doc_rules.get("cross_field_rules", [])
        cross_field_passed, failed_cross_rules = self._check_cross_field_rules(ai_response, cross_field_rules_list)
        cross_field_check_result = {
            "status": "Passed" if cross_field_passed else "Failed",
            "failed_rules": failed_cross_rules
        }
        
        logger.info(f"Validation for doc_type '{doc_type}': Fields: {field_validations}, Mandatory: {mandatory_check_result}, Cross-field: {cross_field_check_result}")
        return {
            "field_validations": field_validations,
            "mandatory_check": mandatory_check_result,
            "cross_field_check": cross_field_check_result
        }

class ConfidenceAdjuster:
    def __init__(self, high_confidence_threshold=0.8, medium_confidence_threshold=0.5, low_confidence_penalty=0.2, validation_failure_penalty=0.3, mandatory_failure_penalty=0.4):
        self.high_confidence_threshold = high_confidence_threshold
        self.medium_confidence_threshold = medium_confidence_threshold
        self.low_confidence_penalty = low_confidence_penalty
        self.validation_failure_penalty = validation_failure_penalty
        self.mandatory_failure_penalty = mandatory_failure_penalty

    def _get_qualitative_confidence(self, score: float) -> str:
        if score >= self.high_confidence_threshold:
            return "High"
        elif score >= self.medium_confidence_threshold:
            return "Medium"
        else:
            return "Low"

    def adjust_confidence(self, ai_response: Dict[str, Any], validation_output: Dict[str, Any]) -> Dict[str, Any]:
        adjusted_confidences = {}
        if not isinstance(ai_response, dict):
            logger.warning("AI response is not a dictionary. Cannot adjust confidence.")
            return {}

        for field_key, field_data_item in ai_response.items():
            original_confidence_score = 0.0
            # value_for_context = None # Not strictly needed here unless for more detailed logging

            if isinstance(field_data_item, dict):
                original_confidence_score = field_data_item.get("confidenceScore", 0.0)
                # value_for_context = field_data_item.get("value")
            elif isinstance(field_data_item, (str, int, float, bool)):
                original_confidence_score = 0.5 # Neutral default for unknown AI confidence
                # value_for_context = field_data_item
                logger.info(f"Field {field_key} has a primitive value '{field_data_item}' without explicit AI confidence. Assigning default original score: {original_confidence_score}.")
            else:
                logger.warning(f"Unexpected data type for field {field_key} in confidence adjustment: {type(field_data_item)}. Defaulting score to 0.0.")
            
            if not isinstance(original_confidence_score, (int, float)):
                try:
                    original_confidence_score = float(original_confidence_score)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid confidence score format for {field_key} (value: {original_confidence_score}). Defaulting to 0.0.")
                    original_confidence_score = 0.0
            
            adjusted_score = original_confidence_score
            field_validation_info = validation_output.get("field_validations", {}).get(field_key)
            
            if field_validation_info and not field_validation_info["is_valid"]:
                adjusted_score -= self.validation_failure_penalty
                logger.debug(f"Applied validation failure penalty to {field_key}. Score: {original_confidence_score} -> {adjusted_score}")
            
            adjusted_score = max(0, min(1, adjusted_score)) # Ensure score is between 0 and 1
            
            adjusted_confidences[field_key] = {
                "original_score": original_confidence_score,
                "original_qualitative": self._get_qualitative_confidence(original_confidence_score),
                "adjusted_score": round(adjusted_score, 3),
                "adjusted_qualitative": self._get_qualitative_confidence(adjusted_score),
                "validation_messages": field_validation_info["messages"] if field_validation_info else []
            }
        return adjusted_confidences

    def get_overall_document_status(self, adjusted_confidence_output: Dict[str, Any], validation_output: Dict[str, Any]) -> Dict[str, Any]:
        messages = []
        overall_confidence_qualitative = "High"
        num_low_confidence_fields = 0
        num_medium_confidence_fields = 0
        total_fields = len(adjusted_confidence_output)

        if not total_fields:
            return {"status": "Undetermined", "messages": ["No metadata fields processed for overall status."]}

        for field_key, conf_data in adjusted_confidence_output.items():
            if conf_data["adjusted_qualitative"] == "Low":
                num_low_confidence_fields += 1
            elif conf_data["adjusted_qualitative"] == "Medium":
                num_medium_confidence_fields += 1
        
        if num_low_confidence_fields > 0:
            overall_confidence_qualitative = "Low"
            messages.append(f"{num_low_confidence_fields}/{total_fields} fields have Low adjusted confidence.")
        elif num_medium_confidence_fields > 0 :
             overall_confidence_qualitative = "Medium"
             messages.append(f"{num_medium_confidence_fields}/{total_fields} fields have Medium adjusted confidence (no Low confidence fields).")
        else: 
            messages.append("All fields have High adjusted confidence.")
        
        mandatory_check = validation_output.get("mandatory_check", {})
        if mandatory_check.get("status") == "Failed":
            messages.append(f"Mandatory fields missing: {', '.join(mandatory_check.get('missing_fields', []))}")
            if overall_confidence_qualitative != "Low": # Downgrade if not already Low
                 overall_confidence_qualitative = "Medium" # Even if High, mandatory failure makes it Medium at best
        
        cross_field_check = validation_output.get("cross_field_check", {})
        if cross_field_check.get("status") == "Failed":
            messages.append(f"Cross-field validation rules failed: {', '.join(cross_field_check.get('failed_rules', []))}")
            if overall_confidence_qualitative != "Low": # Downgrade if not already Low
                 overall_confidence_qualitative = "Medium"
        
        if not messages and overall_confidence_qualitative == "High": # Only if no other issues
            messages.append("Overall document status appears good based on current checks.")
        elif not messages: # Default message if no specific issues but not High (e.g. all Medium)
            messages.append(f"Document status is {overall_confidence_qualitative}.")
            
        return {"status": overall_confidence_qualitative, "messages": messages}

