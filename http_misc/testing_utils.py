from http_misc.http_utils import filter_list_by_key


def validate_dict_lists(expected: list[dict], actual: list[dict], key_field: str | None = 'id'):
    for expected_dict in expected:
        key_value = expected_dict.get(key_field)
        assert key_value is not None
        actual_dict = filter_list_by_key(actual, key_field, key_value)
        assert actual_dict is not None
        assert expected_dict == actual_dict


def validate_list_response(response_json, expected_ids, id_field_name: str | None = 'id'):
    """ Проверка списка ответа """
    expected_ids = {str(item) for item in expected_ids}
    expected_count = len(expected_ids)
    if 'results' in response_json:
        response_ids = {str(item[id_field_name]) for item in response_json['results']}

        assert 'count' in response_json

        actual_count = len(response_json['results'])
        assert actual_count == expected_count, f'Expected: {expected_count}\nActual: {actual_count}'

        actual_count = response_json['count']
        assert actual_count == expected_count, f'Expected: {expected_count}\nActual: {actual_count}'
    else:
        response_ids = {str(item[id_field_name]) for item in response_json}

    assert response_ids == expected_ids, f'Expected: {expected_ids}\nActual: {response_ids}'


class FieldValidators:
    def __init__(self, *args):
        self.validators = args


def validate_dict_fields(result: dict, valid_data: tuple | list):
    """Валидация полей json"""
    for row in valid_data:
        if len(row) < 2:
            raise ValueError(f'Invalid row: {row}')
        field_name = row[0]
        assert field_name in result, f'Field "{field_name}" not in result'
        if len(row) > 1:
            if isinstance(row[1], FieldValidators):
                validators = row[1].validators
            else:
                validators = [row[1]]

            for validator in validators:
                if callable(validator):
                    assert validator(result)
                else:
                    value = result[field_name]
                    assert validator == value, f"{field_name} \nExpected: {validator}\nActual: {value}"


class _IsNone:
    def __eq__(self, other):
        return other is None

    def __ne__(self, other):
        return other is not None

    def __repr__(self):
        return '<IS_NONE>'


class _IsNotNone:
    def __eq__(self, other):
        return other is not None

    def __ne__(self, other):
        return other is None

    def __repr__(self):
        return '<IS_NOT_NONE>'


IS_NONE = _IsNone()
IS_NOT_NONE = _IsNotNone()
