import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  QuestionMarkCircleIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  RocketLaunchIcon,
  BeakerIcon,
  PlayIcon,
  BookOpenIcon,
  ShieldCheckIcon,
  CommandLineIcon,
  LightBulbIcon,
  ExclamationTriangleIcon,
  ArrowTopRightOnSquareIcon,
  ChevronRightIcon,
  CpuChipIcon,
  SignalIcon,
} from '@heroicons/react/24/outline';

/* ───────────────────────────── constants ───────────────────────────── */

const ROLE_BADGE = {
  everyone: 'bg-fg-teal/15 text-fg-teal',
  admin: 'bg-red-100 text-red-700',
  engineer: 'bg-blue-100 text-blue-700',
};

const CATEGORY_META = {
  'getting-started': { label: 'Getting Started', icon: RocketLaunchIcon, accent: 'from-fg-teal to-fg-green' },
  'mcp':             { label: 'MCP & Claude Setup', icon: SignalIcon, accent: 'from-cyan-400 to-blue-600' },
  'agents':          { label: 'AI Agent Integration (CLI)', icon: CpuChipIcon, accent: 'from-violet-400 to-purple-600' },
  'test-cases':      { label: 'Test Case Workflows', icon: BeakerIcon, accent: 'from-blue-400 to-indigo-500' },
  'execution':       { label: 'Test Execution', icon: PlayIcon, accent: 'from-green-400 to-emerald-500' },
  'frameworks':      { label: 'Testing Frameworks', icon: BeakerIcon, accent: 'from-teal-400 to-emerald-500' },
  'knowledge':       { label: 'Knowledge Base', icon: BookOpenIcon, accent: 'from-purple-400 to-violet-500' },
  'admin':           { label: 'Admin Workflows', icon: ShieldCheckIcon, accent: 'from-amber-400 to-orange-500' },
  'cli':             { label: 'qaforge.py CLI Reference', icon: CommandLineIcon, accent: 'from-gray-500 to-gray-700' },
};

/* ───────────────────────────── guide data ──────────────────────────── */

