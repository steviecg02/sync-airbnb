from flatteners.utils import get_first_component, extract_numeric_value, coerce_number


def test_get_first_component_valid_structure():
    data = {
        "data": {
            "porygon": {
                "getPerformanceComponents": {"components": [{"mock": "component"}]}
            }
        }
    }
    assert get_first_component(data) == {"mock": "component"}


def test_get_first_component_missing_keys_returns_empty():
    data = {"data": {}}
    result = get_first_component(data)
    assert result == {}


def test_extract_numeric_value_with_double():
    val = {"doubleValue": 3.14}
    assert extract_numeric_value(val) == 3.14


def test_extract_numeric_value_with_long():
    val = {"longValue": 42}
    assert extract_numeric_value(val) == 42


def test_extract_numeric_value_with_non_dict_returns_none():
    assert extract_numeric_value("not_a_dict") is None


def test_extract_numeric_value_empty_dict_returns_none():
    assert extract_numeric_value({}) is None


def test_coerce_number_string_int():
    assert coerce_number("123") == 123


def test_coerce_number_string_float():
    assert coerce_number("12.34") == 12.34


def test_coerce_number_bad_string_returns_original():
    assert coerce_number("abc123") == "abc123"


def test_coerce_number_already_number():
    assert coerce_number(42.0) == 42.0
