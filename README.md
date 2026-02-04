# browserbase-demo

Browserbase and Stagehand demo showcasing parallel web agent execution for restaurant data extraction.

## Overview

This demo showcases how production systems can use Browserbase to orchestrate multiple parallel web agents acting as subprocessors. Each agent independently navigates restaurant websites to extract menu and business information.

## Features

- **Parallel Execution**: Dispatches multiple web agents simultaneously, similar to production systems
- **Structured Data Extraction**: Extracts restaurant info, menus, hours, contact details using Pydantic schemas
- **Fault Tolerance**: Independent agent execution with per-agent error handling and retries
- **Result Persistence**: Saves extraction results as JSON files for further processing
- **Production-Ready Pattern**: Demonstrates scalable web automation architecture

## Setup

1. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

2. Configure environment variables in `.env`:
   ```
   MODEL_API_KEY=your_api_key
   BROWSERBASE_API_KEY=your_browserbase_api_key
   BROWSERBASE_PROJECT_ID=your_project_id
   LOG_LEVEL=INFO
   ```

3. Add restaurant URLs to `websites.txt` (one per line):
   ```
   https://restaurant1.com
   https://restaurant2.com
   https://restaurant3.com
   ```

## Usage

Run the parallel web agent orchestrator:

```bash
python main.py
```

The system will:
1. Load all URLs from `websites.txt`
2. Dispatch one agent per URL in parallel
3. Extract restaurant details and menu data
4. Save results to `results/` directory

## Architecture

```
main() (Orchestrator)
  ├── Agent 1 → Restaurant 1
  ├── Agent 2 → Restaurant 2
  ├── Agent 3 → Restaurant 3
  └── ...
```

Each agent:
- Runs in its own Browserbase session
- Independently navigates and extracts data
- Saves results with unique identifier
- Handles errors without affecting other agents

## Output

Results are saved as JSON files in `results/`:
- `agent_1_restaurant1_com.json`
- `agent_2_restaurant2_com.json`
- etc.

Each file contains:
- Restaurant information (name, address, hours, contact)
- Menu data organized by sections and categories
- Execution metadata (timing, status, errors)
