# Step-by-Step: Test New Fake Log Streaming Changes

## Step 1: Start the FastAPI Server

Open your terminal/command prompt and run:

```bash
cd e:\Personal Projects\oie
uvicorn app.main:app --reload
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

✅ **Keep this terminal open. You'll need it for testing.**

---

## Step 2: Test the Fake Log Generator (Direct)

Open a **new terminal** and run:

```bash
cd e:\Personal Projects\oie
python tests/test_fake_log_stream.py
```

This will:
- Generate 5 fake logs directly (no HTTP)
- Show you what the logs look like
- Test both generator types

**Expected output:**
```
================================================================================
Testing Fake Log Generator Directly
================================================================================

Generating 5 fake logs...
Log 1: [ERROR] database - Connection timeout while connecting to database
  Category: DATABASE
  Request ID: req_xxx
Log 2: [INFO] api-gateway - Request processed successfully
  Category: API_ERROR
  Request ID: req_yyy
Log 3: [WARNING] redis-cache - High memory usage detected
  Category: PERFORMANCE
  Request ID: req_zzz
Log 4: [CRITICAL] payment-service - Failed to process payment transaction
  Category: PAYMENT_FAILURE
  Request ID: req_abc
Log 5: [DEBUG] analytics-service - Cache cleared
  Category: PERFORMANCE
  Request ID: req_def
```

Press `Ctrl+C` to stop when done.

---

## Step 3: Test Streaming WITHOUT Analysis (Simpler)

In a **new terminal**, test the basic streaming:

```bash
curl "http://localhost:8000/api/v1/incidents/fake-log-stream?interval=0.5&num_logs=5&generator_type=realistic"
```

**Expected response:**
```
data: {"type":"log","log_count":1,"log":{"log_id":"log_xxx","level":"ERROR","service_name":"database","category":"DATABASE",...}}
data: {"type":"log","log_count":2,"log":{"log_id":"log_yyy","level":"INFO","service_name":"api-gateway","category":"API_ERROR",...}}
...
data: {"type":"complete","total_logs":5}
```

**What you're seeing:**
- SSE (Server-Sent Events) streaming
- Logs appearing one by one
- JSON data for each log

---

## Step 4: Test Streaming WITH Analysis (Main Feature)

### Option A: Using Postman (Recommended for Interview)

**1. Open Postman**

**2. Create new request:**
- Method: `POST`
- URL: `http://localhost:8000/api/v1/incidents/stream-analyze`

**3. Add these query parameters:**
```
duration: 30
logs_per_second: 2
error_rate: 0.1
generator_type: realistic
```

**4. Click "Send"**

**5. Watch the real-time stream:**

You'll see events like this:
```
Log #1: ERROR - database
   Category: DATABASE
   Request ID: req_xxx
   → Analyzed! Status: Analyzed, Severity: ERROR

Log #2: WARNING - api-gateway
   Category: API_ERROR
   Request ID: req_yyy
   → Analyzed! Status: Analyzed, Severity: WARNING

Log #3: INFO - redis-cache
   Category: PERFORMANCE
   Request ID: req_zzz
   → Analyzed! Status: Analyzed, Severity: INFO
...
Complete! Total logs: 60
```

**What's happening:**
- Logs arrive every ~0.5 seconds
- Each log is analyzed (0.5-2 second delay)
- Incident record is created in database
- Status changes to "Analyzed"
- Embedding is stored

### Option B: Using curl

```bash
curl -X POST "http://localhost:8000/api/v1/incidents/stream-analyze?duration=10&logs_per_second=3&error_rate=0.1"
```

You'll see the SSE stream with log events and analysis updates.

---

## Step 5: Check Database Results

**1. Create a new Postman request:**
- Method: `GET`
- URL: `http://localhost:8000/api/v1/incidents/?limit=10`

**2. Click "Send"**

**Expected response:**
```json
{
  "id": 1,
  "title": "Streamed Log #1",
  "description": "**Level:** ERROR | **Service:** database | **Category:** DATABASE\n\nConnection timeout...",
  "status": "Analyzed",
  "severity": "ERROR",
  "created_at": "2026-03-03T21:00:00Z"
}
```

**What to verify:**
✅ All 60 incidents were created
✅ Status is "Analyzed" (not "Analyzing")
✅ Severity is set correctly (ERROR, WARNING, etc.)
✅ Description contains log details
✅ Created_at timestamps are recent

**3. Check individual incident:**
- URL: `http://localhost:8000/api/v1/incidents/{id}`
- Replace `{id}` with an actual ID from the list
- Shows complete incident details

