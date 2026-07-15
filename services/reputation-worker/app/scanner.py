import httpx
import logging
import base64
import asyncio
import json

logger = logging.getLogger(__name__)

class ReputationScanner:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"x-apikey": self.api_key} if self.api_key else {}
        self.base_url = "https://www.virustotal.com/api/v3"
        # VT Free tier is 4 req/min. We use a semaphore and sleep to respect this globally
        self.semaphore = asyncio.Semaphore(1) 

    async def scan_urls(self, urls: list, redis_client) -> dict:
        results = {}
        for url in set(urls):
            # Check cache
            cached = await redis_client.get(f"url_rep:{url}")
            if cached:
                results[url] = json.loads(cached)
                continue
                
            if not self.api_key:
                # Mock response
                res = {"risk_score": 0, "risk_level": "LOW_RISK"}
                results[url] = res
                continue

            # Real API Call
            url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
            async with self.semaphore:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(f"{self.base_url}/urls/{url_id}", headers=self.headers, timeout=5.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            stats = data['data']['attributes']['last_analysis_stats']
                            malicious = stats.get('malicious', 0)
                            suspicious = stats.get('suspicious', 0)
                            
                            risk_score = min(100, (malicious * 20) + (suspicious * 10))
                            risk_level = "HIGH_RISK" if malicious >= 5 else "MEDIUM_RISK" if malicious > 0 or suspicious >= 3 else "LOW_RISK"
                            
                            res = {"risk_score": risk_score, "risk_level": risk_level, "vt_stats": stats}
                        else:
                            res = {"risk_score": 0, "risk_level": "UNKNOWN_RISK", "error": resp.status_code}
                except Exception as e:
                    logger.error(f"VT API Error for URL {url}: {e}")
                    res = {"risk_score": 0, "risk_level": "UNKNOWN_RISK"}
                
                # Sleep 15 seconds to enforce 4 req/min max rate limit across tasks
                await asyncio.sleep(15)

            # Cache result: 24h for valid results, 60s for errors/unknown
            ttl = 60 if res.get("risk_level") == "UNKNOWN_RISK" else 86400
            await redis_client.setex(f"url_rep:{url}", ttl, json.dumps(res))
            results[url] = res
            
        return results

    async def scan_hashes(self, hashes: list, redis_client) -> dict:
        results = {}
        for h in set(hashes):
            cached = await redis_client.get(f"hash_rep:{h}")
            if cached:
                results[h] = json.loads(cached)
                continue
                
            if not self.api_key:
                res = {"risk_score": 0, "risk_level": "LOW_RISK"}
                results[h] = res
                continue

            async with self.semaphore:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(f"{self.base_url}/files/{h}", headers=self.headers, timeout=5.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            stats = data['data']['attributes']['last_analysis_stats']
                            malicious = stats.get('malicious', 0)
                            suspicious = stats.get('suspicious', 0)
                            
                            risk_score = min(100, (malicious * 20) + (suspicious * 10))
                            risk_level = "HIGH_RISK" if malicious >= 3 else "MEDIUM_RISK" if malicious > 0 or suspicious >= 2 else "LOW_RISK"
                            
                            res = {"risk_score": risk_score, "risk_level": risk_level, "vt_stats": stats}
                        else:
                            res = {"risk_score": 0, "risk_level": "UNKNOWN_RISK", "error": resp.status_code}
                except Exception as e:
                    logger.error(f"VT API Error for Hash {h}: {e}")
                    res = {"risk_score": 0, "risk_level": "UNKNOWN_RISK"}
                
                await asyncio.sleep(15)
                
            ttl = 60 if res.get("risk_level") == "UNKNOWN_RISK" else 86400
            await redis_client.setex(f"hash_rep:{h}", ttl, json.dumps(res))
            results[h] = res
            
        return results
