Stop wiring APIs directly into your LLM.

Use MCP to route the right tool at the right time.

Here's how...

We built a PR Reviewer Assistant to automate pull request reviews without hardcoding every integration.

Instead of connecting Gemini directly to GitHub, Slack, or Asana APIs, we designed the system around MCP’s host–client–server model:

𝟭/ 𝗛𝗼𝘀𝘁 - 𝘁𝗵𝗲 𝗯𝗿𝗮𝗶𝗻

A FastAPI app powered by 𝗚𝗲𝗺𝗶𝗻𝗶, triggered whenever a pull request opens on GitHub.

Gemini handles reasoning and planning, keeping context across multiple tool calls

This is ideal for multi-step workflows (like PR reviews).

𝟮/ 𝗖𝗹𝗶𝗲𝗻𝘁 - 𝘁𝗵𝗲 𝗰𝗼𝗻𝘁𝗿𝗮𝗰𝘁𝗼𝗿

A single MCP Client is linked to a Global MCP Registry that aggregates all available MCP servers.

This component is what makes the system scalable.

Instead of hardcoding connections, the host can simply query the Global Registry by tag:

“Get me every tool tagged with 𝚙𝚞𝚕𝚕_𝚛𝚎𝚚𝚞𝚎𝚜𝚝 and 𝚌𝚘𝚍𝚎.”

The Global Registry routes the right tools, which keep everything flexible and decoupled.

𝟯/ 𝗦𝗲𝗿𝘃𝗲𝗿𝘀 - 𝘁𝗵𝗲 𝗵𝗮𝗻𝗱𝘀

Each MCP Server does one job:

• GitHub MCP → Fetches PR metadata and diffs
• Asana MCP → Pulls linked task requirements
• Agent Scope Custom MCP → Provides the PR review prompt
• Slack MCP → Posts the review straight to your team’s channel
  
The Agent Scope MCP is the single source of truth for agent behavior.

𝗛𝗲𝗿𝗲'𝘀 𝗵𝗼𝘄 𝗶𝘁 𝗮𝗹𝗹 𝗳𝗹𝗼𝘄𝘀:

1. A developer opens a PR → GitHub triggers the Host
2. Host fetches the review prompt from the Agent Scope MCP
3. Gemini plans which tools to use
4. Global MCP routes tool calls to the right servers
5. Each server executes its task and returns the results
6. Gemini generates the review
7. Slack MCP posts the final feedback in your channel
   
If you want to build with MCP like a real engineer, your AI systems should have:

• Centralized tool management
• Support for both custom and pre-built MCP servers
• Zero hardcoded connections
  
Anca Ioana Muscalagiu and I broke down the full design (with architecture diagrams and code) in our open-source course, Designing Enterprise MCP Systems, in Decoding AI Magazine.

Read it here → https://lnkd.in/daKrq_9T
