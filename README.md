![Banner](/assets/banner_new.png)

<div align="center">

# Awesome AI Apps [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

<a href="https://trendshift.io/repositories/14662" target="_blank"><img src="https://trendshift.io/api/badge/repositories/14662" alt="Arindam200%2Fawesome-ai-apps | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

</div>

This repository is a comprehensive collection of **70+ practical examples, tutorials, and recipes** for building powerful LLM-powered applications. From simple chatbots to advanced AI agents, these projects serve as a guide for developers working with various AI frameworks and tools.

## 📋 Table of Contents

- [🎓 Courses](#-courses)
- [🚀 Featured AI Apps](#-featured-ai-apps)
  - [🧩 Starter Agents](#-starter-agents)
  - [🪶 Simple Agents](#-simple-agents)
  - [🗂️ MCP Agents](#️-mcp-agents)
  - [🧠 Memory Agents](#-memory-agents)
  - [📚 RAG Applications](#-rag-applications)
  - [🔬 Advanced Agents](#-advanced-agents)
- [📺 Tutorials & Videos](#-tutorials--videos)
- [🚀 Getting Started](#getting-started)
- [🤝 Contributing](#-contributing)

---

<div align="center">

## 💎 Sponsors

<p align="center">
  A huge thank you to our sponsors for their generous support!
</p>

<table align="center" cellpadding="10" style="width:100%; border-collapse:collapse;">
  <tr align="center">
    <td width="300" valign="middle" align="center">
      <a href="https://dub.sh/brightdata" target="_blank" title="Visit Bright Data">
        <img src="https://mintlify.s3.us-west-1.amazonaws.com/brightdata/logo/light.svg" height="35" style="max-width:180px;" alt="Bright Data - Web Data Platform">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">Web Data Platform</span>
        <br>
        <a href="https://dub.sh/brightdata" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit Bright Data website">
        </a>
      </sub>
    </td>
    <td width="300" valign="middle" align="center">
      <a href="https://dub.sh/nebius" target="_blank" title="Visit Nebius Token Factory">
        <img src="./assets/nebius.png" height="36" style="max-width:180px;" alt="Nebius Token Factory">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">AI Inference Provider</span>
        <br>
        <a href="https://dub.sh/nebius" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit Nebius Token Factory">
        </a>
      </sub>
    </td>
    <td width="300" valign="middle" align="center">
      <a href="https://dub.sh/scrapegraphai" target="_blank" title="Visit ScrapeGraphAI on GitHub">
        <img src="https://raw.githubusercontent.com/ScrapeGraphAI/ScrapeGraph-AI/main/docs/assets/scrapegraphai_logo.png" height="44" style="max-width:180px;" alt="ScrapeGraphAI - Web Scraping Library">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">AI Web Scraping framework</span>
        <br>
        <a href="https://dub.sh/scrapegraphai" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="View ScrapeGraphAI on GitHub">
        </a>
      </sub>
    </td>
  </tr>
  <tr align="center">
    <td width="300" valign="middle" align="center">
      <a href="https://dub.sh/memorilabs" target="_blank" title="Visit Memorilabs">
        <img src="assets/memori.png" height="36" style="max-width:180px;" alt="Memori - SQL Native Memory for AI">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">SQL Native Memory for AI</span>
        <br>
        <a href="https://dub.sh/memorilabs" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit Memorilabs website">
        </a>
      </sub>
    </td>
    <td width="300" valign="middle" align="center">
      <a href="https://dub.sh/copilotkit" target="_blank" title="Visit CopilotKit">
        <img src="assets/copilot-kit-logo.svg" height="36" style="max-width:180px;" alt="CopilotKit - Agentic Application Platform">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">Agentic Application Platform</span>
        <br>
        <a href="https://dub.sh/copilotkit" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit CopilotKit website">
        </a>
      </sub>
    </td>
    <td width="300" valign="middle" align="center">
      <a href="https://dub.sh/scalekitt" target="_blank" title="Visit ScaleKit">
        <img src="assets/scalekit.svg" height="36" style="max-width:180px;" alt="ScaleKit - Auth Stack for AI">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">Auth Stack for AI</span>
        <br>
        <a href="https://dub.sh/scalekitt" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit ScaleKit website">
        </a>
      </sub>
    </td>
  </tr>
  <tr align="center">
    <td width="200" valign="middle" align="center">
      <a href="https://okahu.ai" target="_blank" title="Visit Okahu">
        <img src="assets/okahu.png" height="36" style="max-width:180px;" alt="Okahu - AI Platform">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">AI Observability Platform</span>
        <br>
        <a href="https://okahu.ai" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit Okahu website">
        </a>
      </sub>
    </td>
    <td width="200" valign="middle" align="center">
      <a href="https://dub.sh/serpApi" target="_blank" title="Visit SerpApi">
        <img src="assets/serpapi.png" height="36" style="max-width:180px;" alt="SerpApi - Google Search API">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">Google Search API</span>
        <br>
        <a href="https://dub.sh/serpApi" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit SerpApi website">
        </a>
      </sub>
    </td>
    <td width="200" valign="middle" align="center">
      <a href="https://dub.sh/agentfield" target="_blank" title="Visit AgentField">
        <img src="assets/agentfield.png" height="40" style="max-width:180px;" alt="AgentField - Kubernetes for AI Agents">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">Kubernetes for AI Agents</span>
        <br>
        <a href="https://dub.sh/agentfield" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit AgentField website">
        </a>
      </sub>
    </td>
  </tr>
  <tr align="center">
    <td width="200" valign="middle" align="center">
      <a href="https://anchorbrowser.io" target="_blank" title="Visit Anchor Browser">
        <img src="assets/anchorbrowser.png" height="36" style="max-width:180px;" alt="Anchor Browser - Agentic Browser Infrastructure">
      </a>
      <br>
      <sub>
        <span style="white-space:nowrap;">Agentic Browser Infrastructure</span>
        <br>
        <a href="https://anchorbrowser.io" target="_blank">
          <img src="https://img.shields.io/badge/Visit%20Site-blue?style=flat-square" alt="Visit Anchor Browser website">
        </a>
      </sub>
    </td>
  </tr>
</table>

### 💎 Become a Sponsor

<p align="center">
Interested in sponsoring this project? Feel free to reach out!
<br/>
<a href="https://dub.sh/arindam-linkedin" target="_blan