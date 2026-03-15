"""Quick script to test Qonic API endpoints."""
import httpx, json, os, glob

token_files = glob.glob(os.path.expanduser("~/.mcp-auth/mcp-remote-0.1.37/*_tokens.json"))
with open(token_files[0]) as f:
    tokens = json.load(f)
at = tokens.get("access_token", "")
base = "https://api.qonic.com"
hdr = {"Authorization": "Bearer " + at, "Accept": "application/json", "Content-Type": "application/json"}

# We started a session previously, now try products again
url = base + "/v1/projects/6234/models/11097/products"

# GET with query params
r = httpx.get(url + "?fields=Name&fields=Class", headers=hdr, timeout=15)
print(f"GET products (in session): {r.status_code}")
print(r.text[:1000])
print()

# POST with query body
r2 = httpx.post(url + "/query", headers=hdr, json={"fields": ["Name", "Class"], "filters": {}}, timeout=15)
print(f"POST products/query (in session): {r2.status_code}")
print(r2.text[:1000])
print()

# GET available-data
r3 = httpx.get(url + "/available-data", headers=hdr, timeout=15)
print(f"GET available-data (in session): {r3.status_code}")
print(r3.text[:1000])
print()

# POST available-data
r4 = httpx.post(url + "/available-data", headers=hdr, json={}, timeout=15)
print(f"POST available-data (in session): {r4.status_code}")
print(r4.text[:500])
print()

# End the session
r5 = httpx.post(base + "/v1/projects/6234/models/11097/end-session", headers=hdr, timeout=15)
print(f"POST end-session: {r5.status_code}")
print(r5.text[:200])