---

## Step 6: View Performance Metrics

**1. Create new Postman request:**
- Method: `GET`
- URL: `http://localhost:8000/api/v1/incidents/performance-metrics?hours=1`

**2. Click "Send"**

**Expected response:**
```json
{
  "period": {
    "start_time": "2026-03-03T20:00:00Z",
    "end_time": "2026-03-03T21:00:00Z",
    "hours": 1
  },
  "throughput": {
    "logs_per_second": 2.0,
    "logs_per_minute": 120.0,
    "logs_per_hour": 120
  },
  "processing_times": {
    "avg_seconds": 0.75,
    "max_seconds": 2.0,
    "min_seconds": 0.5
  },
  "errors": {
    "total_errors": 6,
    "error_rate_percentage": 10.0
  },
  "distribution": {
    "severity": {
      "ERROR": 6,
      "WARNING": 12,
      "INFO": 42
    },
    "categories": {
      "API_ERROR": 15,
      "DATABASE": 10,
      "NETWORK": 5,
      ...
    },
    "services": {
      "api-gateway": 20,
      "database": 15,
      "redis-cache": 10,
      ...
    }
  },
  "summary": {
    "total_incidents": 60,
    "average_processing_speed": "1.33 logs/second"
  }
}
```

**What the metrics show:**
- **Throughput**: How many logs/second
- **Processing Times**: Average, min, max
- **Error Rate**: Percentage of errors
- **Distribution**: Severity, categories, services

---

## Step 7: Test Different Scenarios

### Scenario 1: High Volume
**Postman request:**
```
POST http://localhost:8000/api/v1/incidents/stream-analyze
?duration=60&logs_per_second=10&error_rate=0.15
```
- Tests system at higher load
- More errors (15%)

### Scenario 2: Spiked Traffic
**Postman request:**
```
POST http://localhost:8000/api/v1/incidents/stream-analyze
?duration=60&logs_per_second=5&error_rate=0.1
```
- Uses spiked generator
- Creates burst patterns

### Scenario 3: High Error Rate
**Postman request:**
```
POST http://localhost:8000/api/v1/incidents/stream-analyze
?duration=30&logs_per_second=3&error_rate=0.3
```
- 30% error rate
- More CRITICAL logs

---

## Step 8: Clean Up Database

If you want to clear test data:

```bash
# Using Python
python -c "from app.db.session import SessionLocal; from app.models.incident import Incident; db = SessionLocal(); db.query(Incident).delete(); db.commit(); print('All test incidents deleted')"
```

Or via SQL:
```bash
# If using PostgreSQL directly
psql -U your_username -d oie -c "DELETE FROM incidents WHERE title LIKE 'Streamed Log #%';"
```

---

## Quick Checklist

- [x] Step 1: Server running on http://localhost:8000
- [x] Step 2: Generator test completed
- [x] Step 3: Basic streaming working
- [x] Step 4: Analysis streaming working
- [x] Step 5: Database has incident records
- [x] Step 6: Performance metrics showing data
- [x] Step 7: Different scenarios tested
- [x] Step 8: Test data cleaned up (optional)

---

## Troubleshooting

### Server won't start
- Check if port 8000 is already in use: `netstat -ano | findstr :8000`
- Install dependencies: `pip install -r requirements.txt`
- Check database connection

### No logs appearing
- Verify FastAPI server is running
- Check query parameters (duration > 0, logs_per_second > 0)
- Ensure error_rate is between 0-1

### Empty database
- Check if database connection is working
- Verify database migrations ran
- Check logs for database errors

### Performance too slow
- Reduce logs_per_second to 1 or 2
- Check database performance
- Ensure CrewAI API is responding

---

## What You Should See

**In Postman:**
✅ Real-time SSE events with logs
✅ Analysis updates for each log
✅ Completion message when done

**In Database:**
✅ 60 incident records (for 30 sec @ 2 logs/sec)
✅ Status = "Analyzed"
✅ Correct severity levels
✅ Descriptions with log details

**In Performance Metrics:**
✅ Throughput ~2 logs/sec
✅ Processing time 0.5-2 seconds
✅ Error rate ~10%
✅ Distribution across categories/services

---

## Ready for Interview Demo!

Your system is now ready for the 30-minute interview demo. Refer to:
- `docs/interview_demo_guide.md` - Full demo instructions
- `docs/fake_log_streaming_guide.md` - API documentation
- `tests/test_fake_log_stream.py` - Test script

**Good luck! 🚀**