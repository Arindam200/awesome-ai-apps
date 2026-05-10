# Contributing to Awesome AI Apps

First off, thank you for considering contributing to Awesome AI Apps! It's people like you that make this such a great collection of resources for the community. Your contributions are valuable and help everyone learn and build better AI applications.

This document provides guidelines for contributing to this repository. Please read it carefully to ensure a smooth and effective contribution process.

## Code of Conduct

This project and everyone participating in it is governed by a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior.

## How Can I Contribute?

There are many ways to contribute, from adding new projects to improving existing ones, reporting bugs, or suggesting enhancements.

### Reporting Bugs

If you find a bug in one of the projects, please open an issue. Make sure to include:

- A clear and descriptive title.
- A detailed description of the bug, including steps to reproduce it.
- The name of the project directory where the bug occurred.
- Any relevant error messages or logs.

### Suggesting Enhancements

If you have an idea for a new project or an improvement to an existing one, please open an issue to discuss it. This allows us to coordinate efforts and prevent duplication of work.

### Your First Code Contribution

Unsure where to begin? You can start by looking through `good first issue` and `help wanted` issues.

## Adding a New Project

We welcome new project examples! To maintain consistency and quality, please follow these guidelines when adding a new project.

### 1. Create an Issue

Before starting your work, **create an issue** that describes the project you want to add. This helps us track contributions and avoid multiple people working on the same thing.

### 2. One Project per Pull Request

To keep our review process clean and focused, **each new project must be submitted in its own Pull Request.** Do not bundle multiple new projects into a single PR. Each PR should be linked to the issue you created.

### 3. Folder Structure and Naming

- **Place your project in the appropriate category folder:**
  - `starter_ai_agents/`: For simple, boilerplate-style agents.
  - `simple_ai_agents/`: For straightforward, practical use-cases.
  - `advance_ai_agents/`: For complex, multi-step workflows.
  - `rag_apps/`: For Retrieval-Augmented Generation examples.
  - `memory_agents/`: For agents with memory capabilities.
  - `mcp_ai_agents/`: For projects using the Model Context Protocol.
- **Follow the naming convention for your project's folder:** The name should be descriptive and use snake_case. For example: `finance_agent`, `blog_writing_agent`.

### 4. Project README

- **Every project MUST have its own `README.md` file.**
- This README should provide clear, detailed instructions on how to set up and run the project.
- **Use the provided template as a reference:** Your project's README should follow the structure and include the sections outlined in `.github/README_TEMPLATE.md`. This ensures all projects in the collection are well-documented and easy for others to use.

### 5. Development Best Practices

- **Dependencies:** Include a `requirements.txt` or, preferably, define dependencies within a `pyproject.toml` file in your project's directory.
- **Code Style:** Write clean, readable code. We encourage the use of a code formatter like [Black](https://github.com/psf/black) or [Ruff](https://docs.astral.sh/ruff/formatter/) to maintain a consistent style.
- **Testing:** While not strictly required for all examples, adding tests is highly encouraged. If you do, create a `tests/` subdirectory within your project folder.
- **No Secrets:** Ensure you do not commit any API keys, passwords, or other sensitive information. Use environment variables and provide a `.env.example` file.

## Pull Request Process

1. **Fork the repository** and create your branch from `main`.
2. Make your changes, adhering to the guidelines above.
3. Ensure your code lints and any tests pass.
4. Create a Pull Request to the `main` branch of the original repository.
5. **Link your PR to the issue** you created (e.g., "Closes #123").
6. Provide a clear title and a concise description of your contribution in the PR.

Thank you again for your contribution!
