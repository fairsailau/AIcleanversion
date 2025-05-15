# modules/validation_engine.py
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


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
        
    def get_rules_for_category_template(self, doc_category: Optional[str], template_id: Optional[str]) -> Dict[str, Any]:
        """Get validation rules for a specific document category and metadata template combination
        
        Args:
            doc_category: Document category (from document categorization)
            template_id: Metadata template ID (from metadata template selection)
            
        Returns:
            Dict containing the validation rules specific to this category-template combination
        """
        if not doc_category or not template_id:
            logger.debug("Missing category or template ID, cannot get category-template specific rules")
            return {"fields": [], "mandatory_fields": [], "cross_field_rules": []}
        
        # Load the full ruleset to access the category_template_rules
        try:
            with open(self.rules_config_path, 'r') as f:
                full_config = json.load(f)
                category_template_rules = full_config.get("category_template_rules", {})
        except Exception as e:
            logger.error(f"Error loading category-template rules: {e}")
            return {"fields": [], "mandatory_fields": [], "cross_field_rules": []}
            
        # Generate the rule ID that would have been used when creating these rules
        rule_id = f"{doc_category}|{template_id}|base"
        
        if rule_id in category_template_rules:
            logger.debug(f"Found specific rules for category '{doc_category}' with template '{template_id}'")
            return category_template_rules[rule_id]
        
        logger.debug(f"No specific rules found for category '{doc_category}' with template '{template_id}'")
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

    def validate(self, ai_response: Dict[str, Any], doc_type: Optional[str] = None, doc_category: Optional[str] = None, template_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate an AI response against validation rules based on document type and/or category-template combination
        
        Args:
            ai_response: AI extracted metadata to validate
            doc_type: Document type (e.g., Invoice, Contract, etc.)
            doc_category: Document category from document categorization (e.g., PII, Financial, etc.)
            template_id: Metadata template ID
        
        Returns:
            Dict containing validation results
        """
        # Load validation rules
        rules_loader = ValidationRuleLoader("config/validation_rules.json")
        
        # First, get rules for the document type
        doc_rules = rules_loader.get_rules_for_doc_type(doc_type)
        
        # Then, get rules specific to the category-template combination
        category_template_rules = rules_loader.get_rules_for_category_template(doc_category, template_id)
        
        # If AI response is not a dict, return validation error
        if not isinstance(ai_response, dict):
            logger.warning(f"AI response is not a dictionary. Cannot perform validation.")
            return {
                "field_validations": {},
                "mandatory_check": {"status": "Error", "message": "AI response not a dict"},
                "cross_field_check": {"status": "Error", "message": "AI response not a dict"}
            }

        # Initialize field validations
        field_validations = {}

        # 1. Validate fields based on document type rules and category-template rules
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

            # Get doc type field rules
            doc_type_field_rules = []
            for fr in doc_rules.get("fields", []):
                if fr.get("key") == field_key:
                    doc_type_field_rules = fr.get("rules", [])
                    break
            
            # Get category-template field rules (these take precedence)
            category_template_field_rules = []
            for fr in category_template_rules.get("fields", []):
                if fr.get("key") == field_key:
                    category_template_field_rules = fr.get("rules", [])
                    break
            
            # Combine rules with category-template rules taking precedence
            if category_template_field_rules:
                # If there are specific category-template rules for this field, use only those
                field_specific_rules = category_template_field_rules
                logger.debug(f"Using category-template specific rules for field {field_key}")
            else:
                # Otherwise use document type rules
                field_specific_rules = doc_type_field_rules
                if doc_type_field_rules:
                    logger.debug(f"Using document type rules for field {field_key}")
            
            # Validate field against combined rules
            is_valid, messages = self._validate_field(field_key, value_to_validate, field_specific_rules)
            field_validations[field_key] = {"is_valid": is_valid, "messages": messages}
        
        # 2. Check mandatory fields - use the union of both mandatory field lists
        doc_type_mandatory = doc_rules.get("mandatory_fields", [])
        category_template_mandatory = category_template_rules.get("mandatory_fields", [])
        
        # Combine mandatory fields with deduplication
        mandatory_fields_list = list(set(doc_type_mandatory + category_template_mandatory))
        mandatory_passed, missing_fields = self._check_mandatory_fields(ai_response, mandatory_fields_list)
        
        mandatory_check_result = {
            "status": "Passed" if mandatory_passed else "Failed",
            "missing_fields": missing_fields
        }
        
        # 3. Check cross-field rules - use both sets of cross-field rules
        doc_type_cross_rules = doc_rules.get("cross_field_rules", [])
        category_template_cross_rules = category_template_rules.get("cross_field_rules", [])
        
        # Combine cross-field rules
        cross_field_rules_list = doc_type_cross_rules + category_template_cross_rules
        cross_field_passed, failed_cross_rules = self._check_cross_field_rules(ai_response, cross_field_rules_list)
        
        cross_field_check_result = {
            "status": "Passed" if cross_field_passed else "Failed",
            "failed_rules": failed_cross_rules
        }
        
        validation_source = ""
        if doc_type and not (doc_category and template_id):
            validation_source = f"doc_type '{doc_type}'"
        elif doc_category and template_id and not doc_type:
            validation_source = f"category '{doc_category}' + template '{template_id}'"
        else:
            validation_source = f"doc_type '{doc_type}' + category '{doc_category}' + template '{template_id}'"
        
        logger.info(f"Validation for {validation_source}: Fields: {field_validations}, Mandatory: {mandatory_check_result}, Cross-field: {cross_field_check_result}")
        
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

