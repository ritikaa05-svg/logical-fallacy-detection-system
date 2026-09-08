#!/bin/bash

# 1. Update the Dockerfile programmatically
echo "📌 Pinning FastAPI to 0.111.0..."
python3 -c '
path = "deployment/Dockerfile"
try:
    with open(path, "r") as f:
        content = f.read()
    content = content.replace("fastapi==0.115.0", "fastapi==0.111.0")
    with open(path, "w") as f:
        f.write(content)
except Exception as e:
    print(f"Error updating Dockerfile: {e}")
'

# 2. Cleanup existing container
docker stop logiscan-test >/dev/null 2>&1
docker rm logiscan-test >/dev/null 2>&1

# 3. Rebuild (FastAPI layer will update, others should stay cached)
echo "🛠️ Rebuilding with pinned version..."
docker build -t logiscan:latest -f deployment/Dockerfile . 2>&1 | tail -n 5

# 4. Run
echo "🚢 Launching..."
docker run -d --name logiscan-test -p 8000:8000 -p 8501:8501 logiscan:latest

# 5. Wait for startup
sleep 10

# 6. Verify
echo "--- RESULTS ---"
docker logs logiscan-test 2>&1 | grep -E "Error|Traceback|ready|Uvicorn.*started" | head -n 5
curl -s --connect-timeout 2 http://localhost:8000/ >/dev/null && echo "✅ BACKEND WORKS" || echo "❌ Still failing"
