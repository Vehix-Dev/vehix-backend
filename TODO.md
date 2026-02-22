# TODO: Fix WebSocket Errors

## Completed Fixes
- [x] Fixed AttributeError in RiderConsumer.disconnect: Added check for self.group_name existence before discarding
- [x] Fixed AttributeError in RodieConsumer.disconnect: Added check for self.group_name existence before discarding

## Notes
- WebSocket rejections are due to authentication/role checks in connect() methods - this is expected behavior
- Bad Request for /api/requests/nearby/ is due to missing service_id parameter - this is expected validation
