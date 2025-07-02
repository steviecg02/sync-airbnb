from typing import Any, Union

def get_first_component(response: dict) -> dict:
    """
    Return the first component in a standard Airbnb GraphQL metrics response.
    Handles nesting: data → porygon → getPerformanceComponents → components[0]
    """
    return (
        response.get("data", {})
                .get("porygon", {})
                .get("getPerformanceComponents", {})
                .get("components", [{}])[0]
    )

def extract_numeric_value(value_dict: dict) -> float | int | None:
    """
    Safely extract a numeric value from a GraphQL value object, preferring doubleValue over longValue.
    Preserves 0.0 and 0, and returns None only if both are missing.
    """
    if not isinstance(value_dict, dict):
        return None
    if value_dict.get("doubleValue") is not None:
        return value_dict["doubleValue"]
    return value_dict.get("longValue")

def coerce_number(val: Any) -> int | float | Any:
    """
    Coerce string numbers to int or float. Leave other types alone.
    """
    if isinstance(val, str):
        try:
            return int(val) if val.isdigit() else float(val)
        except ValueError:
            return val
    return val