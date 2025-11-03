import os
from openai import OpenAI
def get_nebius_client():
    """
    Initialize Nebius AI client using OpenAI-compatible API.
    Make sure NEBIUS_API_KEY is set in your environment.
    """
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise ValueError("⚠️ Please set NEBIUS_API_KEY in your environment.")
    
    return OpenAI(
        base_url="https://api.studio.nebius.com/v1/",
        api_key=api_key
    )

def summarize_workflow(log_text: str):
    """
    Uses Nebius LLM to provide deep, insightful analysis of agent workflow.
    Returns tuple of (summary_text, token_count)
    """
    client = get_nebius_client()
    prompt = f"""You are an expert AI systems analyst specializing in multi-agent workflows and distributed AI architectures.

Analyze the following agent workflow log data and provide a DEEP, INSIGHTFUL analysis that goes beyond surface-level observations.

Log Data:
{log_text}

Your analysis should be structured as follows:

**🧠 AI Insight Summary**

Start with a one-sentence executive summary that captures the essence of this workflow's design philosophy.

**🔹 Key Agents & Their Roles:**
List the agents involved with `code formatting`, then explain WHAT each agent does and WHY it's positioned where it is in the pipeline.

**🔹 Workflow Architecture Analysis:**
- Explain the DESIGN PATTERN (sequential, parallel, hub-and-spoke, waterfall, etc.)
- Discuss WHY this architecture was chosen - what problems does it solve?
- Identify any SMART design decisions (e.g., separation of concerns, modularity)
- Point out any POTENTIAL ISSUES with the current design

**🔹 Data Flow & Dependencies:**
- Trace how information flows between agents
- Explain WHY certain agents depend on others
- Identify any BOTTLENECKS or critical path dependencies
- Discuss whether the flow is optimal or could be improved

**🔹 Performance Characteristics:**
- Analyze the workflow's efficiency characteristics
- Discuss latency implications of the sequential/parallel design
- Suggest specific optimizations with estimated impact (e.g., "parallelizing X and Y could reduce latency by ~40%")
- Comment on scalability and throughput potential

**🔹 Memory & State Management:**
- Discuss how state/context flows through the system
- Identify if there's a RAG pattern, memory loops, or stateless processing
- Explain the implications for consistency and reproducibility

**🟢 Conclusion:**
Provide an overall assessment with specific metrics or observations. Be honest about trade-offs and suggest concrete improvements.

IMPORTANT RULES:
- Be SPECIFIC, not generic
- Use technical terminology appropriately
- Provide REASONING for your observations
- Suggest CONCRETE improvements with estimated impacts
- Make it engaging and insightful, not a boring bullet list
- Use markdown formatting with code blocks for agent names
- Keep the total response under 600 words but pack it with insights"""

    response = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,  
        max_tokens=1200, 
    )
    

    usage = response.usage
    total_tokens = usage.total_tokens if usage else 0
    summary_text = response.choices[0].message.content
    return summary_text, total_tokens