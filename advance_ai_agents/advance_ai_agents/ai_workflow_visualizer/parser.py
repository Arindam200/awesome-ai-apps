import json
import random
from datetime import datetime

def generate_random_workflow():
    """Generate random agent workflow events."""
    agent_pool = [
        "input_handler", "intent_classifier", "memory_manager", 
        "response_generator", "output_handler", "data_processor",
        "sentiment_analyzer", "context_builder", "task_planner",
        "execution_engine", "quality_checker", "feedback_loop"
    ]
    
    num_agents = random.randint(4, 8)
    selected_agents = random.sample(agent_pool, num_agents)
    
    events = []
    for i in range(len(selected_agents) - 1):
        events.append({
            "agent": selected_agents[i],
            "next_agent": selected_agents[i + 1],
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    
    return {"events": events}

def parse_logs(log_path=None):
    """Parse logs and extract workflow nodes and edges - generates random data."""
    logs = generate_random_workflow()
    nodes, edges = [], []
    for event in logs.get("events", []):
        agent = event.get("agent", "unknown")
        next_agent = event.get("next_agent", None)
        nodes.append(agent)
        if next_agent:
            edges.append((agent, next_agent))
    return list(set(nodes)), edges, json.dumps(logs, indent=2)