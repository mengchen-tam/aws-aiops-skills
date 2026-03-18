# AWS AIOps Skills

A collection of AI-powered operational skills for AWS infrastructure diagnosis and optimization.

These skills work with any AI coding assistant that supports structured prompts — Kiro, Claude Code, OpenClaw, Cursor, etc.

## Skills

| Skill | Description | MCP / Tool Requirements | Status |
|-------|-------------|------------------------|--------|
| [rds-pi-analyzer](./rds-pi-analyzer/) | Analyze RDS Performance Insights data to diagnose slow queries and bottlenecks. Supports PostgreSQL, MySQL, MariaDB with adaptive time window selection, wait event cross-analysis, and engine-specific optimization recommendations. | [aws-api-mcp-server](https://github.com/aws/aws-mcp-servers#aws-api-mcp-server)<br>[aws-documentation-mcp-server](https://github.com/aws/aws-mcp-servers#aws-documentation-mcp-server) | ✅ Production |
| [phd-notification-verifier](./phd-notification-verifier/) | Verify AWS Personal Health Dashboard EOL events are actually resolved by querying resource state. Supports 10+ services (RDS, Lambda, SageMaker, EKS, ECS, MSK, ElastiCache, OpenSearch, EC2, ELB) with confidence scoring and evidence-based conclusions. | [aws-api-mcp-server](https://github.com/aws/aws-mcp-servers#aws-api-mcp-server) | ✅ Production |

## What are Skills?

Skills are structured markdown prompts that guide AI assistants through complex operational workflows. Each skill includes:

- `skill.md` — Step-by-step workflow definition
- `config.example.yaml` — Example configuration (copy to `config.yaml` for your environment)
- `README.md` — Usage documentation

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
```

### 3. Set up for your AI assistant

#### Kiro IDE

Symlink into Kiro's skills directory:
```bash
ln -s ~/aws-aiops-skills/rds-pi-analyzer ~/.kiro/skills/rds-pi-analyzer
ln -s ~/aws-aiops-skills/phd-notification-verifier ~/.kiro/skills/phd-notification-verifier
```
Then reference the skill in Kiro chat.

#### Claude Code

Add to your `.claude/commands/` directory:
```bash
mkdir -p .claude/commands
ln -s ~/aws-aiops-skills/rds-pi-analyzer/SKILL.md .claude/commands/rds-pi-analyzer.md
ln -s ~/aws-aiops-skills/phd-notification-verifier/SKILL.md .claude/commands/phd-verifier.md
```
Then use `/rds-pi-analyzer` or `/phd-verifier` slash commands in Claude Code.

#### OpenClaw

Place in your OpenClaw skills directory:
```bash
ln -s ~/aws-aiops-skills/rds-pi-analyzer ~/.openclaw/skills/rds-pi-analyzer
ln -s ~/aws-aiops-skills/phd-notification-verifier ~/.openclaw/skills/phd-notification-verifier
```
OpenClaw will auto-detect the SKILL.md and make it available.

#### Other AI Assistants (Cursor, Windsurf, etc.)

The SKILL.md files are plain markdown. You can:
- Copy the content into your assistant's context/rules
- Reference the file path in your prompt
- Use it as a system prompt or custom instruction

Example for Cursor:
```bash
# Add to .cursor/rules/
cp ~/aws-aiops-skills/rds-pi-analyzer/SKILL.md .cursor/rules/rds-pi-analyzer.md
cp ~/aws-aiops-skills/phd-notification-verifier/SKILL.md .cursor/rules/phd-verifier.md
```

## Contributing

To add a new skill:

1. Create a new directory: `<skill-name>/`
2. Add `SKILL.md` (workflow definition), `README.md` (usage docs), and `config.example.yaml` (example config)
3. Optional: Add `references/` directory for detailed documentation
4. Update this README's skill table
5. Ensure no sensitive data (account IDs, keys) in committed files (use `.gitignore`)

See existing skills for structure examples.

## License

MIT
