# AWS AIOps Skills

A collection of AI-powered operational skills for AWS infrastructure diagnosis and optimization.

These skills work with any AI coding assistant that supports structured prompts — Kiro, Claude Code, OpenClaw, Cursor, etc.

## Skills

| Skill | Description | MCP / Tool Requirements |
|-------|-------------|------------------------|
| [rds-pi-analyzer](./rds-pi-analyzer/) | Analyze RDS Performance Insights data to diagnose slow queries and bottlenecks. Supports PostgreSQL, MySQL, MariaDB with adaptive time window selection, wait event cross-analysis, and engine-specific optimization recommendations. | [aws-api-mcp-server](https://github.com/aws/aws-mcp-servers#aws-api-mcp-server)<br>[aws-documentation-mcp-server](https://github.com/aws/aws-mcp-servers#aws-documentation-mcp-server) |
| [phd-notification-verifier](./phd-notification-verifier/) | Verify AWS Personal Health Dashboard EOL events are actually resolved by querying resource state. Supports 10+ services (RDS, Lambda, SageMaker, EKS, ECS, MSK, ElastiCache, OpenSearch, EC2, ELB) with confidence scoring and evidence-based conclusions. | [aws-api-mcp-server](https://github.com/aws/aws-mcp-servers#aws-api-mcp-server)<br>[aws-documentation-mcp-server](https://github.com/aws/aws-mcp-servers#aws-documentation-mcp-server) |
| [rightsizing-advisor](./rightsizing-advisor/) | Scan all database instances in a target account, analyze CloudWatch utilization patterns (peak/off-peak, weekday/weekend), quantify idle waste, and recommend optimization actions (downsize, Graviton migration, Aurora Serverless v2, Reserved Instances, gp3 storage). Currently supports RDS. | [aws-api-mcp-server](https://github.com/aws/aws-mcp-servers#aws-api-mcp-server)<br>[aws-documentation-mcp-server](https://github.com/aws/aws-mcp-servers#aws-documentation-mcp-server)<br>Python 3.10+ (local) |

## What are Skills?

Skills are structured markdown prompts that guide AI assistants through complex operational workflows. Each skill includes:

- `SKILL.md` — Step-by-step workflow definition
- `config.example.yaml` — Example configuration (copy to `config.yaml` for your environment)
- `README.md` — Usage documentation
- `references/` — Detailed reference docs loaded on demand to save context
- `scripts/` — Helper scripts for data-intensive tasks (e.g., metric collection)

## Quick Start

### 1. Clone this repo

```bash
git clone https://github.com/mengchen-tam/aws-aiops-skills.git ~/aws-aiops-skills
```

### 2. Configure

Each skill requires configuration. Copy the example config and customize:

```bash
# For RDS PI Analyzer
cd ~/aws-aiops-skills/rds-pi-analyzer
cp config.example.yaml config.yaml
# Edit config.yaml with your account/region details

# For PHD Verifier
cd ~/aws-aiops-skills/phd-notification-verifier
cp config.example.yaml config.yaml
# Edit config.yaml with cross-account role ARNs

# For Rightsizing Advisor
cd ~/aws-aiops-skills/rightsizing-advisor
cp config.example.yaml config.yaml
# Edit config.yaml with cross-account role ARNs
# Also set up Python environment for metric collection:
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
```

### 3. Set up for your AI assistant

#### Kiro IDE

Symlink into Kiro's skills directory:
```bash
ln -s ~/aws-aiops-skills/rds-pi-analyzer ~/.kiro/skills/rds-pi-analyzer
ln -s ~/aws-aiops-skills/phd-notification-verifier ~/.kiro/skills/phd-notification-verifier
ln -s ~/aws-aiops-skills/rightsizing-advisor ~/.kiro/skills/rightsizing-advisor
```
Then reference the skill in Kiro chat.

#### Claude Code

Add to your `.claude/commands/` directory:
```bash
mkdir -p .claude/commands
ln -s ~/aws-aiops-skills/rds-pi-analyzer/SKILL.md .claude/commands/rds-pi-analyzer.md
ln -s ~/aws-aiops-skills/phd-notification-verifier/SKILL.md .claude/commands/phd-verifier.md
ln -s ~/aws-aiops-skills/rightsizing-advisor/SKILL.md .claude/commands/rightsizing-advisor.md
```
Then use slash commands in Claude Code.

#### Other AI Assistants (Cursor, Windsurf, etc.)

The SKILL.md files are plain markdown. You can:
- Copy the content into your assistant's context/rules
- Reference the file path in your prompt
- Use it as a system prompt or custom instruction

## Architecture

![Architecture](architecture.html)

Open `architecture.html` in a browser to view the system architecture diagram.

### Example Workflow: Rightsizing Analysis

```
User: "帮我分析账号 A 的 RDS rightsizing"
  │
  ├─ Step 1: LLM calls call_aws → describe-db-instances (via MCP → ECS → Account A)
  │           Returns instance list, LLM presents to user for confirmation
  │
  ├─ Step 2: LLM runs collect_rds_metrics.py via execute_bash
  │           Script → MCP SDK → ECS → CloudWatch (Account A)
  │           Aggregates 50,000+ datapoints → 3KB JSON per instance
  │
  ├─ Step 3-5: LLM reads RDS.md → interprets metrics → generates recommendations
  │
  ├─ Step 6: LLM generates markdown report with evidence
  │
  └─ Step 7: LLM queries aws-doc-mcp → includes reference links
```

## Contributing

To add a new skill:

1. Create a new directory: `<skill-name>/`
2. Add `SKILL.md` (workflow definition), `config.example.yaml` (example config)
3. Optional: Add `references/` for detailed docs, `scripts/` for helper scripts
4. Update this README's skill table
5. Ensure no sensitive data (account IDs, keys) in committed files (use `.gitignore`)

See existing skills for structure examples.

## License

MIT
