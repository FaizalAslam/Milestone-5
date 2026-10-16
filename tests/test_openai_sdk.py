import json
import httpx2
from openai import OpenAI
from groww.analysis import Engine
from groww.models import Taxonomy


def test_responses_sdk_parses_strict_schema_without_network(tmp_path):
    requests = []
    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        text = json.dumps({'themes': [{'id': f'T{i}', 'name': name, 'description': name}
                                      for i, name in enumerate(['Fees', 'Support', 'Orders'], 1)]})
        return httpx2.Response(200, json={
            'id': 'resp_test_only', 'object': 'response', 'created_at': 1792108800,
            'status': 'completed', 'model': 'gpt-5-mini', 'error': None, 'incomplete_details': None,
            'output': [{'id': 'msg_test_only', 'type': 'message', 'status': 'completed',
                        'role': 'assistant', 'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}],
            'parallel_tool_calls': False, 'tool_choice': 'auto', 'tools': []})
    engine = Engine('test-key-not-a-real-secret', cache_root=tmp_path)
    engine.client = OpenAI(api_key='test-key-not-a-real-secret',
                           http_client=httpx2.Client(transport=httpx2.MockTransport(handle)))
    result = engine.ask(Taxonomy, 'Discover themes.', [{'review': 'test only'}])
    assert len(result.themes) == 3
    assert requests[0]['store'] is False
    assert requests[0]['text']['format']['strict'] is True
    assert requests[0]['text']['format']['type'] == 'json_schema'
    assert requests[0]['reasoning']['effort'] == 'low'
