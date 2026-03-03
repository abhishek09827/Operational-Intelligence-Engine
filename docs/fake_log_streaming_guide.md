# Fake Log Streaming Guide

This guide explains how to use the fake log streaming feature in the Operational Intelligence Engine.

## Overview

The fake log generator creates realistic log entries that can be streamed in real-time. This is useful for:
- Testing the log analysis system
- Demonstrating the system capabilities
- Load testing the streaming infrastructure
- Frontend development and testing

## Available Endpoints

### 1. Stream Fake Logs (No Analysis)

**Endpoint:** `GET /api/v1/incidents/fake-log-stream`

Stream raw fake logs without any analysis.

**Parameters:**
- `interval` (float, optional): Seconds between logs (default: 1.0)
- `num_logs` (int, optional): Number of logs to stream (default: 100)
- `generator_type` (str, optional): Type of generator ('realistic' or 'spiked') (default: 'realistic')

**Example:**
```bash
curl "http://localhost:8000/api/v1/incidents/fake-log-stream?interval=0.5&num_logs=50&generator_type=spiked"
```

**Response:** Server-Sent Events (SSE) stream with log data:
```
data: {"type":"log","log_count":1,"log":{"log_id":"log_xxx","level":"ERROR","service_name":"api-gateway",...}}

data: {"type":"log","log_count":2,"log":{"log_id":"log_yyy","level":"INFO","service_name":"database",...}}
...
data: {"type":"complete","total_logs":50}
```

### 2. Stream Logs with Real-Time Analysis

**Endpoint:** `POST /api/v1/incidents/stream-analyze`

Stream fake logs and analyze each one in real-time, creating incident records.

**Parameters:**
- `generator_type` (str, optional): Type of generator ('realistic', 'spiked') (default: 'realistic')
- `duration` (int, optional): Duration in seconds to stream logs (default: 60)
- `logs_per_second` (int, optional): Number of logs per second (default: 1)
- `error_rate` (float, optional): Probability of ERROR/CRITICAL logs (default: 0.05)

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/incidents/stream-analyze?duration=30&logs_per_second=2&error_rate=0.1"
```

**Response:** Server-Sent Events (SSE) stream with log and analysis data:
```
data: {"type":"log","log_count":1,"incident_id":1,"log":{...}}

data: {"type":"analysis_update","incident_id":1,"log_count":1,"status":"Analyzed","severity":"ERROR"}

data: {"type":"log","log_count":2,"incident_id":2,"log":{...}}

data: {"type":"analysis_update","incident_id":2,"log_count":2,"status":"Analyzed","severity":"WARNING"}
...
data: {"type":"complete","total_logs":60,"message":"Streaming complete. Processed 60 logs."}
```

## Generators

### Realistic Stream

Generates a steady stream of logs with normal variation:
- Random intervals (0.8-1.2x base interval)
- Mix of all log levels
- Various services
- Realistic error patterns

**Use case:** Normal system load simulation

### Spiked Stream

Generates logs with random spikes in activity:
- Occasional bursts of multiple logs
- Can simulate traffic spikes or failures
- Higher error rate during spikes

**Use case:** Testing with load spikes

## Event Types

### Log Event
Sent when a new log is generated:
```json
{
  "type": "log",
  "log_count": 1,
  "incident_id": 1,
  "log": {
    "log_id": "log_xxx",
    "timestamp": "2026-03-03T20:00:00Z",
    "level": "ERROR",
    "service_name": "api-gateway",
    "category": "API_ERROR",
    "request_id": "req_xxx",
    "message": "Connection timeout while connecting to database"
  }
}
```

### Analysis Update Event
Sent when a log is analyzed and an incident is created:
```json
{
  "type": "analysis_update",
  "incident_id": 1,
  "log_count": 1,
  "status": "Analyzed",
  "severity": "ERROR"
}
```

### Complete Event
Sent when streaming is finished:
```json
{
  "type": "complete",
  "total_logs": 60,
  "message": "Streaming complete. Processed 60 logs."
}
```

## Testing

Run the comprehensive test script:

```bash
cd e:\Personal Projects\oie
python tests/test_fake_log_stream.py
```

This will:
1. Test the generator directly (without HTTP)
2. Stream fake logs without analysis
3. Stream logs with real-time analysis
4. Verify incidents in the database
5. List all processed incidents

## Example Usage in Python

```python
import requests
import json

# Stream fake logs with analysis
response = requests.post(
    "http://localhost:8000/api/v1/incidents/stream-analyze",
    params={
        "duration": 30,
        "logs_per_second": 2,
        "error_rate": 0.1
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        data = json.loads(line)
        
        if data['type'] == 'log':
            print(f"New log from {data['log']['service_name']}")
            
        elif data['type'] == 'analysis_update':
            print(f"Analyzed! Status: {data['status']}, Severity: {data['severity']}")
            
        elif data['type'] == 'complete':
            print(f"Done! Processed {data['total_logs']} logs")
            break
```

## Log Categories

The generator creates logs with various categories:
- `API_ERROR`: API endpoint failures
- `DATABASE`: Database issues
- `NETWORK`: Network problems
- `PAYMENT_FAILURE`: Payment processing errors
- `TIMEOUT`: Request timeouts
- `PERFORMANCE`: Performance issues

## Error Levels

Logs have different severity levels:
- `DEBUG`: Debug information
- `INFO`: General information
- `WARNING`: Warnings
- `ERROR`: Errors
- `CRITICAL`: Critical failures

## Integration with Existing Features

The streamed logs are automatically:
1. Saved to the database as incident records
2. Analyzed and categorized
3. Stored with embeddings for RAG
4. Available through the regular incident endpoints

You can view the results using:
- `GET /api/v1/incidents/{id}` - Get specific incident
- `GET /api/v1/incidents/` - List all incidents
- `GET /api/v1/incidents/{id}/analysis` - Get analysis details

## Performance Considerations

- **Duration**: Default 60 seconds of streaming
- **Logs per second**: Default 1 log/second
- **Error rate**: Default 5% chance of ERROR/CRITICAL
- **Analysis delay**: 0.5-2 seconds per log

Adjust these parameters based on your testing needs:
```bash
# High volume test
curl -X POST "http://localhost:8000/api/v1/incidents/stream-analyze?logs_per_second=10&duration=60"

# Heavy load test
curl -X POST "http://localhost:8000/api/v1/incidents/stream-analyze?logs_per_second=5&error_rate=0.2&duration=120"
```

## Troubleshooting

### Server not responding
Make sure the FastAPI server is running:
```bash
cd e:\Personal Projects\oie
uvicorn app.main:app --reload
```

### Empty response
Check if the generator type is valid:
- `realistic` - Normal logs
- `spiked` - Logs with spikes

### Stream stops prematurely
Increase the timeout or check for errors in the response headers.

## Future Enhancements

Planned improvements:
- [ ] Custom log patterns
- [ ] Real-time metrics and statistics
- [ ] WebSocket support for bidirectional communication
- [ ] Export streaming data to files
- [ ] Configurable log format (JSON, CSV, plain text)