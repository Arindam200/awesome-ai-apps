# Lesson 1: Your First AI Agent

Welcome to the first lesson of the AWS Strands course! Here, you'll learn the fundamentals of creating a simple but powerful AI agent.

We'll build a **weather assistant** that can understand a question, fetch live data from an external API, and provide a helpful answer. This will introduce you to the core concepts of the Strands SDK:

-   **Agent Creation**: How to instantiate an agent.
-   **Model Configuration**: How to connect your agent to a large language model (LLM).
-   **Tool Usage**: How to give your agent abilities, like accessing the internet.

---

### Key Concepts Explained

1.  **System Prompt**: The `WEATHER_SYSTEM_PROMPT` is the agent's constitution. It's a detailed set of instructions that defines the agent's personality, its capabilities, and the exact steps it should follow. A well-crafted system prompt is crucial for reliable agent behavior.

2.  **Model Configuration**: `LiteLLMModel` is a bridge to the language model that acts as the agent's "brain". Strands uses `litellm` under the hood, which means you can easily switch between dozens of LLM providers (like OpenAI, Anthropic, Google, etc.) just by changing the `model_id`.

3.  **Tool Usage**: Tools are the agent's hands and eyes. By giving the agent the `http_request` tool, we grant it the ability to access the internet. The agent's LLM brain knows how to use this tool to follow the instructions in the system prompt.

4.  **Agent Instantiation**: The `Agent` class brings everything together. We provide it with the system prompt, the model, and the tools it's allowed to use.

5.  **Invocation**: Calling the agent is as simple as calling a function: `weather_agent(user_query)`. The agent takes the query, thinks step-by-step (using the LLM), uses its tools as needed, and returns a final, synthesized answer.

---

### Further Learning

-   **Watch the Video:** [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
-   **Read the Docs:** [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)

---

### Navigation

| Previous Lesson | Next Lesson |
| :-------------- | :---------- |
| N/A             | [Lesson 2: Session Management](/course/aws_strands/02_session_management) |