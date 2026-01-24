import requests
import time
import json
import asyncio
from jinja2 import Template
from tests import (
    scenario_login,
    scenario_create_request,
    scenario_accept_request,
    scenario_websocket_chat,
)

# Configure these before running
TEST_CONFIG = {
    'base_url': 'http://127.0.0.1:8000',
    'ws_base': 'ws://127.0.0.1:8000',
    'rider': {'username': 'rider1', 'password': 'password'},
    'rodie': {'username': 'rodie1', 'password': 'password'},
    'service_id': 1,
    'rider_coords': [6.5244, 3.3792],
}

RESULTS_FILE = 'e2e_results.json'
REPORT_FILE = 'report.html'
TEMPLATE_FILE = 'report_template.html'


def save_results(results):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)


def render_report(results):
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        tpl = Template(f.read())
    out = tpl.render(results=results)
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(out)
    print('Report written to', REPORT_FILE)


async def run_all():
    cfg = TEST_CONFIG
    results = []
    sess = requests.Session()

    # 1) Login rider
    r = await scenario_login(sess, cfg['base_url'], cfg['rider'])
    results.append(r)
    rider_token = r.get('response', {}).get('access') if r.get('ok') else None

    # 2) Login rodie
    r2 = await scenario_login(sess, cfg['base_url'], cfg['rodie'])
    results.append(r2)
    rodie_token = r2.get('response', {}).get('access') if r2.get('ok') else None

    # 3) Rider creates request
    if rider_token:
        cr = scenario_create_request(sess, cfg['base_url'], rider_token, cfg['rider_coords'], cfg['service_id'])
        results.append(cr)
        if cr.get('ok'):
            # Expect response with request id
            req_id = cr.get('response', {}).get('id') or cr.get('response', {}).get('request_id')
        else:
            req_id = None
    else:
        req_id = None

    # 4) Rodie accepts
    if rodie_token and req_id:
        ar = scenario_accept_request(sess, cfg['base_url'], rodie_token, req_id)
        results.append(ar)
    
    # 5) Websocket chat test
    if rodie_token and req_id:
        ws = await scenario_websocket_chat(cfg['ws_base'], rodie_token, req_id)
        results.append(ws)

    save_results(results)
    render_report({'results': results})


if __name__ == '__main__':
    asyncio.run(run_all())
