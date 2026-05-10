# Lesson 3: Getting Structured Output

In this lesson, you'll learn one of the most powerful features of the Strands SDK: extracting structured data (like JSON) from unstructured text. This is essential for any application that needs to reliably get specific pieces of information from an LLM.

We'll use a **Pydantic model** to define the exact data schema we want, and the agent's `structured_output` method will do the heavy lifting of forcing the LLM's output into that schema.

---

### Key Concepts Explained

1.  **Pydantic Schema (`PersonInfo`)**: We define a `PersonInfo` class using Pydantic. This class acts as a blueprint for the data we want. By defining fields like `name: str` and `age: int`, we are telling the agent the exact keys and data types it must return. Adding a `description` to each field further helps the LLM understand what to extract.

2.  **`structured_output` Method**: This is the star of the show. Instead of just calling the agent with text, we use `agent.structured_output()`.
    -   The first argument is our Pydantic class (`PersonInfo`).
    -   The second argument is the unstructured text we want to process.

3.  **Validated Output**: The method returns a `PersonInfo` object, not just a string. The data is already parsed, validated, and ready to use in your application. If the LLM fails to return data that matches the schema, Strands will automatically handle the error, often by retrying or raising an exception. This makes your application much more robust.

This feature is incredibly powerful for building reliable AI workflows, as it turns the unpredictable nature of LLM text generation into a predictable and structured data source.

---

### Further Learning

-   **Watch the Video:** [AWS Strands Course Playlist](https://www.youtube.com/playlist?list=PLMZM1DAlf0Lrc43ZtUXAwYu9DhnqxzRKZ)
-   **Read the Docs:** [Official Strands Documentation](https://strandsagents.com/latest/documentation/docs/)

---

### Navigation

| Previous Lesson | Next Lesson |
| :-------------- | :---------- |
| [Lesson 2: Session Management](/course/aws_strands/02_session_management) | [Lesson 4: MCP Agent](/course/aws_strands/04_mcp_agent) |