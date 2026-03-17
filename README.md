# AWS AIOps Skills

A collection of AI-powered operational skills for AWS infrastructure diagnosis and optimization.

These skills work with any AI coding assistant that supports structured prompts — Kiro, Claude Code, OpenClaw, Cursor, etc.

## Skills

| Skill | Description | Supported Engines |
|-------|-------------|-------------------|
| [rds-pi-analyzer](./rds-pi-analyzer/) | Analyze RDS Performance Insights data to diagnose slow queries and bottlenecks | PostgreSQL, MySQL, MariaDB |

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

```bash
cd ~/aws-aiops-skills/rds-pi-analyzer
cp config.example.yaml config.yaml
# Edit config.yaml with your account details
```

### 3. Set up for your AI assistant

#### Kiro IDE

Symlink into Kiro's skills directory:
```bash
ln -s ~/aws-aiops-skills/rds-pi-analyzer ~/.kiro/skills/rds-pi-analyzer
```
Then reference the skill in Kiro chat.

#### Claude Code

Add to your `.claude/commands/` directory:
```bash
mkdir -p .claude/commands
ln -s ~/aws-aiops-skills/rds-pi-analyzer/skill.md .claude/commands/rds-pi-analyzer.md
```
Then use `/rds-pi-analyzer` slash command in Claude Code.

#### OpenClaw

Place in your OpenClaw skills directory:
```bash
ln -s ~/aws-aiops-skills/rds-pi-analyzer ~/.openclaw/skills/rds-pi-analyzer
```
OpenClaw will auto-detect the `skill.md` and make it available.

#### Other AI Assistants (Cursor, Windsurf, etc.)

The `skill.md` files are plain markdown. You can:
- Copy the content into your assistant's context/rules
- Reference the file path in your prompt
- Use it as a system prompt or custom instruction

## Contributing

To add a new skill:

1. Create a new directory: `<skill-name>/`
2. Add `skill.md`, `README.md`, and `config.example.yaml`
3. Update this README's skill table
4. Ensure no sensitive data (account IDs, keys) in committed files

## License

MIT