const GUIDE_SCENARIOS = [
  /* ── Getting Started ────────────────────────────────────────────── */
  {
    id: 'first-login',
    title: 'First Login & Setup',
    role: 'everyone',
    category: 'getting-started',
    description: 'Log in, change your password, and navigate the platform.',
    prerequisites: ['A QAForge account (admin creates it for you)', 'Browser access to the QAForge URL'],
    steps: [
      'Navigate to your QAForge URL (e.g. https://your-server:8080) and enter your email and password.',
      'After login you land on the **Dashboard** — this shows pending reviews, active projects, and pass rates.',
      'Use the **sidebar** to navigate: Projects, Review Queue, Knowledge Base, and (for admins) Settings & Users.',
      'Go to **Users** (or ask your admin) and click **Change Password** to set a strong password.',
      'Explore the Dashboard to see pending review counts and your assigned projects.',
    ],
    tips: ['Bookmark the QAForge URL for quick access.', 'Your JWT token expires after 24 hours — you will be redirected to login automatically.'],
    warnings: ['Change the default password immediately after first login.'],
  },
  {
    id: 'create-project',
    title: 'Create Your First Project',
    role: 'admin',
    category: 'getting-started',
    description: 'Use the Project Wizard to create a project, assign engineers, and generate an agent key.',
    prerequisites: ['Admin role', 'At least one engineer user created'],
    steps: [
      'Go to **Projects** from the sidebar and click **New Project**.',
      '**Step 1 — Details:** Enter a project name, select the domain (MDM, AI, Data Engineering, etc.), optionally add a sub-domain and description. Check "Auto-generate Agent Key" if agents will submit test results.',
      '**Step 2 — Team:** Select engineers to assign. They will only see this project in their dashboard.',
      '**Step 3 — Success:** Copy the generated agent key and the setup instructions. Share these with your engineer.',
      'The project now appears on the Projects page. Click into it to add requirements, generate test cases, and create test plans.',
    ],
    tips: ['The agent key is shown only once — copy it immediately.', 'You can regenerate a key later from the project detail page.'],
    cli: null,
    related: ['connect-agent', 'generate-from-requirements'],
  },
  /* ── MCP & Claude Code Setup ──────────────────────────────────── */
  {
    id: 'mcp-qa-user-setup',
    title: 'QA User Setup — Claude Code + MCP (No Code Needed)',
    role: 'everyone',
    category: 'mcp',
    description: 'Connect Claude Code to QAForge + Reltio MCP servers and start managing tests using natural language. No codebase, no CLI scripts, no git repo needed.',
    prerequisites: [
      'Node.js 18+ installed on your machine',
      'An Anthropic API key (for Claude Code itself)',
      'QAForge server URL from your admin (e.g. https://your-server:8080)',
    ],
    steps: [
      '**Install Claude Code** — Anthropic\'s AI coding agent that connects to MCP servers.',
      '**Add QAForge MCP server** — this gives Claude access to 20 test management tools (connect to projects, list/generate/submit test cases, create plans, submit results, manage KB, testing frameworks).',
      '**Add Reltio MCP server (optional)** — this adds 45 MDM tools (entity search, match, merge, workflows, data model). Only needed if you work with Reltio.',
      '**Create a workspace and start Claude Code** — no git repo needed, any empty directory works.',
      '**Verify connection** — type `/mcp` in Claude Code to confirm both servers are connected and tools are listed.',
      '**Start working** — talk naturally. Say "Show me all test cases" or "Generate 10 security test cases" and Claude uses the right MCP tool automatically.',
    ],
    cli: [
      { label: 'Step 1: Install Claude Code', cmd: 'npm install -g @anthropic-ai/claude-code' },
      { label: 'Step 2: Add QAForge MCP server', cmd: 'claude mcp add qaforge \\\n  "https://qaforge.freshgravity.net/qaforge-mcp/sse" \\\n  --transport sse' },
      { label: 'Step 3: Add Reltio MCP server (optional)', cmd: 'claude mcp add reltio \\\n  "https://qaforge.freshgravity.net/mcp/sse" \\\n  --transport sse' },
      { label: 'Step 4: Start Claude Code', cmd: 'mkdir -p ~/qa-workspace && cd ~/qa-workspace && claude' },
    ],
    tips: [
      'The QAForge server is at qaforge.freshgravity.net with valid Let\'s Encrypt SSL.',
      'No agent key needed in your terminal — the MCP server has the key configured on the server side.',
      'Works from any directory — you don\'t need a git repo or any project files.',
      'MCP servers persist across Claude Code sessions — you only run the setup commands once.',
    ],
    warnings: ['Valid Let\'s Encrypt SSL — no certificate warnings or special configuration needed.'],
    related: ['claude-desktop-qa-setup', 'mcp-developer-setup', 'mcp-qaforge-tools', 'mcp-reltio-tools'],
  },
  {
    id: 'mcp-developer-setup',
    title: 'Developer Setup — Claude Code + MCP + Full Codebase',
    role: 'engineer',
    category: 'mcp',
    description: 'Get everything QA users have — plus full Git repo access to modify QAForge code, add features, fix bugs, and deploy.',
    prerequisites: [
      'Git access to the QAForge repo (Bitbucket)',
      'Node.js 18+ and Docker (for local development)',
      'An Anthropic API key (for Claude Code)',
    ],
    steps: [
      '**Clone the QAForge repo** — this gives Claude Code access to the full codebase via CLAUDE.md.',
      '**Add both MCP servers** — same commands as the QA User setup. These give Claude Code remote tool access.',
      '**Start Claude Code from the repo** — Claude reads CLAUDE.md automatically and understands the project architecture.',
      '**You now have dual capabilities:** Use MCP tools for test management ("list test cases", "generate from BRD") AND edit source code ("fix the bug in agent_api.py", "add a new MCP tool").',
      '**Deploy changes** — ask Claude to deploy: it pushes to Git, SSHes to the VM, and runs the deploy script.',
    ],
    cli: [
      { label: 'Step 1: Clone the repo', cmd: 'git clone git@bitbucket.org:lifio/qaforge.git\ncd qaforge' },
      { label: 'Step 2: Add QAForge MCP', cmd: 'claude mcp add qaforge \\\n  "https://qaforge.freshgravity.net/qaforge-mcp/sse" \\\n  --transport sse' },
      { label: 'Step 3: Add Reltio MCP', cmd: 'claude mcp add reltio \\\n  "https://qaforge.freshgravity.net/mcp/sse" \\\n  --transport sse' },
      { label: 'Step 4: Start Claude Code from repo', cmd: 'cd ~/Downloads/qaforge && claude' },
    ],
    tips: [
      'Claude Code reads CLAUDE.md at startup — it knows the full architecture, route modules, agent patterns, and deploy commands.',
      'Developers can add new MCP tools: create function in mcp-server/src/tools/, register in server.py, rebuild the container.',
      'Deploy with one command: git push && ssh VM "cd /opt/qaforge && git pull && bash scripts/vm-deploy.sh"',
    ],
    related: ['claude-desktop-dev-setup', 'mcp-qa-user-setup', 'mcp-qaforge-tools', 'agent-claude-code'],
  },
  {
    id: 'mcp-qaforge-tools',
    title: 'QAForge MCP — 20 Available Tools',
    role: 'everyone',
    category: 'mcp',
    description: 'Complete reference of all 20 QAForge MCP tools available through Claude Code. Each tool maps to a QAForge Agent API endpoint.',
    prerequisites: ['QAForge MCP server connected (see QA User Setup or Developer Setup)'],
    steps: [
      '**Connection (2 tools):** `connect` — switch to a different QAForge project by providing its agent key. `connection_status` — check which project is currently connected and whether using a session override or server default.',
      '**Project (2 tools):** `get_project` — get project metadata, domain, app profile, description. `update_project` — update description or BRD/PRD context text.',
      '**Requirements (3 tools):** `list_requirements` — list all project requirements. `extract_requirements` — AI-extract structured requirements from BRD/PRD text. `submit_requirements` — submit manually created requirements.',
      '**Test Cases (3 tools):** `list_test_cases` — list test cases, filter by status or plan. `generate_test_cases` — AI-generate from frameworks + requirements + KB (auto-fetches domain frameworks as mandatory test areas). `submit_test_cases` — submit structured test cases.',
      '**Test Plans (3 tools):** `list_test_plans` — list plans with pass/fail stats. `create_test_plan` — create smoke, regression, e2e, or custom plan with test case binding. `get_plan_test_cases` — get test cases assigned to a plan.',
      '**Execution (2 tools):** `submit_results` — submit execution results with proof artifacts (API responses, screenshots, logs). `add_proof` — attach additional proof to an existing execution.',
      '**Knowledge Base (2 tools):** `kb_stats` — KB statistics by domain/sub-domain. `upload_reference` — upload reference test cases for AI generation quality.',
      '**Frameworks (2 tools):** `get_frameworks` — fetch domain-specific testing standards, patterns, and quality gates. `check_framework_coverage` — gap analysis comparing test cases against framework sections.',
      '**Summary (1 tool):** `get_summary` — project quality dashboard: total test cases, pass rates, execution stats, coverage percentage.',
    ],
    tips: [
      'All tools are project-scoped — the agent key determines which project you access.',
      'Use `connect(agent_key)` to switch between projects without restarting the MCP server.',
      'You don\'t need to remember tool names. Just say "show me test cases" and Claude picks the right tool.',
      'Example prompts: "Generate 10 security test cases", "Create a smoke test plan", "What\'s the pass rate?", "Check framework coverage for MDM".',
      '`generate_test_cases` now auto-fetches testing frameworks as mandatory test areas — ensuring AI-generated tests satisfy domain standards.',
      'SSE endpoint: https://qaforge.freshgravity.net/qaforge-mcp/sse',
    ],
    related: ['mcp-connect-project', 'mcp-reltio-tools', 'mcp-qa-user-setup'],
  },
  {
    id: 'mcp-reltio-tools',
    title: 'Reltio MCP — 45 Available Tools',
    role: 'everyone',
    category: 'mcp',
    description: 'Complete reference of all 45 Reltio MDM tools for entity management, matching, merging, workflows, and tenant configuration.',
    prerequisites: ['Reltio MCP server connected (see QA User Setup)', 'A configured Reltio tenant with valid credentials on the server'],
    steps: [
      '**Entity Management (7 tools):** `search_entities_tool` — search by filter. `get_entity_tool` — get by ID. `get_entity_with_matches_tool` — entity + potential matches. `get_entity_graph_tool` — graph traversal (hops). `get_entity_parents_tool` — find parent paths. `create_entity_tool` — create entities. `update_entity_attributes_tool` — update attributes.',
      '**Match Management (7 tools):** `find_potential_matches_tool` — by rule/score/confidence. `get_potential_matches_stats_tool` — match counts. `get_entity_match_history_tool` — match history. `merge_entities_tool` — merge two entities. `unmerge_entity_tool` — unmerge contributor. `reject_entity_match_tool` — reject duplicate. `export_merge_tree_tool` — export merge tree.',
      '**Relationships & Interactions (7 tools):** `get_entity_relations_tool` — connections. `get_relation_details_tool` — relation by ID. `relation_search_tool` — search relationships. `create_relationships_tool` — create relations. `delete_relation_tool` — delete relation. `get_entity_interactions_tool` — interactions. `create_interaction_tool` — create interaction.',
      '**Tenant Configuration (10 tools):** `get_business_configuration_tool` — full config. `get_tenant_metadata_tool` — metadata. `get_tenant_permissions_metadata_tool` — permissions. `get_data_model_definition_tool` — data model. Plus entity, relation, interaction, graph, grouping, and change request type definitions.',
      '**User & Activity (4 tools):** `get_users_by_role_and_tenant_tool` — users by role. `get_users_by_group_and_tenant_tool` — users by group. `check_user_activity_tool` — check activity. `get_merge_activities_tool` — merge events.',
      '**Workflow Management (7 tools):** `get_user_workflow_tasks_tool` — user tasks. `get_task_details_tool` — task details. `retrieve_tasks_tool` — tasks by filter. `get_possible_assignees_tool` — possible assignees. `reassign_workflow_task_tool` — reassign. `start_process_instance_tool` — start workflow. `execute_task_action_tool` — execute action.',
      '**Reference Data & System (3 tools):** `rdm_lookups_list_tool` — RDM lookups. `health_check_tool` — server health. `capabilities_tool` — list all capabilities.',
    ],
    tips: [
      'Entity URIs from search_entities_tool can be passed to merge, unmerge, and relation tools.',
      'Use get_data_model_definition_tool to understand the tenant\'s entity types before searching.',
      'Example prompts: "Search for entities where FirstName starts with John", "Find potential matches for entity X", "Merge these two entities".',
      'SSE endpoint: https://qaforge.freshgravity.net/mcp/sse',
    ],
    related: ['mcp-qaforge-tools', 'mcp-qa-user-setup'],
  },
  {
    id: 'mcp-connect-project',
    title: 'Switch Projects — Connect to a Different QAForge Project',
    role: 'everyone',
    category: 'mcp',
    description: 'Switch between QAForge projects within the same Claude Code session using the `connect` tool. No server restart or env changes needed.',
    prerequisites: ['QAForge MCP server connected (see QA User Setup)', 'Agent key for the target project (from Project Settings or admin)'],
    steps: [
      '**Get the agent key** for the project you want to switch to. Find it in the project detail page under the Test Plans tab > "Agent API Key" section, or ask your admin.',
      '**Tell Claude to connect** — just say: "connect to project X with key qf_xxx..." Claude will call the `connect` tool automatically.',
      '**Verify the switch** — say "which project am I connected to?" or "connection status". Claude will confirm the project name, domain, and key source.',
      '**Start working** — all subsequent MCP tool calls (list test cases, generate, submit results, etc.) now operate on the new project.',
      '**Switch again anytime** — just provide a different agent key. The previous project data is untouched; you are just changing which project the tools target.',
    ],
    tips: [
      'Each project has its own agent key — generated in Project Settings or during project creation.',
      'The `connect` tool validates the key before switching. If the key is invalid, nothing changes.',
      'Use `connection_status` to see whether you are using a session override or the server default key.',
      'The server-configured default key (from QAFORGE_AGENT_KEY env) still works as a fallback when no override is set.',
    ],
    warnings: ['Agent keys are project-scoped. Make sure you have the right key for the project you want to access.'],
    related: ['mcp-qaforge-tools', 'create-project', 'mcp-qa-user-setup'],
  },
  {
    id: 'claude-desktop-qa-setup',
    title: 'Claude Desktop — QA Mode (No Terminal Needed)',
    role: 'everyone',
    category: 'mcp',
    description: 'Set up Claude Desktop (Anthropic\'s desktop app) with QAForge + Reltio MCP servers. No terminal, no CLI, no git repo — just a desktop app with full MCP tool access.',
    prerequisites: [
      'Claude Desktop app installed (download from claude.ai/download)',
      'QAForge server URL from your admin (e.g. https://your-server:8080)',
      'An Anthropic account (for Claude Desktop login)',
    ],
    steps: [
      '**Download Claude Desktop** from claude.ai/download (macOS or Windows). Install and sign in with your Anthropic account.',
      '**Open the config file** — Claude Desktop stores its MCP server configuration in a JSON file on your machine.',
      '**Add QAForge + Reltio MCP servers** — paste the JSON configuration (see below) into the config file. URLs are pre-configured for qaforge.freshgravity.net.',
      '**Quit and reopen Claude Desktop** — press Cmd+Q (Mac) or close completely (Windows), then reopen. MCP servers load on startup.',
      '**Verify connection** — start a new conversation and ask "What tools do you have?" or "Show me MCP tools." You should see QAForge and Reltio tools listed.',
      '**Connect to your project** — say: "Connect to my project with key qf_xxx..." (get the key from your admin or the Project Settings page in QAForge UI).',
      '**Start working** — you now have full access to 65 tools (20 QAForge + 45 Reltio). Just talk naturally: "Show me all test cases", "Generate 10 regression tests", "Search Reltio for entities with FirstName John".',
    ],
    cli: [
      { label: 'Config file location (macOS)', cmd: '~/Library/Application Support/Claude/claude_desktop_config.json' },
      { label: 'Config file location (Windows)', cmd: '%APPDATA%\\Claude\\claude_desktop_config.json' },
      { label: 'JSON to add (paste into config file)', cmd: '{\n  "mcpServers": {\n    "qaforge": {\n      "url": "https://qaforge.freshgravity.net/qaforge-mcp/sse"\n    },\n    "reltio": {\n      "url": "https://qaforge.freshgravity.net/mcp/sse"\n    }\n  }\n}' },
    ],
    tips: [
      'The QAForge server is at qaforge.freshgravity.net — no port number needed.',
      'If the config file already has content, merge the "mcpServers" block into the existing JSON — don\'t overwrite the whole file.',
      'Claude Desktop is ideal for QA users who don\'t need terminal or codebase access.',
      'You can add more MCP servers later by editing the same config file.',
      'On macOS, open the config file quickly: open the Terminal app and run: open ~/Library/Application\\ Support/Claude/claude_desktop_config.json',
    ],
    warnings: [
      'You must fully quit Claude Desktop (Cmd+Q on Mac) and reopen it for new MCP servers to take effect.',
      'Valid Let\'s Encrypt SSL — works out of the box with Claude Desktop.',
    ],
    related: ['claude-desktop-dev-setup', 'mcp-qa-user-setup', 'mcp-qaforge-tools', 'mcp-connect-project'],
  },
  {
    id: 'claude-desktop-dev-setup',
    title: 'Claude Desktop — Developer Mode (Full Codebase Access)',
    role: 'engineer',
    category: 'mcp',
    description: 'Use Claude Desktop with MCP servers AND full codebase access. Open a project folder in Claude Desktop to get file editing, terminal commands, git operations, and all 65 MCP tools in one session.',
    prerequisites: [
      'Claude Desktop app installed with MCP servers configured (see QA Mode setup first)',
      'Git access to the QAForge repo (or any project repo)',
      'Node.js 18+ (for Claude Code features inside Desktop)',
    ],
    steps: [
      '**Complete the QA Mode setup first** — add QAForge and Reltio MCP servers to your Claude Desktop config file (see "Claude Desktop — QA Mode" scenario).',
      '**Open your project in Claude Desktop** — use File > Open Folder (or drag the project folder onto Claude Desktop). This gives Claude access to your full codebase.',
      '**Alternatively, use Claude Code from the project directory** — run `claude` from your repo root. Claude Code reads the `.mcp.json` file in the project root for MCP server config.',
      '**For Claude Code: add a `.mcp.json` file** to your project root with the MCP server configuration (see below). This auto-loads MCP servers when Claude Code starts from that directory.',
      '**You now have dual capabilities:** All 65 MCP tools for test management + full codebase access to edit code, run commands, deploy, and debug.',
      '**Example developer workflows:** "Fix the bug in api_client.py and then run the smoke tests via QAForge", "Add a new MCP tool for test plan export, then test it by calling it", "Generate test cases from this BRD file in my Downloads folder".',
    ],
    cli: [
      { label: 'Option A: .mcp.json in project root (for Claude Code)', cmd: '# Create .mcp.json in your project root:\n{\n  "mcpServers": {\n    "qaforge": {\n      "type": "sse",\n      "url": "https://qaforge.freshgravity.net/qaforge-mcp/sse"\n    },\n    "reltio": {\n      "type": "sse",\n      "url": "https://qaforge.freshgravity.net/mcp/sse"\n    }\n  }\n}' },
      { label: 'Option B: Global config (for Claude Code CLI)', cmd: 'claude mcp add qaforge \\\n  "https://qaforge.freshgravity.net/qaforge-mcp/sse" \\\n  --transport sse\n\nclaude mcp add reltio \\\n  "https://qaforge.freshgravity.net/mcp/sse" \\\n  --transport sse' },
      { label: 'Start Claude Code from repo', cmd: 'cd ~/path/to/your/project && claude' },
    ],
    tips: [
      'Claude Code reads CLAUDE.md at startup — add QAForge instructions there so Claude knows how to run tests and submit results automatically.',
      '.mcp.json is project-scoped (only loads when Claude Code runs from that directory). `claude mcp add` is user-scoped (loads in every session).',
      'Developer mode gives you the power to fix a bug, run tests, submit results to QAForge, and deploy — all in one conversation.',
      'Developers can also add new MCP tools: create a function in mcp-server/src/tools/, register in server.py, rebuild the container, and immediately test via MCP.',
    ],
    warnings: [
      'Keep .mcp.json in .gitignore if it contains internal server addresses you don\'t want in version control.',
      'The .mcp.json format uses "type": "sse" while claude_desktop_config.json just uses "url" directly — they are different formats.',
    ],
    related: ['claude-desktop-qa-setup', 'mcp-developer-setup', 'mcp-qaforge-tools', 'agent-claude-code'],
  },

  /* ── AI Agent Integration ──────────────────────────────────────── */
  {
    id: 'connect-agent',
    title: 'Connect Your Agent (qaforge.py)',
    role: 'engineer',
    category: 'agents',
    description: 'Set up the qaforge.py CLI to connect your development environment to QAForge.',
    prerequisites: ['Python 3.8+', 'Agent key or bootstrap token from admin', 'qaforge.py script in your project\'s scripts/ folder'],
    steps: [
      'Get the agent key from your admin (or the bootstrap token if self-onboarding).',
      'Run the setup command — this saves the API URL and key to your `.env` file:',
      'Verify connectivity:',
      'You are now ready to submit test cases, run tests, and sync results with QAForge.',
    ],
    cli: [
      { label: 'Option A: Setup with agent key', cmd: 'python scripts/qaforge.py setup \\\n  --project "My Project" \\\n  --token "qf_your_agent_key_here"' },
      { label: 'Option B: Bootstrap (self-onboarding)', cmd: 'python scripts/qaforge.py setup \\\n  --project "My Project" \\\n  --token "bootstrap-token-from-admin" \\\n  --domain mdm --sub-domain reltio' },
      { label: 'Verify', cmd: 'python scripts/qaforge.py status' },
    ],
    tips: ['The setup command creates/updates QAFORGE_API_URL and QAFORGE_AGENT_KEY in your .env file.', 'qaforge.py auto-installs the openpyxl dependency if needed.'],
    related: ['create-project', 'agent-claude-code', 'agent-other-agents'],
  },
  {
    id: 'agent-claude-code',
    title: 'Setting Up Claude Code with QAForge',
    role: 'engineer',
    category: 'agents',
    description: 'Configure Claude Code (Anthropic\'s AI coding agent) to submit test results, generate test cases, and sync with QAForge — all through CLAUDE.md project instructions.',
    prerequisites: [
      'Claude Code installed and authenticated',
      'A QAForge project with an agent key (or a bootstrap token from your admin)',
      'Python 3.8+ in your project environment',
    ],
    steps: [
      '**Copy qaforge.py** into your project\'s `scripts/` folder. This is the CLI bridge between Claude Code and QAForge.',
      '**Add QAForge instructions to your CLAUDE.md** — Claude Code reads this file at the start of every session. Paste the QAForge section (see "CLAUDE.md Template" scenario) into your project\'s `CLAUDE.md` file.',
      '**Run setup** — in your Claude Code session, ask it to run the setup command. Claude reads the instructions from CLAUDE.md and executes automatically.',
      '**Verify** — ask Claude Code to check connectivity: it should show your project name, test case count, and KB stats.',
      '**Start using QAForge** — Claude Code can now: run tests and auto-submit (`run-smoke`, `run-pytest`, `run-playwright`), generate test cases from BRD (`generate-from-brd`), submit requirements, and check progress (`summary`).',
      'Claude Code will automatically follow the QAForge workflow documented in CLAUDE.md — running tests, capturing proof artifacts, and submitting results without manual intervention.',
    ],
    cli: [
      { label: 'Step 1: Setup (in Claude Code session)', cmd: 'python scripts/qaforge.py setup \\\n  --project "My App QA" \\\n  --token "bootstrap-token-from-admin" \\\n  --domain mdm --sub-domain reltio' },
      { label: 'Step 2: Verify', cmd: 'python scripts/qaforge.py status' },
      { label: 'Step 3: Run tests + auto-submit', cmd: 'python scripts/qaforge.py run-smoke\npython scripts/qaforge.py run-pytest backend/tests/' },
    ],
    tips: [
      'Claude Code reads CLAUDE.md at session start — it learns all QAForge commands automatically.',
      'The setup command saves QAFORGE_API_URL and QAFORGE_AGENT_KEY to your .env file, so subsequent sessions pick it up automatically.',
      'You can ask Claude Code natural-language like "run the smoke tests and submit to QAForge" — it knows how because of CLAUDE.md.',
    ],
    warnings: ['Keep your .env file in .gitignore — it contains the agent API key.'],
    related: ['agent-claude-md-template', 'connect-agent', 'agent-workflow-tests'],
  },
  {
    id: 'agent-other-agents',
    title: 'Setting Up Codex, Gemini CLI & Other Agents',
    role: 'engineer',
    category: 'agents',
    description: 'Configure OpenAI Codex, Google Gemini CLI, Cursor, Windsurf, or any AI coding agent to work with QAForge. The qaforge.py CLI works identically across all agents.',
    prerequisites: [
      'An AI coding agent installed (Codex, Gemini CLI, Cursor, Windsurf, etc.)',
      'A QAForge project with an agent key or bootstrap token',
      'Python 3.8+ in your project environment',
    ],
    steps: [
      '**Copy qaforge.py** into your project\'s `scripts/` folder — same script for all agents.',
      '**Add QAForge instructions to your agent\'s config file.** Each agent reads a different file:',
      '• **Codex:** Add to `codex.md` or `.codex/instructions.md` in your project root.',
      '• **Gemini CLI:** Add to `GEMINI.md` or the agent\'s context file.',
      '• **Cursor:** Add to `.cursorrules` or the project instructions panel.',
      '• **Windsurf:** Add to `.windsurfrules` or the cascade rules file.',
      '• **Generic agents:** Use environment variables and document commands in your README.',
      '**Run setup** — the qaforge.py setup command is identical regardless of which agent runs it.',
      '**For agents without a config file** — set env vars directly: `export QAFORGE_API_URL=...` and `export QAFORGE_AGENT_KEY=...`.',
      'All qaforge.py commands work the same across all agents.',
    ],
    cli: [
      { label: 'Setup (works with any agent)', cmd: 'python scripts/qaforge.py setup \\\n  --project "My Project" \\\n  --token "bootstrap-token" \\\n  --domain data_eng --sub-domain snowflake' },
      { label: 'Environment variables (alternative)', cmd: 'export QAFORGE_API_URL=https://your-server:8080/api\nexport QAFORGE_AGENT_KEY=qf_your_key_here\npython scripts/qaforge.py status' },
    ],
    tips: [
      'qaforge.py reads from .env automatically — once setup is done, all agents in the project share the same config.',
      'For Codex: paste the same QAForge CLAUDE.md section into your codex.md — the instructions are agent-agnostic.',
      'Agents that can make HTTP calls directly can skip qaforge.py and use the REST API with the X-Agent-Key header.',
    ],
    related: ['agent-claude-code', 'agent-rest-api', 'agent-claude-md-template'],
  },
  {
    id: 'agent-workflow-tests',
    title: 'Agent Workflow: Run Tests & Auto-Submit',
    role: 'engineer',
    category: 'agents',
    description: 'The core agent workflow — run smoke tests, pytest, or Playwright E2E tests and have results (with proof artifacts) automatically submitted to QAForge.',
    prerequisites: [
      'qaforge.py connected (setup complete, .env configured)',
      'Tests written and runnable locally (smoke, pytest, or Playwright)',
    ],
    steps: [
      '**Ask your agent to run tests.** Example prompt: "Run the smoke tests and submit results to QAForge."',
      'The agent runs the appropriate qaforge.py command (`run-smoke`, `run-pytest`, or `run-playwright`).',
      '**qaforge.py captures:** pass/fail status, test duration, stdout/stderr output, and (for Playwright) screenshots.',
      '**Auto-submit:** Results are submitted to QAForge as execution results with proof artifacts attached.',
      '**Proof artifacts** include: `api_response` (HTTP status & body), `test_output` (stdout/stderr), `screenshot` (Playwright captures), `log` (error traces).',
      'Check results in the QAForge web UI → **Review Queue** → **Executions** tab.',
      'Approve passed tests in bulk using **Approve All Passed** in the Review Queue.',
    ],
    cli: [
      { label: 'Smoke tests', cmd: 'python scripts/qaforge.py run-smoke' },
      { label: 'Pytest', cmd: 'python scripts/qaforge.py run-pytest backend/tests/' },
      { label: 'Playwright E2E (all specs)', cmd: 'python scripts/qaforge.py run-playwright' },
      { label: 'Playwright (specific spec)', cmd: 'python scripts/qaforge.py run-playwright \\\n  --spec e2e/candidates.spec.js' },
    ],
    tips: [
      'Each run creates an "agent session" — you can track which agent ran which tests in the project dashboard.',
      'Proof artifact types: api_response, test_output, screenshot, log, query_result, data_comparison.',
      'Failed tests appear in the Review Queue with error details and stack traces for debugging.',
      'After fixing a bug, re-run the failing tests — QAForge tracks execution history per test case.',
    ],
    related: ['submit-execution', 'review-results', 'agent-claude-code'],
  },
  {
    id: 'agent-workflow-brd',
    title: 'Agent Workflow: Extract Requirements from BRD',
    role: 'engineer',
    category: 'agents',
    description: 'Have your AI agent read a BRD/PRD document, extract testable requirements, and submit them to QAForge for full traceability.',
    prerequisites: [
      'qaforge.py connected',
      'A BRD/PRD document (Excel .xlsx, text file, or raw text)',
    ],
    steps: [
      '**Ask your agent to extract requirements.** Example: "Read the BRD at ~/Desktop/BRD.xlsx and extract requirements for the MDM domain."',
      'The agent uses `extract-requirements` (text files) or the REST API `POST /api/agent/requirements/extract` (raw text).',
      '**AI extraction:** QAForge uses domain-specific AI to identify testable requirements — data load specs, validation rules, business rules, acceptance criteria.',
      'Extracted requirements get auto-assigned REQ IDs (REQ-001, REQ-002, etc.) and persisted.',
      'Requirements appear in your project\'s **Requirements** tab with full traceability.',
      'You can then **generate test cases** from these requirements — creating a Requirements → Test Cases → Executions chain.',
    ],
    cli: [
      { label: 'Extract from text file', cmd: 'python scripts/qaforge.py extract-requirements \\\n  --file ~/Desktop/BRD.txt --domain mdm' },
      { label: 'Extract with focus areas', cmd: 'python scripts/qaforge.py extract-requirements \\\n  --file ~/Desktop/BRD.txt \\\n  --domain data_eng --sub-domain snowflake \\\n  --focus "data quality rules"' },
      { label: 'Submit structured requirements', cmd: 'python scripts/qaforge.py submit-requirements <<\'EOF\'\n[\n  {"req_id": "REQ-001", "title": "Customer entity load",\n   "priority": "high", "category": "data_load"},\n  {"req_id": "REQ-002", "title": "Count reconciliation",\n   "priority": "high", "category": "validation"}\n]\nEOF' },
    ],
    tips: [
      'Extraction is domain-aware: MDM gets match/merge rules, Data Eng gets pipeline specs, AI gets model evaluation criteria.',
      'For Excel BRDs, use generate-from-brd instead — it handles Excel parsing and generates test cases directly.',
      'Agent-submitted requirements are tagged with source="agent" for audit trail.',
    ],
    related: ['agent-requirements', 'agent-workflow-generate', 'upload-brd-file'],
  },
  {
    id: 'agent-workflow-generate',
    title: 'Agent Workflow: Generate Test Cases from BRD',
    role: 'engineer',
    category: 'agents',
    description: 'Generate enterprise-grade test cases from a BRD spreadsheet with optional reference learning from the Knowledge Base — the most powerful agent workflow.',
    prerequisites: [
      'qaforge.py connected',
      'BRD Excel file (.xlsx) with requirement descriptions',
      'Optional: Reference test case Excel for style/format learning',
    ],
    steps: [
      '**Ask your agent to generate test cases.** Example: "Generate 10 MDM test cases from the BRD at ~/Desktop/Network_Entity_BRD.xlsx."',
      'The agent runs `generate-from-brd` with the BRD file path, domain, and optional reference.',
      '**With reference Excel (first time):** QAForge learns the test case format/style from your reference and auto-saves samples to the Knowledge Base.',
      '**Without reference (subsequent runs):** QAForge auto-retrieves the best matching KB entries using BRD-aware keyword matching.',
      'The AI generates test cases with: multi-step procedures, SQL scripts, expected results, priority, category, and domain tags.',
      'Generated test cases appear with "draft" status. Review and approve them in the **Review Queue**.',
    ],
    cli: [
      { label: 'With reference (first time)', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/Sample_MDM_TC.xlsx \\\n  --reference ~/Desktop/Sample_MDM_TC.xlsx \\\n  --domain mdm --sub-domain reltio --count 10' },
      { label: 'Without reference (uses KB)', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/new_requirement.xlsx \\\n  --domain mdm --sub-domain reltio --count 5' },
      { label: 'Data Engineering domain', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/DE_Specs.xlsx \\\n  --domain data_eng --sub-domain snowflake --count 10' },
    ],
    tips: [
      'Upload references per domain separately (MDM, Data Eng, AI) — KB matches by domain and keywords.',
      'The first reference upload teaches QAForge your team\'s testing style. Subsequent runs are smarter.',
      'Domains: mdm, ai, data_eng, integration, digital. Sub-domains: reltio, snowflake, databricks, etc.',
    ],
    warnings: ['Large BRD files may take 30-60 seconds to process depending on the LLM provider.'],
    related: ['generate-from-brd', 'upload-reference', 'agent-workflow-brd'],
  },
  {
    id: 'agent-rest-api',
    title: 'Agent REST API Reference',
    role: 'engineer',
    category: 'agents',
    description: 'Complete reference for the QAForge Agent API — for agents that call HTTP endpoints directly instead of using qaforge.py.',
    prerequisites: [
      'A QAForge agent API key (starts with qf_)',
      'HTTP client capability (curl, requests, fetch, etc.)',
    ],
    steps: [
      '**Authentication:** All agent endpoints require the `X-Agent-Key` header with your `qf_...` key. No JWT needed.',
      '**Base URL:** `https://your-server:8080/api/agent/` — all endpoints under `/agent/`.',
      '**Bootstrap:** `POST /bootstrap` with `X-Bootstrap-Token` — creates project + returns agent key.',
      '**Sessions:** `POST /sessions` — create a tracking session (agent_name, version, mode).',
      '**Test Cases:** `POST /test-cases` — batch submit. `GET /test-cases` — list (filter by status, plan).',
      '**Executions:** `POST /executions` — submit results with proof artifacts. `POST /executions/{id}/proof` — add proof to existing result.',
      '**Requirements:** `POST /requirements` — batch submit. `GET /requirements` — list. `POST /requirements/extract` — AI extraction.',
      '**Test Plans:** `POST /test-plans` — create plans to group test cases.',
      '**Generation:** `POST /generate-from-brd` — generate test cases from BRD text + optional reference TCs.',
      '**Knowledge Base:** `POST /upload-reference` — upload reference TCs. `GET /kb-stats` — check KB coverage.',
      '**Project:** `PUT /project` — update metadata (app_profile, description, brd_prd_text).',
      '**Summary:** `GET /summary` — project progress (totals, pass rate, pending reviews).',
    ],
    cli: [
      { label: 'Bootstrap (create project + get key)', cmd: 'curl -sk -X POST https://your-server:8080/api/agent/bootstrap \\\n  -H "X-Bootstrap-Token: bootstrap-token" \\\n  -H "Content-Type: application/json" \\\n  -d \'{"project_name": "My Project", "domain": "mdm"}\'' },
      { label: 'Submit test cases', cmd: 'curl -sk -X POST https://your-server:8080/api/agent/test-cases \\\n  -H "X-Agent-Key: qf_your_key" \\\n  -H "Content-Type: application/json" \\\n  -d \'{"test_cases": [{"test_case_id": "TC-001",\n    "title": "Verify login", "priority": "P1",\n    "category": "functional", "execution_type": "api",\n    "expected_result": "200 OK"}]}\'' },
      { label: 'Submit execution results', cmd: 'curl -sk -X POST https://your-server:8080/api/agent/executions \\\n  -H "X-Agent-Key: qf_your_key" \\\n  -H "Content-Type: application/json" \\\n  -d \'{"executions": [{"test_case_id": "<uuid>",\n    "status": "passed", "actual_result": "200 OK",\n    "duration_ms": 150}]}\'' },
      { label: 'Get project summary', cmd: 'curl -sk https://your-server:8080/api/agent/summary \\\n  -H "X-Agent-Key: qf_your_key"' },
    ],
    tips: [
      'Agent keys are project-scoped — each key can only access its own project\'s data.',
      '-s in curl suppresses progress. No -k flag needed — qaforge.freshgravity.net has valid Let\'s Encrypt SSL.',
      'Proof artifact types: api_response, test_output, screenshot, log, query_result, data_comparison.',
      'Test case statuses: draft, approved, executed, passed, failed, deprecated.',
    ],
    warnings: ['Agent API keys are SHA-256 hashed in the database. If you lose your key, regenerate from the project settings page.'],
    related: ['connect-agent', 'agent-claude-code', 'cli-reference'],
  },
  {
    id: 'agent-claude-md-template',
    title: 'CLAUDE.md Template for QAForge',
    role: 'engineer',
    category: 'agents',
    description: 'A ready-to-copy CLAUDE.md section for any project. Paste it into your CLAUDE.md (or codex.md / .cursorrules) to enable agent integration with QAForge.',
    prerequisites: [
      'A project with a CLAUDE.md file (or create one)',
      'qaforge.py in the project\'s scripts/ folder',
    ],
    steps: [
      '**Create or open your project\'s CLAUDE.md** — Claude Code reads this file at the start of every session.',
      '**Copy the QAForge section below** and paste it into your CLAUDE.md. Replace placeholders with your actual values.',
      'The template includes: setup, test runners, BRD generation, KB commands, ad-hoc submissions, and all valid enum values.',
      '**Key sections in the template:**',
      '• **Getting Started** — setup with bootstrap token, status check',
      '• **Run Tests & Auto-Submit** — run-smoke, run-pytest, run-playwright commands',
      '• **Generate from BRD** — with/without reference, domain-specific',
      '• **Requirements** — submit-requirements, extract-requirements',
      '• **Enum Values** — domains, categories, priorities, execution types, proof types',
      'Claude Code will parse this section and understand how to interact with QAForge without any additional prompting.',
    ],
    cli: [
      { label: 'Copy this into your CLAUDE.md', cmd: '### QAForge Integration (Test Documentation)\n\nQAForge is our enterprise test documentation platform.\nUse it for test case generation, test logging, and KB management.\n\n**Setup (first time only):**\npython scripts/qaforge.py setup \\\n  --project "YOUR_PROJECT" \\\n  --token "YOUR_BOOTSTRAP_TOKEN" \\\n  --domain YOUR_DOMAIN --sub-domain YOUR_SUB_DOMAIN\npython scripts/qaforge.py status\n\n**Run Tests & Auto-Submit:**\npython scripts/qaforge.py run-smoke\npython scripts/qaforge.py run-pytest backend/tests/\npython scripts/qaforge.py run-playwright\n\n**Generate Test Cases from BRD:**\npython scripts/qaforge.py generate-from-brd \\\n  --brd ~/path/to/BRD.xlsx \\\n  --domain YOUR_DOMAIN --count 10\n\n**Requirements:**\npython scripts/qaforge.py submit-requirements \'[{...}]\'\npython scripts/qaforge.py extract-requirements --file BRD.txt\n\n**Check Progress:**\npython scripts/qaforge.py summary\n\n**Domains:** mdm | ai | data_eng | integration | digital\n**Categories:** functional | integration | regression | smoke | e2e\n**Priorities:** P1 | P2 | P3 | P4\n**Proof types:** api_response | test_output | screenshot | log' },
    ],
    tips: [
      'Replace YOUR_PROJECT, YOUR_DOMAIN, YOUR_SUB_DOMAIN, and YOUR_BOOTSTRAP_TOKEN with your actual values.',
      'The template is agent-agnostic — works for Codex (codex.md), Gemini CLI, Cursor (.cursorrules), etc.',
      'Keep it concise — agents have limited context windows. The template above is ~500 tokens.',
      'For a real-world example, see the Orbit Recruitment App\'s CLAUDE.md — it uses this exact pattern.',
    ],
    related: ['agent-claude-code', 'agent-other-agents', 'connect-agent'],
  },

  /* ── Test Case Workflows ────────────────────────────────────────── */
  {
    id: 'generate-from-requirements',
    title: 'Generate Test Cases from Requirements',
    role: 'everyone',
    category: 'test-cases',
    description: 'Add requirements to a project, then use AI to auto-generate test cases.',
    prerequisites: ['An active project', 'At least one requirement added'],
    steps: [
      'Open your project and go to the **Requirements** tab.',
      'Click **Add Requirement** — enter a title, description, priority (high/medium/low), and source (BRD/PRD/manual).',
      'Alternatively, paste raw BRD/PRD text and click **Extract** to let AI parse it into structured requirements.',
      'Go to the **Test Cases** tab and click **Generate**.',
      'Select which requirements to generate from, choose priority and category, then click **Generate Test Cases**.',
      'AI generates test cases with steps, expected results, priority, and category. They appear with "draft" status.',
      'Review them in the **Review Queue** — approve, reject, or request changes.',
    ],
    tips: ['Add as many requirements as possible before generating — the AI uses all of them for context.', 'Higher priority requirements get more thorough test cases.'],
    related: ['review-results', 'generate-from-brd'],
  },
  {
    id: 'generate-from-brd',
    title: 'Generate Enterprise Test Cases from BRD (Excel)',
    role: 'engineer',
    category: 'test-cases',
    description: 'Use qaforge.py to generate domain-specific test cases from a BRD spreadsheet with reference examples.',
    prerequisites: ['qaforge.py connected (run setup first)', 'BRD Excel file (.xlsx)', 'Optional: Reference test case Excel for in-context learning'],
    steps: [
      'Prepare your BRD Excel file — it should contain requirement descriptions, acceptance criteria, or specifications.',
      'Optionally prepare a reference Excel with example test cases — QAForge learns the format and style from these.',
      'Run the generate command (see CLI below).',
      'QAForge reads the BRD, retrieves relevant KB patterns, uses the reference for style, and generates domain-specific test cases.',
      'Generated test cases appear in your project with "draft" status — review them in the Review Queue.',
    ],
    cli: [
      { label: 'With reference (recommended)', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/Sample_MDM_TC.xlsx \\\n  --reference ~/Desktop/Sample_MDM_TC.xlsx \\\n  --domain mdm --sub-domain reltio --count 10' },
      { label: 'Without reference (uses KB)', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/new_requirement.xlsx \\\n  --domain mdm --sub-domain reltio --count 5' },
      { label: 'Data Engineering domain', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/DE_Specs.xlsx \\\n  --reference ~/Desktop/Sample_DE_TC.xlsx \\\n  --domain data_eng --sub-domain snowflake --count 10' },
    ],
    tips: [
      'The first time you provide a reference Excel, QAForge auto-saves it to the Knowledge Base for future use.',
      'On subsequent runs without --reference, QAForge auto-retrieves the best matching reference from KB.',
      'Supported domains: mdm, ai, data_eng, integration, digital, app.',
    ],
    warnings: ['Large BRD files may take 30-60 seconds to process depending on your LLM provider.'],
    related: ['upload-reference', 'connect-agent', 'upload-brd-file', 'agent-workflow-generate'],
  },
  {
    id: 'upload-brd-file',
    title: 'Upload BRD/PRD File (Excel, PDF, Word)',
    role: 'everyone',
    category: 'test-cases',
    description: 'Upload a BRD/PRD file directly — no copy-paste needed. Supports .xlsx, .pdf, and .docx formats.',
    prerequisites: ['An active project', 'A BRD/PRD file in .xlsx, .pdf, or .docx format (max 10 MB)'],
    steps: [
      'Open your project and go to the **Requirements** tab.',
      'Click **Upload BRD/PRD** to expand the extraction panel.',
      'Select the **Upload File** tab (default). You can also switch to **Paste Text** for the classic text-paste mode.',
      'Drag and drop your file onto the drop zone, or click **Browse** to select a file.',
      'The file name, size, and type will be shown. Click the **X** to remove and try a different file.',
      'Click **Extract Requirements** — the AI extracts text from the file and identifies testable requirements.',
      'Extracted requirements appear in the requirements list with auto-assigned REQ IDs.',
    ],
    tips: [
      'Excel files (.xlsx): All sheets are read — put your requirements in any sheet.',
      'PDF files: Text is extracted from all pages. Scanned PDFs (images) are not supported — use text-based PDFs.',
      'Word files (.docx): All paragraphs and table content are extracted.',
      'The extraction uses domain-specific AI — MDM projects get match/merge rules, Data Engineering projects get pipeline specs, etc.',
    ],
    warnings: ['Maximum file size is 10 MB. For very large documents, consider splitting into sections.'],
    related: ['generate-from-brd', 'generate-from-requirements'],
  },
  {
    id: 'agent-requirements',
    title: 'Submit Requirements via Agent API',
    role: 'engineer',
    category: 'test-cases',
    description: 'Use the CLI or Agent API to submit and extract requirements programmatically — ideal for Claude/Codex agent workflows.',
    prerequisites: ['qaforge.py connected (run setup first)', 'Requirements data in JSON format or a text document'],
    steps: [
      'Use `qaforge.py submit-requirements` to batch-submit structured requirements from JSON.',
      'Use `qaforge.py extract-requirements --file BRD.txt` to extract requirements from a text file using AI.',
      'Requirements appear in your project with the source tag "agent".',
      'You can then generate test cases from these requirements using the standard workflow.',
    ],
    cli: [
      { label: 'Submit requirements from JSON', cmd: 'python scripts/qaforge.py submit-requirements <<\'EOF\'\n[\n  {"req_id": "REQ-001", "title": "Customer entity load", "priority": "high", "category": "data_load"},\n  {"req_id": "REQ-002", "title": "Count reconciliation", "priority": "high", "category": "validation"}\n]\nEOF' },
      { label: 'Extract from text file', cmd: 'python scripts/qaforge.py extract-requirements \\\n  --file ~/Desktop/BRD.txt --domain mdm' },
      { label: 'Extract with focus areas', cmd: 'python scripts/qaforge.py extract-requirements \\\n  --file ~/Desktop/BRD.txt --domain data_eng \\\n  --sub-domain snowflake --focus "data quality rules"' },
    ],
    tips: [
      'Agent-submitted requirements create a full traceability chain: Requirements → Test Cases → Executions.',
      'The extract command uses the same AI pipeline as the web UI — domain-specific extraction with deduplication.',
      'Agents (Claude, Codex) can call the REST API directly: POST /api/agent/requirements and POST /api/agent/requirements/extract.',
    ],
    related: ['connect-agent', 'upload-brd-file', 'generate-from-requirements', 'agent-workflow-brd'],
  },
  {
    id: 'chat-generate',
    title: 'Chat-Based Test Generation',
    role: 'everyone',
    category: 'test-cases',
    description: 'Have an interactive conversation with AI to generate test cases through back-and-forth dialog.',
    prerequisites: ['An active project'],
    steps: [
      'Open your project and go to the **Test Cases** tab.',
      'Click **Chat Generate** (or use the chat icon).',
      'Describe what you want to test in natural language — e.g., "I need test cases for the customer entity load from Snowflake to Reltio."',
      'The AI may ask clarifying questions about edge cases, data volumes, or specific scenarios.',
      'Continue the dialog until the AI generates test cases you are satisfied with.',
      'Click **Save** to add the generated test cases to your project with "draft" status.',
    ],
    tips: ['Be specific about your domain — mention technologies, table names, and business rules.', 'You can refine test cases in the conversation: "Make TC-3 more detailed" or "Add a negative test case."'],
    related: ['generate-from-requirements'],
  },
  {
    id: 'bulk-upload',
    title: 'Bulk Upload Test Cases from Excel',
    role: 'everyone',
    category: 'test-cases',
    description: 'Download a template, fill it with test cases, and upload in bulk.',
    prerequisites: ['An active project'],
    steps: [
      'Open your project and go to the **Test Cases** tab.',
      'Click **Upload** and then **Download Template** to get the Excel template.',
      'Fill in the template columns: test_case_id, title, description, steps, expected_result, priority (P1-P4), category, execution_type.',
      'Save the Excel file and click **Upload** → select your filled template.',
      'QAForge validates and imports all test cases. Invalid rows are reported with error details.',
      'Uploaded test cases appear with "draft" status for review.',
    ],
    tips: ['Keep test_case_id unique (e.g., TC-AUTH-001, TC-MDM-001).', 'You can upload hundreds of test cases at once.'],
    related: ['export-test-cases'],
  },
  {
    id: 'manual-test-case',
    title: 'Create Test Cases Manually',
    role: 'everyone',
    category: 'test-cases',
    description: 'Add individual test cases through the web form.',
    prerequisites: ['An active project'],
    steps: [
      'Open your project and go to the **Test Cases** tab.',
      'Click **Add Test Case**.',
      'Fill in: title, description, steps (numbered), expected result, priority (P1-P4), category (functional, integration, etc.), and execution type (api, ui, sql, manual, mdm).',
      'Click **Save**. The test case is created with "draft" status.',
      'You can edit it anytime by clicking the test case row.',
    ],
    tips: ['Use clear, action-oriented titles: "Verify customer entity load count matches source."'],
    related: ['bulk-upload'],
  },
  {
    id: 'export-test-cases',
    title: 'Export Test Cases',
    role: 'everyone',
    category: 'test-cases',
    description: 'Download test cases as Excel, Word, JSON, or CSV.',
    prerequisites: ['A project with test cases'],
    steps: [
      'Open your project and go to the **Test Cases** tab.',
      'Click **Export**.',
      'Choose the format: Excel (.xlsx), Word (.docx), JSON, or CSV.',
      'Optionally filter by status, priority, or category before exporting.',
      'Click **Download** — the file is generated and downloaded to your browser.',
    ],
    tips: ['Excel export includes all metadata: steps, expected results, actual results, and proof references.'],
  },

  /* ── Test Execution Workflows ───────────────────────────────────── */
  {
    id: 'create-test-plan',
    title: 'Create a Test Plan',
    role: 'everyone',
    category: 'execution',
    description: 'Organize test cases into SIT, UAT, Regression, or custom test plans.',
    prerequisites: ['A project with test cases'],
    steps: [
      'Open your project and click **Test Plans** in the sidebar or project tabs.',
      'Click **Create Test Plan**.',
      'Enter a name, select the plan type (SIT, UAT, Regression, Smoke, Migration, Custom), and add a description.',
      'Assign test cases to the plan — select from the project\'s test case list.',
      'The test plan dashboard shows: total cases, pass/fail counts, and completion percentage.',
      'Click into the plan to view test cases, execution results, traceability matrix, and summary.',
    ],
    tips: ['Use SIT plans for integration testing, UAT for user acceptance, and Regression for ongoing quality.'],
    related: ['submit-execution', 'review-results'],
  },
  {
    id: 'submit-execution',
    title: 'Submit Execution Results via Agent',
    role: 'engineer',
    category: 'execution',
    description: 'Run tests locally and auto-submit results (with proof artifacts) to QAForge.',
    prerequisites: ['qaforge.py connected', 'Tests written and runnable locally'],
    steps: [
      'Run your tests using one of the qaforge.py runner commands (see CLI below).',
      'qaforge.py captures: pass/fail status, duration, stdout/stderr, and (for Playwright) screenshots.',
      'Results are auto-submitted to QAForge with proof artifacts attached.',
      'Check results in the Review Queue or the project\'s Test Plans → Executions tab.',
    ],
    cli: [
      { label: 'Smoke tests', cmd: 'python scripts/qaforge.py run-smoke' },
      { label: 'pytest', cmd: 'python scripts/qaforge.py run-pytest backend/tests/' },
      { label: 'Playwright E2E', cmd: 'python scripts/qaforge.py run-playwright' },
      { label: 'Specific Playwright spec', cmd: 'python scripts/qaforge.py run-playwright --spec e2e/candidates.spec.js' },
    ],
    tips: [
      'Each run creates an "agent session" visible in the project dashboard.',
      'Proof artifacts include: api_response, test_output, screenshot, log, query_result, data_comparison.',
    ],
    related: ['review-results', 'connect-agent', 'agent-workflow-tests'],
  },
  {
    id: 'review-results',
    title: 'Review Test Results in the Review Queue',
    role: 'everyone',
    category: 'execution',
    description: 'Approve or reject test cases and execution results from a centralized review page.',
    prerequisites: ['Pending items in the Review Queue (generated test cases or submitted execution results)'],
    steps: [
      'Go to **Review Queue** from the sidebar.',
      '**Test Cases tab:** Shows all test cases with "draft" status across your projects. Click a row to expand and see the full test case details.',
      '**Executions tab:** Shows execution results awaiting review. Expand to see actual results, duration, and proof artifacts.',
      'Select items individually (checkboxes) or use **Select All**.',
      'Click **Approve Selected** to mark as reviewed/approved, or **Reject Selected** to deprecate.',
      'For executions, use **Approve All Passed** to auto-approve all items with a "passed" status.',
    ],
    tips: [
      'The Dashboard shows your total pending review count — use it as a daily starting point.',
      'Bulk operations save significant time when reviewing agent-generated test cases.',
    ],
    related: ['submit-execution', 'generate-from-requirements'],
  },

  /* ── Testing Frameworks ───────────────────────────────────────── */
  {
    id: 'frameworks-overview',
    title: 'Testing Frameworks Overview',
    role: 'everyone',
    category: 'frameworks',
    description: 'Understand how testing frameworks drive quality standards across domains — the key to reusable, consistent test coverage.',
    prerequisites: [],
    steps: [
      '**What is a Testing Framework?** A framework defines MANDATORY test areas for a domain — it\'s the quality contract that every application must satisfy.',
      '**Navigate to Frameworks** from the sidebar. You\'ll see all frameworks grouped by domain with version badges.',
      '**5 domains covered:** AI/GenAI (v2.0), Full-Stack App Building (v1.0), Data Engineering (v1.0), Integration (v1.0), MDM (v1.0).',
      '**Each framework has numbered sections** with specific test items. For example, the AI framework covers: LLM Integration, Agent Architecture, Integrity & Fraud Detection, Configuration-Driven Behavior, Security, and more.',
      '**Frameworks are versioned** — as you learn from building apps (like Orbit), you upgrade the framework (v1.0 → v2.0) to capture new patterns.',
      '**AI uses frameworks automatically** — when you call `generate_test_cases`, it fetches the relevant framework and uses it as mandatory test areas.',
    ],
    tips: [
      'Frameworks are the reusable knowledge that compound over time — each project makes the next one\'s testing better.',
      'Click any framework card to expand and see all sections and test items.',
      'Use domain filter tabs (All, AI/GenAI, Data Engineering, etc.) to focus on a specific area.',
    ],
    related: ['frameworks-create', 'frameworks-coverage', 'frameworks-mcp'],
  },
  {
    id: 'frameworks-create',
    title: 'Create & Version a Framework',
    role: 'admin',
    category: 'frameworks',
    description: 'Add a new testing framework or upgrade an existing one with lessons learned from your projects.',
    prerequisites: ['Admin role'],
    steps: [
      'Go to **Frameworks** and click **+ Add Framework**.',
      'Fill in: **Title** (e.g., "Reltio MDM Testing Framework"), **Domain** (select from dropdown), **Sub-Domain** (optional, e.g., "reltio"), **Version** (e.g., "1.0").',
      'Write the **Content** — this is the framework body. Use numbered sections with items:',
      '```\n1. ENTITY LIFECYCLE\n- Entity creation with all required attributes\n- Entity update (single and bulk)\n- Entity search (full-text, attribute-based)\n```',
      'Add **Tags** for discoverability (e.g., "mdm", "reltio", "entity-management").',
      'Click **Create Framework**. It\'s immediately available for AI test generation.',
      '**To upgrade:** Delete the old version, create a new one with bumped version (e.g., v1.0 → v2.0). Add new sections from your latest project learnings.',
    ],
    tips: [
      'Structure frameworks with numbered sections (1. AREA) and bullet items (- specific test). This format is parsed by the AI for coverage analysis.',
      'Version your frameworks semantically: v1.0 = initial, v2.0 = major learnings added, v1.1 = minor additions.',
      'A good framework has 6-10 sections with 4-8 items each — comprehensive but focused.',
    ],
    related: ['frameworks-overview', 'frameworks-coverage'],
  },
  {
    id: 'frameworks-coverage',
    title: 'Check Framework Coverage (Gap Analysis)',
    role: 'everyone',
    category: 'frameworks',
    description: 'Use the check_framework_coverage MCP tool to find which framework sections are covered by existing test cases and which have gaps.',
    prerequisites: ['QAForge MCP server connected', 'At least one framework and some test cases in the project'],
    steps: [
      '**In Claude Code**, say: "Check framework coverage for the MDM domain" or "What framework areas are we missing?"',
      'Claude calls `check_framework_coverage(domain="mdm")` which compares your test cases against the framework sections.',
      '**The report shows:** per-section coverage percentage, total items vs covered items, and a list of missing items.',
      '**Act on gaps:** Ask Claude to "Generate test cases for the missing framework areas" — it will focus on uncovered sections.',
      '**Iterate:** After generating, re-run coverage check to verify improvement.',
    ],
    cli: [
      { label: 'Check MDM coverage', cmd: '# In Claude Code:\n"Check framework coverage for MDM domain"\n\n# Claude calls: check_framework_coverage(domain="mdm")' },
      { label: 'Generate for gaps', cmd: '# In Claude Code:\n"Generate 10 test cases focusing on the missing\nframework areas for MDM"' },
    ],
    tips: [
      'Coverage analysis uses keyword matching — test case titles and descriptions are compared against framework items.',
      'A good target is 70%+ coverage across all framework sections.',
      'Run coverage checks before each release to ensure no regression in framework compliance.',
    ],
    related: ['frameworks-overview', 'frameworks-mcp'],
  },
  {
    id: 'frameworks-mcp',
    title: 'Framework-Driven Test Generation (MCP)',
    role: 'everyone',
    category: 'frameworks',
    description: 'The most powerful workflow — AI generates test cases that satisfy BOTH your project requirements AND your domain framework standards.',
    prerequisites: ['QAForge MCP server connected', 'A framework for your domain', 'Project requirements submitted'],
    steps: [
      '**The flow:** When you call `generate_test_cases(domain="ai")`, the MCP tool automatically: (1) fetches the AI/GenAI framework, (2) fetches project requirements, (3) sends both to the AI as context.',
      '**The AI sees:** "MANDATORY TESTING FRAMEWORK — Generate test cases that cover these areas: [framework content]" + "PROJECT REQUIREMENTS: [your requirements]".',
      '**Result:** Test cases that cover both your specific requirements AND the domain\'s quality standards.',
      '**Two key use cases:**',
      '**Use Case 1 — Vibe Coding:** You\'re building an app and say "Generate test cases using the AI framework" → tests cover LLM integration, security, agents, etc.',
      '**Use Case 2 — Conformance Check:** You have an existing app and say "Check if my tests cover all areas in the app building framework" → gap analysis with actionable items.',
    ],
    cli: [
      { label: 'Generate with framework', cmd: '# In Claude Code:\n"Generate 15 test cases for the AI domain using\nthe framework standards and our requirements"' },
      { label: 'Fetch framework first', cmd: '# In Claude Code:\n"Show me the AI/GenAI testing framework"\n\n# Claude calls: get_frameworks(domain="ai")' },
      { label: 'Full workflow', cmd: '# In Claude Code:\n"Fetch the app building framework, compare it\nwith our existing test cases, and generate tests\nfor any missing areas"' },
    ],
    tips: [
      'Frameworks compound over time — every project you build adds learnings that improve the next project\'s test coverage.',
      'The AI framework v2.0 was built from real Orbit learnings: agent architecture, fraud detection, config-driven behavior, input sanitization patterns.',
      'You can combine multiple frameworks: generate tests that satisfy both AI and App Building standards for a full-stack AI application.',
    ],
    related: ['frameworks-coverage', 'frameworks-overview', 'generate-from-requirements'],
  },

  /* ── Knowledge Base Workflows ───────────────────────────────────── */
  {
    id: 'seed-kb',
    title: 'Seed the Knowledge Base',
    role: 'admin',
    category: 'knowledge',
    description: 'Populate KB with reference patterns, anti-patterns, and best practices with one click.',
    prerequisites: ['Admin role'],
    steps: [
      'Go to **Knowledge Base** from the sidebar.',
      'Click **Seed Reference Data** button in the top-right.',
      'QAForge loads 30+ entries: API testing checklists, UI testing patterns, security testing patterns, CRUD lifecycle, login flows, search/filter patterns, and framework-specific anti-patterns.',
      'Entries are tagged by domain and type. They are used by the AI when generating test cases.',
      'Seeding is idempotent — running it again won\'t create duplicates.',
    ],
    tips: ['Seed the KB before generating any test cases — it significantly improves AI output quality.'],
    related: ['upload-reference', 'browse-kb'],
  },
  {
    id: 'upload-reference',
    title: 'Upload Reference Test Cases to KB',
    role: 'engineer',
    category: 'knowledge',
    description: 'Add domain-specific reference test cases from Excel so the AI learns your team\'s testing style.',
    prerequisites: ['qaforge.py connected', 'Reference Excel file with example test cases'],
    steps: [
      'Prepare an Excel file with reference test cases — these teach the AI your team\'s format, depth, and domain terminology.',
      'Run the upload command:',
      'QAForge parses the Excel, extracts test case patterns, and stores them in the Knowledge Base.',
      'Future test case generation will use these references for in-context learning.',
      'Verify with:',
    ],
    cli: [
      { label: 'Upload reference', cmd: 'python scripts/qaforge.py upload-reference \\\n  --file ~/Desktop/Sample_MDM_TC.xlsx \\\n  --domain mdm --sub-domain reltio' },
      { label: 'Check KB stats', cmd: 'python scripts/qaforge.py kb-stats --domain mdm' },
    ],
    tips: ['Upload references for each domain separately — MDM, Data Engineering, AI, etc.', 'The more examples you provide, the better the AI generates.'],
    related: ['seed-kb', 'generate-from-brd'],
  },
  {
    id: 'browse-kb',
    title: 'Browse & Search the Knowledge Base',
    role: 'everyone',
    category: 'knowledge',
    description: 'Find testing patterns, anti-patterns, and compliance rules across all domains.',
    prerequisites: [],
    steps: [
      'Go to **Knowledge Base** from the sidebar.',
      'Use the **Search** bar to find entries by keyword (e.g., "Reltio", "SQL injection", "CRUD").',
      'Filter by **domain** using the tabs: General, MDM, AI, Data Engineering, App.',
      'Each entry shows its type with a colored badge: pattern (teal), anti-pattern (orange), framework pattern (purple), compliance rule (indigo), etc.',
      'Entries with an "Auto-learned" badge were automatically saved from reference uploads.',
      'Click an entry to expand and see full content, tags, and usage count.',
    ],
    tips: ['Entries with high usage counts are frequently referenced by the AI — they are the most impactful.', 'Add your own entries to teach the AI about your specific domain.'],
    related: ['add-kb-entry'],
  },
  {
    id: 'add-kb-entry',
    title: 'Add Custom Knowledge Entries',
    role: 'everyone',
    category: 'knowledge',
    description: 'Manually add domain expertise, testing patterns, or anti-patterns to the Knowledge Base.',
    prerequisites: [],
    steps: [
      'Go to **Knowledge Base** and click **Add Entry**.',
      'Fill in: title, content (the detailed knowledge), domain, entry type, sub-domain, and tags.',
      '**Entry types:** pattern, defect, best_practice, test_case, framework_pattern, anti_pattern, compliance_rule.',
      'Click **Save**. The entry is immediately available for AI to use during test case generation.',
    ],
    tips: [
      'Use "anti_pattern" for things to avoid: "NEVER use html.escape() — causes double encoding."',
      'Use "compliance_rule" for mandatory checks: "Every route must call audit_log() for mutations."',
      'Use "framework_pattern" for architectural standards: "All DB access through database_pg.py."',
    ],
    related: ['browse-kb'],
  },

  /* ── Admin Workflows ────────────────────────────────────────────── */
  {
    id: 'manage-users',
    title: 'Manage Users',
    role: 'admin',
    category: 'admin',
    description: 'Add engineers, change roles, and deactivate accounts.',
    prerequisites: ['Admin role'],
    steps: [
      'Go to **Users** from the sidebar (admin section).',
      'Click **Add Engineer** to create a new user — enter name, email, password, and select roles (admin or engineer).',
      'To edit a user, click the pencil icon — you can change their name and role badges.',
      'To deactivate a user, click the X icon (you cannot deactivate yourself).',
      'Share the login credentials with the new user and ask them to change their password on first login.',
    ],
    tips: ['Engineers can only see projects they are assigned to. Admins see all projects.'],
    related: ['create-project'],
  },
  {
    id: 'configure-llm',
    title: 'Configure LLM Settings',
    role: 'admin',
    category: 'admin',
    description: 'Switch between AI providers and models for test case generation.',
    prerequisites: ['Admin role', 'API key for at least one provider'],
    steps: [
      'Go to **Settings** from the sidebar (admin section).',
      'You will see the current LLM provider and model.',
      'Available providers: **Anthropic** (Claude Sonnet/Haiku), **OpenAI** (GPT-4o/GPT-4o-mini), **Groq** (Llama 3.3/Mixtral), **Ollama** (local models).',
      'Select your preferred provider and model, then click **Save**.',
      'API keys are set via environment variables on the server (ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY).',
    ],
    tips: ['Groq offers the fastest generation (Llama 3.3 70B). Claude Sonnet gives the highest quality for enterprise test cases.', 'Use "mock" provider for testing without spending API credits.'],
    warnings: ['Changing the provider affects all users and all projects immediately.'],
  },
  {
    id: 'monitor-health',
    title: 'Monitor Platform Health',
    role: 'admin',
    category: 'admin',
    description: 'Use the Dashboard to monitor pending reviews, project status, and test pass rates.',
    prerequisites: ['Admin role'],
    steps: [
      'The **Dashboard** is your home page — it shows 4 key metrics:',
      '**Pending Reviews** — how many test cases and executions need human review. Click "Go to Review Queue" to process them.',
      '**Active Projects** — count of projects in "active" status.',
      '**Pass Rate** — overall pass rate across all projects.',
      '**KB Entries** — total knowledge base entries driving AI quality.',
      'Below the stats, see **My Projects** table with per-project pass rates and test case counts.',
    ],
    tips: ['Check the Dashboard daily — pending reviews should not accumulate. A healthy queue has < 20 items.'],
    related: ['review-results'],
  },
  {
    id: 'fresh-vm-deploy',
    title: 'Fresh VM Deployment — Full Stack',
    role: 'admin',
    category: 'admin',
    description: 'Deploy QAForge + MCP servers on a brand-new Ubuntu VM from scratch. Covers system prep, QAForge core, Reltio MCP, SSL, and verification. ~35 minutes total.',
    prerequisites: [
      'Ubuntu 22.04+ VM with 4 GB RAM, 20 GB disk',
      'SSH access to the VM',
      'Docker 24+ and Docker Compose v2 installed',
      'At least one LLM API key (Anthropic, OpenAI, or Groq)',
      'Reltio OAuth credentials (if deploying Reltio MCP)',
    ],
    steps: [
      '**Phase 1 — System Prep (5 min):** SSH into your VM. Install Docker and Docker Compose if not present. Create `/opt/qaforge` and `/opt/reltio-mcp-server` directories.',
      '**Phase 2 — QAForge Core (10 min):** Clone the repo to `/opt/qaforge`. Copy `.env.example` to `.env`, set `SECRET_KEY` (generate with `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`), add your LLM API key, and change `DB_PASSWORD`. Generate SSL certs. Run `docker compose up -d --build` and wait for all 6 containers to show "healthy". Run Alembic migrations.',
      '**Phase 3 — Agent Key (5 min):** Open `https://VM_IP:8080`, log in as `admin@freshgravity.com / admin123`, create a project, and generate an agent API key. Add `QAFORGE_MCP_AGENT_KEY=qf_YOUR_KEY` to `.env` and restart: `docker compose up -d qaforge_mcp`.',
      '**Phase 4 — Reltio MCP (10 min, Optional):** Clone `https://github.com/reltio-ai/reltio-mcp-server.git` to `/opt/reltio-mcp-server`. Create `.env` with Reltio credentials (single-quote the secret if it contains `$`). Change port mapping to `8002:8000`. Build and start, then run `docker network connect qaforge_default reltio_mcp_server`.',
      '**Phase 5 — Verify (5 min):** Run `bash scripts/verify-mcp.sh` from `/opt/qaforge`. It checks all containers, MCP SSE path prefixes, agent key authentication, and Docker network connectivity. All checks should pass.',
      '**Phase 6 — Security Hardening:** Change the admin password, restrict DB/Redis external ports, set `CORS_ORIGINS` to your domain, and set up SSL auto-renewal if using Let\'s Encrypt.',
    ],
    cli: [
      { label: 'Clone QAForge', cmd: 'cd /opt && git clone git@bitbucket.org:lifio/qaforge.git && cd qaforge' },
      { label: 'Configure environment', cmd: 'cp .env.example .env\n# Edit .env: set SECRET_KEY, DB_PASSWORD, LLM API key' },
      { label: 'Generate SSL certs', cmd: 'mkdir -p certs && openssl req -x509 -nodes -days 365 \\\n  -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem \\\n  -subj "/CN=qaforge.local"' },
      { label: 'Build and start', cmd: 'docker compose up -d --build' },
      { label: 'Run migrations', cmd: 'docker compose exec backend sh -c "cd /app && alembic upgrade head"' },
      { label: 'Full deploy (subsequent)', cmd: 'cd /opt/qaforge && git pull && bash scripts/full-deploy.sh' },
      { label: 'Verify MCP endpoints', cmd: 'bash scripts/verify-mcp.sh' },
    ],
    tips: [
      'For subsequent deploys, use `git pull && bash scripts/vm-deploy.sh` (QAForge only) or `bash scripts/full-deploy.sh` (full stack).',
      'The verify-mcp.sh script catches the most common issue: MCP path prefixes missing, which causes 405 errors for MCP clients.',
      'See docs/FRESH_DEPLOY.md for the complete step-by-step guide with expected outputs.',
    ],
    warnings: [
      'Change the default admin password (admin123) immediately after first login.',
      'If RELTIO_CLIENT_SECRET contains $ characters, wrap the value in single quotes in .env.',
      'After every restart of the Reltio MCP container, re-run: docker network connect qaforge_default reltio_mcp_server',
    ],
    related: ['create-project', 'mcp-qa-user-setup', 'configure-llm', 'monitor-health'],
  },

  /* ── CLI Reference ──────────────────────────────────────────────── */
  {
    id: 'cli-reference',
    title: 'qaforge.py — Full Command Reference',
    role: 'engineer',
    category: 'cli',
    description: 'Complete reference for every qaforge.py CLI command with examples.',
    prerequisites: ['Python 3.8+', 'qaforge.py in your project\'s scripts/ folder'],
    steps: [
      '**setup** — Initialize connection to QAForge (saves API URL + key to .env)',
      '**status** — Check connectivity and project status',
      '**run-smoke** — Run smoke tests and auto-submit results',
      '**run-pytest** — Run pytest and auto-submit results',
      '**run-playwright** — Run Playwright E2E tests with screenshot capture',
      '**generate-from-brd** — Generate test cases from BRD Excel with reference learning',
      '**upload-reference** — Upload reference test cases to Knowledge Base',
      '**kb-stats** — Show Knowledge Base statistics for a domain',
      '**summary** — Show project progress summary',
      '**submit-cases** — Submit test cases via JSON (stdin)',
      '**submit-results** — Submit execution results via JSON (stdin)',
      '**submit-requirements** — Submit structured requirements from JSON (stdin or file)',
      '**extract-requirements** — Extract requirements from a text file using AI',
    ],
    cli: [
      { label: 'Setup', cmd: 'python scripts/qaforge.py setup --project "Name" --token "key"' },
      { label: 'Status', cmd: 'python scripts/qaforge.py status' },
      { label: 'Run smoke tests', cmd: 'python scripts/qaforge.py run-smoke' },
      { label: 'Run pytest', cmd: 'python scripts/qaforge.py run-pytest backend/tests/' },
      { label: 'Run Playwright', cmd: 'python scripts/qaforge.py run-playwright' },
      { label: 'Run specific spec', cmd: 'python scripts/qaforge.py run-playwright --spec e2e/login.spec.js' },
      { label: 'Generate from BRD', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd file.xlsx --reference ref.xlsx \\\n  --domain mdm --sub-domain reltio --count 10' },
      { label: 'Upload reference', cmd: 'python scripts/qaforge.py upload-reference \\\n  --file sample.xlsx --domain mdm --sub-domain reltio' },
      { label: 'Submit requirements', cmd: 'python scripts/qaforge.py submit-requirements <<\'EOF\'\n[{"req_id":"REQ-001","title":"Customer load","priority":"high"}]\nEOF' },
      { label: 'Extract requirements from file', cmd: 'python scripts/qaforge.py extract-requirements \\\n  --file ~/Desktop/BRD.txt --domain mdm' },
      { label: 'KB stats', cmd: 'python scripts/qaforge.py kb-stats --domain mdm' },
      { label: 'Summary', cmd: 'python scripts/qaforge.py summary' },
    ],
    tips: [
      'All commands read QAFORGE_API_URL and QAFORGE_AGENT_KEY from .env automatically.',
      'qaforge.py auto-installs openpyxl if needed (no pip install required).',
      'Domains: mdm | ai | data_eng | integration | digital | app.',
      'Categories: functional | integration | regression | smoke | e2e | data_quality | match_rule | migration.',
      'Priorities: P1 | P2 | P3 | P4.',
    ],
    related: ['connect-agent', 'submit-execution', 'generate-from-brd', 'agent-requirements', 'upload-brd-file', 'agent-rest-api'],
  },
];

/* ───────────────────────────── sub-components ─────────────────────── */

function CodeBlock({ cmd, label }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="mb-3">
      {label && <p className="text-xs font-medium text-fg-mid mb-1">{label}</p>}
      <div className="relative group">
        <pre className="bg-gray-900 text-green-400 text-xs font-mono p-3 rounded-lg overflow-x-auto whitespace-pre-wrap leading-relaxed">
          {cmd}
        </pre>
        <button
          onClick={handleCopy}
          className="absolute top-2 right-2 text-gray-500 hover:text-green-400 text-xs font-mono opacity-0 group-hover:opacity-100 transition-opacity"
        >
          {copied ? 'copied!' : 'copy'}
        </button>
      </div>
    </div>
  );
}

function Tip({ children }) {
  return (
    <div className="flex gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-blue-800 mb-2">
      <LightBulbIcon className="w-4 h-4 flex-shrink-0 mt-0.5 text-blue-500" />
      <span>{children}</span>
    </div>
  );
}

function Warning({ children }) {
  return (
    <div className="flex gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800 mb-2">
      <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-500" />
      <span>{children}</span>
    </div>
  );
}

function ScenarioCard({ scenario, isOpen, onToggle, onNavigate }) {
  const roleBadgeClass = ROLE_BADGE[scenario.role] || ROLE_BADGE.everyone;

  return (
    <div className="border border-gray-100 rounded-xl bg-white hover:shadow-sm transition-shadow overflow-hidden">
      {/* Collapsed header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-5 py-4 text-left"
      >
        <ChevronDownIcon
          className={`w-4 h-4 text-fg-mid flex-shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-fg-dark">{scenario.title}</span>
            <span className={`badge text-xxs ${roleBadgeClass}`}>{scenario.role}</span>
          </div>
          {!isOpen && (
            <p className="text-xs text-fg-mid mt-0.5 truncate">{scenario.description}</p>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isOpen && (
        <div className="px-5 pb-5 animate-fade-in">
          <p className="text-sm text-fg-mid mb-4">{scenario.description}</p>

          {/* Prerequisites */}
          {scenario.prerequisites && scenario.prerequisites.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">Prerequisites</h4>
              <ul className="space-y-1">
                {scenario.prerequisites.map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-fg-mid">
                    <ChevronRightIcon className="w-3 h-3 mt-0.5 text-fg-teal flex-shrink-0" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Steps */}
          <div className="mb-4">
            <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">Steps</h4>
            <ol className="space-y-2">
              {scenario.steps.map((step, i) => (
                <li key={i} className="flex items-start gap-3 text-sm text-fg-dark">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-fg-teal/15 text-fg-teal text-xs font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </span>
                  <span dangerouslySetInnerHTML={{ __html: step.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
                </li>
              ))}
            </ol>
          </div>

          {/* CLI Commands */}
          {scenario.cli && scenario.cli.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">CLI Commands</h4>
              {scenario.cli.map((c, i) => (
                <CodeBlock key={i} cmd={c.cmd} label={c.label} />
              ))}
            </div>
          )}

          {/* Tips */}
          {scenario.tips && scenario.tips.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">Tips</h4>
              {scenario.tips.map((t, i) => (
                <Tip key={i}>{t}</Tip>
              ))}
            </div>
          )}

          {/* Warnings */}
          {scenario.warnings && scenario.warnings.length > 0 && (
            <div className="mb-4">
              {scenario.warnings.map((w, i) => (
                <Warning key={i}>{w}</Warning>
              ))}
            </div>
          )}

          {/* Related */}
          {scenario.related && scenario.related.length > 0 && (
            <div className="pt-3 border-t border-gray-100">
              <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">Related</h4>
              <div className="flex flex-wrap gap-2">
                {scenario.related.map((relId) => {
                  const rel = GUIDE_SCENARIOS.find((s) => s.id === relId);
                  if (!rel) return null;
                  return (
                    <button
                      key={relId}
                      onClick={() => onNavigate(relId)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-fg-teal hover:text-fg-tealDark"
                    >
                      <ArrowTopRightOnSquareIcon className="w-3 h-3" />
                      {rel.title}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ───────────────────────────── main page ──────────────────────────── */

export default function Guide() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [openIds, setOpenIds] = useState(new Set());
  const [allExpanded, setAllExpanded] = useState(false);

  const categories = Object.keys(CATEGORY_META);

  // Filter scenarios
  const filtered = useMemo(() => {
    return GUIDE_SCENARIOS.filter((s) => {
      if (roleFilter !== 'all' && s.role !== roleFilter && s.role !== 'everyone') return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          s.title.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          (s.steps && s.steps.some((st) => st.toLowerCase().includes(q))) ||
          (s.tips && s.tips.some((t) => t.toLowerCase().includes(q)))
        );
      }
      return true;
    });
  }, [search, roleFilter]);

  const toggle = (id) => {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const navigateToScenario = (id) => {
    setOpenIds((prev) => new Set(prev).add(id));
    setTimeout(() => {
      document.getElementById(`scenario-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  const toggleAll = () => {
    if (allExpanded) {
      setOpenIds(new Set());
    } else {
      setOpenIds(new Set(filtered.map((s) => s.id)));
    }
    setAllExpanded(!allExpanded);
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="section-header">
        <div>
          <div className="flex items-center gap-2">
            <QuestionMarkCircleIcon className="w-7 h-7 text-fg-teal" />
            <h1 className="text-2xl font-bold text-fg-navy">Usage Guide</h1>
          </div>
          <p className="text-sm text-fg-mid mt-1">
            {filtered.length} scenario{filtered.length !== 1 ? 's' : ''} — step-by-step walkthroughs for every workflow
          </p>
        </div>
        <button onClick={toggleAll} className="btn-secondary text-sm">
          {allExpanded ? 'Collapse All' : 'Expand All'}
        </button>
      </div>

      {/* Search + Role Tabs */}
      <div className="card-static p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search guide... (e.g. BRD, Reltio, pytest, review)"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field pl-9 text-sm"
            />
          </div>
          {/* Role filter */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {[
              { key: 'all', label: 'All' },
              { key: 'admin', label: 'Admin' },
              { key: 'engineer', label: 'Engineer' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setRoleFilter(tab.key)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  roleFilter === tab.key
                    ? 'bg-white text-fg-navy shadow-sm'
                    : 'text-fg-mid hover:text-fg-dark'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Categories + Scenarios */}
      <div className="space-y-8">
        {categories.map((catKey) => {
          const catMeta = CATEGORY_META[catKey];
          const catScenarios = filtered.filter((s) => s.category === catKey);
          if (catScenarios.length === 0) return null;

          const CatIcon = catMeta.icon;

          return (
            <div key={catKey}>
              {/* Category header */}
              <div className="card-static overflow-hidden">
                <div className={`h-1 bg-gradient-to-r ${catMeta.accent}`} />
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <CatIcon className="w-5 h-5 text-fg-teal" />
                    <h2 className="text-sm font-bold text-fg-navy uppercase tracking-wider">{catMeta.label}</h2>
                    <span className="text-xs text-fg-mid ml-auto">{catScenarios.length} scenario{catScenarios.length !== 1 ? 's' : ''}</span>
                  </div>

                  <div className="space-y-2">
                    {catScenarios.map((scenario) => (
                      <div key={scenario.id} id={`scenario-${scenario.id}`}>
                        <ScenarioCard
                          scenario={scenario}
                          isOpen={openIds.has(scenario.id)}
                          onToggle={() => toggle(scenario.id)}
                          onNavigate={navigateToScenario}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="card-static p-10 text-center">
          <QuestionMarkCircleIcon className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-fg-mid">No scenarios match your search. Try a different keyword.</p>
        </div>
      )}

      {/* Quick navigation to app sections */}
      <div className="card-static overflow-hidden mt-8">
        <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
        <div className="p-5">
          <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-3">Quick Links</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { label: 'Dashboard', path: '/' },
              { label: 'Projects', path: '/projects' },
              { label: 'Review Queue', path: '/reviews' },
              { label: 'Knowledge Base', path: '/knowledge' },
            ].map((link) => (
              <button
                key={link.path}
                onClick={() => navigate(link.path)}
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-gray-200 text-sm font-medium text-fg-dark hover:border-fg-teal hover:text-fg-teal transition-all"
              >
                {link.label}
                <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
