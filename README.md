# Akka2Rebeca Translation - LangGraph Project

## Description
A professional LangGraph-based workflow for intelligent translation and processing.

## Setup

### 1. Clone and Navigate
\`\`\`bash
cd akka2rebecatranslation
\`\`\`

### 2. Activate Virtual Environment
\`\`\`bash
# On Linux/Mac
source .venv/bin/activate

# On Windows
.venv\\Scripts\\activate
\`\`\`

### 3. Install Dependencies
\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 4. Configure Environment
Create `.env` file and add your API keys:
\`\`\`
OPENAI_API_KEY=your-key-here
\`\`\`

## Running the Application
\`\`\`bash
python main.py
\`\`\`
## Adding New Nodes
1. Create function in `src/agents/`
2. Add to workflow in `src/graphs/main_workflow.py`
3. Update state if needed in `src/state/workflow_state.py`
