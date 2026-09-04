import pytest
from backend.app.providers.parsing import parse_agent_action

ALLOWED = {"click", "type", "scroll", "navigate_back", "wait", "finish", "fail"}


def test_plain_json():
    text = '{"action":"click","target":"button_01","reason":"go","confidence":0.8}'
    data = parse_agent_action(text, ALLOWED)
    assert data["action"] == "click"
    assert data["target"] == "button_01"


def test_json_fenced_with_language_tag():
    text = '```json\n{"action":"wait","reason":"thinking","confidence":0.5}\n```'
    data = parse_agent_action(text, ALLOWED)
    assert data["action"] == "wait"


def test_json_fenced_bare():
    text = '```\n{"action":"finish","reason":"done","confidence":0.9}\n```'
    data = parse_agent_action(text, ALLOWED)
    assert data["action"] == "finish"


def test_json_with_leading_prose():
    text = ('Here is my decision based on the observation:\n'
            '{"action":"click","target":"link_02","reason":"navigate","confidence":0.7}')
    data = parse_agent_action(text, ALLOWED)
    assert data["action"] == "click"
    assert data["target"] == "link_02"


def test_json_with_trailing_prose_containing_braces():
    text = ('{"action":"type","target":"input_01","text":"laptop","reason":"search",'
            '"confidence":0.9}\nNote: I might reconsider if {conditions} change later.')
    data = parse_agent_action(text, ALLOWED)
    assert data["action"] == "type"
    assert data["target"] == "input_01"


def test_json_with_leading_prose_containing_braces():
    # A brace-containing aside BEFORE the real JSON object used to make the
    # old greedy "first { to last }" regex grab the wrong span entirely.
    text = ('I was thinking about {alternate approaches} but decided on this:\n'
            '{"action":"click","target":"button_03","reason":"proceed","confidence":0.6}')
    data = parse_agent_action(text, ALLOWED)
    assert data["action"] == "click"
    assert data["target"] == "button_03"


def test_trailing_comma_repaired():
    text = '{"action":"scroll","reason":"see more","confidence":0.4,}'
    data = parse_agent_action(text, ALLOWED)
    assert data["action"] == "scroll"


def test_confidence_clamped_to_0_1():
    text = '{"action":"wait","reason":"pause","confidence":1.7}'
    data = parse_agent_action(text, ALLOWED)
    assert data["confidence"] == 1.0


def test_missing_target_for_click_rejected():
    with pytest.raises(ValueError):
        parse_agent_action('{"action":"click","reason":"go"}', ALLOWED)


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        parse_agent_action('{"action":"delete_everything","target":"x"}', ALLOWED)


def test_empty_output_rejected():
    with pytest.raises(ValueError):
        parse_agent_action("", ALLOWED)


def test_prose_only_no_json_rejected():
    with pytest.raises(ValueError):
        parse_agent_action("I think I should click the button now.", ALLOWED)


def test_ambiguous_multiple_distinct_objects_rejected():
    text = ('{"action":"click","target":"button_01","confidence":0.5}\n'
            'or maybe\n'
            '{"action":"click","target":"button_02","confidence":0.5}')
    with pytest.raises(ValueError):
        parse_agent_action(text, ALLOWED)


def test_repeated_identical_object_not_ambiguous():
    # The same object echoed twice (e.g. inside and outside a fence) is not
    # a genuine ambiguity — it should still parse.
    text = ('{"action":"wait","reason":"pause","confidence":0.5}\n'
            '{"action":"wait","reason":"pause","confidence":0.5}')
    data = parse_agent_action(text, ALLOWED)
    assert data["action"] == "wait"
