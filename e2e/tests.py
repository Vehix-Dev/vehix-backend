import time
import json
import asyncio
from typing import Dict, Any

# Lightweight scenario helpers that runner.py will call.
# Each scenario returns a dict with {'name', 'ok', 'details'}

async def scenario_login(session, base_url, credentials):
    name = f"Login {credentials['username']}"
    try:
        resp = session.post(f"{base_url}/api/auth/login/", json={
            'username': credentials['username'],
            'password': credentials['password']
        })
        data = resp.json()
        ok = resp.status_code == 200 and 'access' in data
        return {'name': name, 'ok': ok, 'response': data, 'status': resp.status_code}
    except Exception as e:
        return {'name': name, 'ok': False, 'error': str(e)}


def scenario_create_request(session, base_url, token, rider_coords, service_id):
    name = 'Create ServiceRequest'
    headers = {'Authorization': f'Bearer {token}'}
    try:
        resp = session.post(f"{base_url}/api/requests/create/", json={
            'service_type': service_id,
            'rider_lat': rider_coords[0],
            'rider_lng': rider_coords[1]
        }, headers=headers)
        data = resp.json()
        ok = resp.status_code in (200, 201)
        return {'name': name, 'ok': ok, 'status': resp.status_code, 'response': data}
    except Exception as e:
        return {'name': name, 'ok': False, 'error': str(e)}


def scenario_accept_request(session, base_url, token, request_id):
    name = 'Rodie Accept Request'
    headers = {'Authorization': f'Bearer {token}'}
    try:
        resp = session.post(f"{base_url}/api/requests/{request_id}/accept/", headers=headers)
        data = resp.json()
        ok = resp.status_code == 200
        return {'name': name, 'ok': ok, 'status': resp.status_code, 'response': data}
    except Exception as e:
        return {'name': name, 'ok': False, 'error': str(e)}


async def scenario_websocket_chat(ws_url, token, request_id):
    """Connect to Channels via WebSocket and send/receive a chat message."""
    name = 'WebSocket Chat'
    import websocket
    try:
        headers = [f'Authorization: Bearer {token}']
        ws = websocket.create_connection(f"{ws_url}/ws/requests/{request_id}/", header=headers, timeout=10)
        # send a chat (protocol depends on frontend; here we use a simple JSON packet)
        msg = json.dumps({'type': 'CHAT', 'request_id': request_id, 'text': 'Hello from E2E test'})
        ws.send(msg)
        # wait for one message
        result = ws.recv()
        ws.close()
        return {'name': name, 'ok': True, 'response': result}
    except Exception as e:
        return {'name': name, 'ok': False, 'error': str(e)}
