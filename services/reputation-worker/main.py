import json
import os
import time
import requests
import redis
import base64
from confluent_kafka import Consumer, Producer

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_INPUT_TOPIC = os.getenv('KAFKA_INPUT_TOPIC', 'emails_topic')
KAFKA_OUTPUT_TOPIC = os.getenv('KAFKA_OUTPUT_TOPIC', 'analysis_results_topic')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
VT_API_KEY = os.getenv('VT_API_KEY', 'your_vt_key')

# 4 requests per minute limit = 1 request every 15 seconds
RATE_LIMIT_DELAY = 15.0 

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

def get_kafka_consumer():
    conf = {
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': 'reputation-worker-group',
        'auto.offset.reset': 'earliest'
    }
    return Consumer(conf)

def get_kafka_producer():
    conf = {'bootstrap.servers': KAFKA_BROKER}
    return Producer(conf)

def check_vt(indicator, indicator_type):
    """
    indicator_type: 'urls' or 'files' (for hashes)
    """
    cache_key = f"vt:{indicator}"
    try:
        cached_result = redis_client.get(cache_key)
        if cached_result:
            print(f"Cache hit for {indicator}")
            return json.loads(cached_result)
    except Exception as e:
        print(f"Redis cache error: {e}")
        
    print(f"Checking VT for {indicator}...")
    headers = {
        "accept": "application/json",
        "x-apikey": VT_API_KEY
    }
    
    url = ""
    if indicator_type == "urls":
        url_id = base64.urlsafe_b64encode(indicator.encode()).decode().strip("=")
        url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
    elif indicator_type == "files":
        url = f"https://www.virustotal.com/api/v3/files/{indicator}"
        
    if not url:
        return None
        
    response = requests.get(url, headers=headers)
    
    # Respect rate limiting (4 req/min)
    time.sleep(RATE_LIMIT_DELAY)
    
    if response.status_code == 200:
        result = response.json()
        try:
            redis_client.set(cache_key, json.dumps(result), ex=86400) # Cache for 24 hours
        except Exception as e:
            print(f"Redis cache set error: {e}")
        return result
    else:
        print(f"VT API Error {response.status_code}: {response.text}")
        return {"error": response.status_code, "message": response.text}

def main():
    consumer = get_kafka_consumer()
    producer = get_kafka_producer()
    consumer.subscribe([KAFKA_INPUT_TOPIC])

    print("Reputation Worker started. Listening for messages...")
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue
            
            try:
                email_data = json.loads(msg.value().decode('utf-8'))
                email_id = email_data.get('id', 'unknown')
                urls = email_data.get('urls', [])
                hashes = email_data.get('hashes', [])
                
                print(f"Processing email {email_id}, {len(urls)} URLs, {len(hashes)} hashes...")
                
                reputation_results = {"urls": {}, "hashes": {}}
                
                for u in urls:
                    reputation_results["urls"][u] = check_vt(u, "urls")
                    
                for h in hashes:
                    reputation_results["hashes"][h] = check_vt(h, "files")
                
                result_event = {
                    'email_id': email_id,
                    'worker': 'reputation-worker',
                    'reputation': reputation_results,
                    'timestamp': time.time()
                }
                
                producer.produce(KAFKA_OUTPUT_TOPIC, key=str(email_id).encode('utf-8'), value=json.dumps(result_event).encode('utf-8'))
                producer.flush()
                print(f"Result for email {email_id} published.")
                
            except Exception as e:
                print(f"Error processing message: {e}")
                
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == '__main__':
    main()
