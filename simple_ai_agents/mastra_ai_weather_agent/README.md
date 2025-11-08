# Using a tool with Mastra AI and Nebius 

A simple example showing how to use a tool.

## Prerequisites

- Node.js v20.0+
- pnpm (recommended) or npm
- Nebius Token Factory Key

## Getting Started

1. Copy the environment variables file and add your OpenAI API key:

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and add your OpenAI API key:

   ```env
   NEBIUS_API_KEY=your-api-key-here
   ```

2. Install dependencies:

   ```
   pnpm install
   ```

3. Run the example:

   ```bash
   pnpm start
   ```
