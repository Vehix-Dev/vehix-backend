import os

file_path = 'realtime/consumers.py'
with open(file_path, 'r') as f:
    content = f.read()

# Standardize RodieConsumer.offer_request
old_offer = """    async def offer_request(self, event):
        await self.send_json({
            "type": "OFFER_REQUEST",
            "data": event.get("data")
        })"""
new_offer = """    async def offer_request(self, event):
        await self.send_json({
            "type": "OFFER_REQUEST",
            "request": event.get("request")
        })"""
content =内容 = content.replace(old_offer, new_offer)

# Standardize RiderConsumer methods
replacements = {
    'async def request_accepted(self, event):\n        await self.send_json({"type": "REQUEST_UPDATE", "status": "ACCEPTED", "data": event.get("data")})': 
    'async def request_accepted(self, event):\n        await self.send_json({"type": "REQUEST_UPDATE", "status": "ACCEPTED", "request": event.get("request")})',
    
    'async def request_enroute(self, event):\n        await self.send_json({"type": "REQUEST_UPDATE", "status": "EN_ROUTE", "data": event.get("data")})':
    'async def request_enroute(self, event):\n        await self.send_json({"type": "REQUEST_UPDATE", "status": "EN_ROUTE", "request": event.get("request")})',
    
    'async def request_started(self, event):\n        await self.send_json({"type": "REQUEST_UPDATE", "status": "STARTED", "data": event.get("data")})':
    'async def request_started(self, event):\n        await self.send_json({"type": "REQUEST_UPDATE", "status": "STARTED", "request": event.get("request")})',
    
    'async def request_completed(self, event):\n        await self.send_json({"type": "REQUEST_UPDATE", "status": "COMPLETED", "data": event.get("data")})':
    'async def request_completed(self, event):\n        await self.send_json({"type": "REQUEST_UPDATE", "status": "COMPLETED", "request": event.get("request")})'
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(file_path, 'w') as f:
    f.write(content)
print("Updated realtime/consumers.py successfully")
