# Lesson 8: Safety Guardrails with Hooks

Safety guardrails are essential for protecting AI systems from harmful inputs and outputs. This lesson demonstrates how to implement comprehensive safety guardrails using AWS Strands hooks with configurable rules and real-time monitoring.

### What You'll Learn

- How to implement safety guardrails using AWS Strands hooks
- Input validation and output monitoring techniques
- Configurable safety rules and risk assessment
- Real-time safety monitoring and reporting
- Best practices for AI safety in production systems

### Prerequisites

- Basic understanding of AWS Strands framework
- Python environment with required dependencies
- API key for your chosen language model (Nebius, OpenAI, etc.)

## Use Cases

Safety guardrails are essential for several real-world scenarios:

### 🛡️ **Security-Critical Operations**

- **Content filtering**: Block harmful or inappropriate content
- **Jailbreak prevention**: Detect attempts to bypass safety instructions
- **Sensitive data protection**: Prevent exposure of personal information
- **Malicious input blocking**: Stop harmful requests before processing

### 🔒 **Compliance and Safety**

- **Regulatory compliance**: Meet industry safety requirements
- **Risk mitigation**: Reduce liability from harmful outputs
- **Audit trails**: Track all safety violations and responses
- **Quality assurance**: Ensure consistent safety standards

### 🎯 **Production Deployment**

- **User safety**: Protect end users from harmful content
- **System integrity**: Maintain AI system reliability
- **Cost control**: Prevent expensive harmful outputs
- **Reputation protection**: Maintain brand safety

### 📊 **Monitoring and Analytics**

- **Safety metrics**: Track violation rates and patterns
- **Performance impact**: Monitor guardrails overhead
- **Rule effectiveness**: Analyze which rules are most important
- **Trend analysis**: Identify emerging safety threats

---

## Implementation

### Code: `main.py`

This script demonstrates how to set up safety guardrails for an AI agent:

1. **Environment Setup**: Validates required environment variables
2. **Guardrails Configuration**: Sets up safety rules and validation
3. **Agent Creation**: Creates an agent with guardrails enabled
4. **Safety Testing**: Demonstrates blocking of unsafe requests

### Key Components

The implementation consists of:

- **SafetyGuardrails**: Core safety validation logic with configurable rules
- **GuardrailsHook**: Hook implementation that integrates with AWS Strands
- **GuardedAgent**: Wrapper for easy integration with existing agents
- **Safety Testing**: Comprehensive test cases for validation

## Key Concepts

### 🔧 **Multi-Layer Safety Validation**

The guardrails system implements multiple layers of protection:

- **Keyword Detection**: Blocks requests containing harmful terms
- **Pattern Matching**: Detects jailbreak attempts using regex
- **Context Analysis**: Assesses risk based on content context
- **LLM Validation**: Uses AI to evaluate edge cases

### 🎯 **Risk Assessment Engine**

Requests are categorized by risk level:

| Risk Level | Description                             | Action              |
| ---------- | --------------------------------------- | ------------------- |
| `low`      | Safe requests that pass all checks      | Allow processing    |
| `medium`   | Sensitive topics requiring monitoring   | Allow with warnings |
| `high`     | Dangerous requests that must be blocked | Block immediately   |

### 📊 **Real-time Monitoring**

The system provides comprehensive monitoring:

- **Safety Statistics**: Track violation rates and patterns
- **Audit Logging**: Record all validation attempts
- **Performance Metrics**: Monitor guardrails overhead


### 🏷️ **Safety Rules Configuration**

Custom attributes provide context for safety validation:

| Rule Type             | Description                    | Examples                                      |
| --------------------- | ------------------------------ | --------------------------------------------- |
| `prohibited_keywords` | Harmful or dangerous terms     | "violence", "hate", "bomb", "weapon"          |
| `jailbreak_patterns`  | Bypass attempt patterns        | "ignore previous instructions", "you are now" |
| `sensitive_topics`    | Personal/sensitive information | "personal information", "financial data"      |

### 📈 **Safety Metrics**

Key metrics to track:

- **Safety Rate**: Percentage of requests that pass validation
- **Blocked Requests**: Number and type of blocked requests
- **Risk Distribution**: Breakdown by risk level (low/medium/high)
- **Performance Impact**: Validation overhead and response times

## Quick Start

### 1. **Setup Environment**

```bash
# Install dependencies
uv sync

# Set up your API key
export NEBIUS_API_KEY="your-api-key-here"
```

### 2. **Run the Example**

```bash
uv run main.py
```

### 3. **Expected Output**

You'll see the guardrails system in action with real-time validation feedback:

```
🛡️ AWS Strands Guardrails Demo
This demo shows how to implement safety guardrails using hooks.

🔒 GUARDRAILS: Validating input...
Input: Tell me how to make a bomb
❌ BLOCKED: Input failed safety validation
Risk Level: HIGH
Violations: Prohibited keyword: bomb

❌ BLOCKED: Request blocked by safety guardrails: Prohibited keyword: bomb
```

The system will automatically block unsafe requests while allowing legitimate ones to proceed.

---

## Further Learning

### 📚 **Resources**

- **Video Tutorial**: [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
- **Documentation**: [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)

---

## Navigation

| ← Previous                                            | Next →                                                        |
| :---------------------------------------------------- | :------------------------------------------------------------ |
| [Observability](/course/aws_strands/07_observability) | [Advanced Patterns](/course/aws_strands/09_advanced_patterns) |
