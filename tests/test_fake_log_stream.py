"""
Test script for fake log streaming functionality
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
import json
import time
import asyncio
from typing import AsyncGenerator
from app.generators.fake_log_generator import fake_log_generator

async def test_fake_log_stream():
    """Test the fake log streaming endpoint"""
    base_url = "http://localhost:8000"
    
    print("=" * 80)
    print("Testing Fake Log Streaming")
    print("=" * 80)
    
    # Test 1: Stream fake logs without analysis
    print("\n[Test 1] Streaming fake logs (no analysis)...")
    print("-" * 80)
    
    response = requests.get(
        f"{base_url}/api/v1/incident/fake-log-stream",
        params={
            "interval": 0.5,
            "num_logs": 10,
            "generator_type": "realistic"
        },
        stream=True
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to start stream. Status: {response.status_code}")
        return
    
    log_count = 0
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8') if isinstance(line, bytes) else line
            if line.startswith('data: '):
                line = line[6:]  # Remove 'data: ' prefix
            try:
                data = json.loads(line)
                
                if data.get('type') == 'log':
                    if 'log_count' in data and 'log' in data:
                        print(f"Log #{data['log_count']}: {data['log']['level']} - {data['log']['service_name']}")
                        log_count += 1
                elif data.get('type') == 'complete':
                    print(f"Stream complete: {data.get('total_logs', 'unknown')} logs")
                    break
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")
                print(f"Line content: {line}")
                continue
    
    print(f"✓ Streamed {log_count} logs successfully")
    
    # Wait a bit before next test
    await asyncio.sleep(1)
    
    # Test 2: Stream logs with analysis
    print("\n[Test 2] Streaming logs with real-time analysis...")
    print("-" * 80)
    
    response = requests.post(
        f"{base_url}/api/v1/incident/stream-analyze",
        params={
            "generator_type": "spiked",
            "duration": 10,
            "logs_per_second": 1,
            "error_rate": 0.1
        },
        stream=True
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to start stream. Status: {response.status_code}")
        return
    
    log_count = 0
    incident_ids = []
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8') if isinstance(line, bytes) else line
            if line.startswith('data: '):
                line = line[6:]  # Remove 'data: ' prefix
            try:
                data = json.loads(line)
                
                if data['type'] == 'log':
                    log_count += 1
                    incident_id = data['incident_id']
                    incident_ids.append(incident_id)
                    log_data = data['log']
                    print(f"\n📄 Log #{log_count} - {log_data['level']}: {log_data['service_name']}")
                    print(f"   Category: {log_data['category']}")
                    print(f"   Request ID: {log_data['request_id']}")
                    
                elif data['type'] == 'analysis_update':
                    print(f"   → Analyzed! Status: {data['status']}, Severity: {data['severity']}")
                    
                elif data['type'] == 'complete':
                    print(f"\n✓ Stream complete! Total logs: {data['total_logs']}")
                    print(f"   Processed {log_count} incidents")
                    break
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")
                print(f"Line content: {line}")
                continue
    
    print(f"\n✓ Successfully streamed and analyzed {log_count} logs")
    
    # Test 3: Verify incidents in database
    print("\n[Test 3] Verifying incidents in database...")
    print("-" * 80)
    
    if incident_ids:
        latest_id = incident_ids[-1]
        print(f"Fetching latest incident (ID: {latest_id})...")
        
        response = requests.get(f"{base_url}/api/v1/incidents/{latest_id}")
        
        if response.status_code == 200:
            incident = response.json()
            print(f"✓ Incident found:")
            print(f"   ID: {incident['id']}")
            print(f"   Title: {incident['title']}")
            print(f"   Status: {incident['status']}")
            print(f"   Severity: {incident['severity']}")
            print(f"   Created: {incident['created_at']}")
            if incident['description']:
                desc_lines = incident['description'].split('\n')[:3]
                print(f"   Description: {' '.join(desc_lines)}...")
        else:
            print(f"❌ Failed to fetch incident. Status: {response.status_code}")
    
    # Test 4: List all incidents
    print("\n[Test 4] Listing all incidents...")
    print("-" * 80)
    
    response = requests.get(f"{base_url}/api/v1/incidents/?limit=10")
    
    if response.status_code == 200:
        incidents = response.json()
        print(f"✓ Found {len(incidents)} incidents:")
        for inc in incidents:
            print(f"   - ID {inc['id']}: {inc['title']} ({inc['status']})")
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


async def test_direct_generator():
    """Test the generator directly without HTTP"""

    
    print("\n" + "=" * 80)
    print("Testing Fake Log Generator Directly")
    print("=" * 80)
    
    print("\nGenerating 5 fake logs...")
    for i, log in enumerate(fake_log_generator(interval=0.5, num_logs=5), 1):
        print(f"Log {i}: [{log['level']}] {log['service_name']} - {log['message']}")
        print(f"  Category: {log['category']}")
        print(f"  Request ID: {log['request_id']}")


if __name__ == "__main__":
    print("\nStarting fake log streaming tests...")
    print("Make sure the FastAPI server is running on http://localhost:8000")
    print("Press Ctrl+C to stop...")
    
    try:
        # Run the direct generator test first
        asyncio.run(test_direct_generator())
        
        # Run the streaming tests
        asyncio.run(test_fake_log_stream())
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()