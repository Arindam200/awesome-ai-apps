# 🧠 AI Workflow Visualizer

**AI Workflow Visualizer** is a powerful tool that automatically **summarizes, parses, and visualizes intelligent agent workflows**.
It leverages the **Nebius API** to generate structured, human-understandable visual representations of complex AI agent logs.

---

## 🚀 Features

* **Workflow Summarization** – Automatically extracts key steps and decisions from raw agent logs.
* **Graph Visualization** – Builds clear, interactive graph-based representations of workflows.
* **Nebius API Integration** – Uses Nebius LLMs for accurate summarization and entity extraction.
* **Dynamic Parsing** – Flexible parsing logic that adapts to diverse agent log formats.
* **Sample Logs Included** – Comes with a ready-to-test sample log (`sample_logs/agent_log.json`).

---

## 🧩 Project Structure

```
ai_workflow_visualizer/
│
├── app.py                  # Main entry point for running the visualizer
├── graph_builder.py        # Builds graph structure for workflow visualization
├── nebius_client.py        # Handles interaction with Nebius API
├── parser.py               # Parses and cleans agent logs
├── requirements.txt        # Python dependencies
└── sample_logs/
    └── agent_log.json      # Example agent workflow data
```

---

## ⚙️ Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/Sanjana-m55/awesome-ai-apps.git
cd awesome-ai-apps/advance_ai_agents/advance_ai_agents/ai_workflow_visualizer
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # On macOS/Linux
venv\Scripts\activate           # On Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your Nebius API key

Create a `.env` file and add:

```
NEBIUS_API_KEY=your_api_key_here
```

---

## 🧠 Usage

### Run the Visualizer

```bash
streamlit run app.py
```

### Example Input

The visualizer uses logs like this:

```json
{
  "agent": "ChatAgent",
  "steps": [
    {"action": "Search", "description": "Searching for user query..."},
    {"action": "Analyze", "description": "Analyzing retrieved data..."},
    {"action": "Respond", "description": "Generating final response..."}
  ]
}
```

### Output

✅ Clean summary of workflow steps
✅ Visual graph showing relationships and sequence of actions
✅ Interactive insights into decision paths

---

## 🧠 Technologies Used

* **Python 3.9+**
* **Nebius API (LLM)**
* **Graphviz / NetworkX** (for visualization)
* **dotenv**
* **JSON Parsing Libraries**

---

## 🤝 Contributing

Contributions are welcome!
Please fork the repo, create a branch, and submit a pull request:

```bash
git checkout -b feature/your-feature-name
git commit -m "feat: describe your feature"
git push origin feature/your-feature-name
```

---

## 🧩 Example Commit

```
feat: implemented intelligent workflow summarization and visualization using Nebius API
```

---

## 🪪 License

This project is licensed under the **MIT License**.
See the [LICENSE](LICENSE) file for details.

---

## 💡 Acknowledgments

* [Nebius AI](https://nebius.com/) for providing advanced AI summarization APIs
* [NetworkX](https://networkx.org/) for visualization support
* All open-source contributors!

---

✨ *Developed with ❤️ by [Sanjana M](https://github.com/Sanjana-m55)*
