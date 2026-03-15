# 🎯 Demo Cheat Sheet

## Pre-Demo Checklist
- [ ] Docker Desktop running
- [ ] Demo containers started: `docker compose -f docker-compose.demo.yml up -d`
- [ ] `NEBIUS_API_KEY` configured
- [ ] Temporal server ready (for Temporal demo)
- [ ] Browser open to `http://localhost:8233`

---

## 🎬 Demo Flow (5 minutes)

### 1. Introduction (30 sec)
"DevOps engineers spend hours managing containers. What if you could do it with natural language?"

### 2. Simple Agent (1.5 min)
```bash
python docker_agent.py
```

**Query 1:** `Check container status`
- Point out: 3 containers, names, status, uptime

**Query 2:** `Is demo-nginx healthy?`
- Point out: Health check, CPU, memory metrics

**Query 3:** `Show me logs for demo-logger`
- Point out: Real-time logs, different log levels

### 3. Temporal Upgrade (2 min)
```bash
# Already running: temporal server, worker, client
```

**Query 1:** `Check demo-nginx health and show logs`
- Switch to Temporal UI immediately
- Show: AI orchestrator breaking down the query
- Show: Each activity executing
- Point out: Different retry policies

**Query 2:** Demonstrate fault tolerance
- Start: `Show me logs for demo-logger`
- Kill worker (Ctrl+C)
- Restart worker
- Show: Operation continues!

### 4. Temporal UI Tour (1 min)
- Show workflow list
- Click into a workflow
- Show execution timeline
- Point out: Complete audit trail

### 5. Wrap Up (30 sec)
"Same code, two modes. Simple for dev, Temporal for production."

---

## 💬 Sample Queries

### Basic
```
Check container status
Show me all running containers
```

### Health Checks
```
Is demo-nginx healthy?
Check health of all running containers
Is demo-redis consuming too much memory?
```

### Logs
```
Show me logs for demo-logger
Show me the last 50 lines from demo-redis
Show me logs for demo-nginx
```

### Operations
```
Restart demo-nginx
```

### Complex (Temporal)
```
Check demo-nginx health and show logs
Check demo-redis health and show me its logs
```

---

## 🎯 Key Talking Points

### Simple Agent
- ✅ "Natural language - no Docker commands needed"
- ✅ "Instant feedback for development"
- ✅ "User-friendly error messages"

### Temporal Agent
- ✅ "Automatic retries - handles transient failures"
- ✅ "Complete audit trail - every operation tracked"
- ✅ "Fault tolerance - survives worker crashes"
- ✅ "AI orchestration - breaks down complex queries"

### Technical
- ✅ "Real Docker SDK integration"
- ✅ "Health checks with CPU/memory metrics"
- ✅ "Configurable retry policies per operation"
- ✅ "Production-ready error handling"

---

## 🔥 "Wow" Moments

### 1. AI Orchestration
Show in Temporal UI how:
```
"Check nginx health and show logs"
```
Becomes:
```
health:demo-nginx → logs:demo-nginx
```

### 2. Fault Tolerance
Kill worker mid-operation, restart, continues!

### 3. Retry Policies
Show in code:
- Status: 3 attempts, 1s→5s
- Restart: 5 attempts, 5s→30s

### 4. Execution History
Browse past operations, click into details, see everything!

---

## 🐛 Quick Fixes

**Containers not running?**
```bash
./demo-setup.sh status
./demo-setup.sh restart
```

**No logs yet?**
```bash
sleep 10  # Wait for logs to generate
./demo-setup.sh logs
```

**Temporal UI not loading?**
```bash
curl http://localhost:8233
# Restart: temporal server start-dev
```

**Worker won't start?**
```bash
# Check Temporal server is running first
# Check Docker is accessible
```

---

## 📊 Expected Output Examples

### Container Status
```
Found 3 container(s):

Container: demo-nginx (a1b2c3d4e5f6)
  Status: running
  Image: nginx:alpine
  Uptime: 2 hours
  Ports: 80/tcp->0.0.0.0:8080
```

### Health Check
```
✓ demo-nginx: Healthy
  Status: running
  Health Check: healthy
  CPU: 0.5%
  Memory: 2.1%
  Restarts: 0
```

### Logs
```
Last 100 lines from container 'demo-logger':
============================================================
[INFO] Processing request #32505 at Fri Jan 16 11:30:50 UTC 2026
[DEBUG] Cache hit ratio: 87%
[WARN] High memory usage detected: 76%
[ERROR] Connection timeout to database
```

---

## 🎤 The Closing Line

"This is how you build reliable DevOps automation. Start with a simple agent for development, then add Temporal for production. Same tools, same code, enterprise features when you need them."

---

## 📞 Backup Plan

If live demo fails:
1. Show validation script: `python validate_docker_monitor.py`
2. Walk through code structure
3. Show Temporal UI with pre-recorded workflows
4. Explain architecture with diagrams

---

## ⏱️ Time Allocations

- Introduction: 30 sec
- Simple Agent: 1.5 min
- Temporal Agent: 2 min
- Temporal UI: 1 min
- Wrap up: 30 sec
- **Total: 5.5 minutes**

Add 2-3 minutes for Q&A!
