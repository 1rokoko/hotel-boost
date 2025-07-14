# Hotel Boost - Task Management Setup Guide

## Overview
This project is now configured with claude-task-master and notification-mcp for enhanced AI-powered development workflow.

## MCP Servers Configured

### 1. Claude Task Master (`taskmaster-ai`)
- **Purpose**: AI-powered task management and project planning
- **Location**: Configured in `C:\Users\Аркадий\.cursor\mcp.json`
- **Features**:
  - Parse PRD documents into actionable tasks
  - Generate project plans and task breakdowns
  - Track progress and manage workflows
  - Research capabilities for technical decisions

### 2. Notification MCP (`notifications`)
- **Purpose**: Audio notifications for task completion
- **Sound**: Gentle chime (configurable)
- **Features**:
  - Play notification sounds when tasks are completed
  - Customizable sound selection
  - Cross-platform audio support

## Project Structure

```
hotel-boost/
├── .taskmaster/
│   ├── config.json          # Project configuration
│   ├── docs/
│   │   └── prd.txt          # Product Requirements Document
│   ├── tasks.json           # Task tracking
│   └── templates/
│       └── usage_guide.md   # This guide
├── node_modules/            # Dependencies (task-master-ai installed)
└── package.json             # Package configuration
```

## How to Use

### 1. Working with PRD
- Edit `.taskmaster/docs/prd.txt` with your project requirements
- Use AI assistant to parse PRD: "Can you parse my PRD and generate tasks?"

### 2. Task Management Commands
- "What's the next task I should work on?"
- "Can you help me implement task [number]?"
- "Show me tasks 1, 3, and 5"
- "Can you expand task 4 with more details?"

### 3. Research Commands
- "Research the latest best practices for [technology]"
- "Research [specific topic] for our current implementation"

### 4. Notifications
- Notifications will automatically play when tasks are completed
- Sound can be changed by modifying `MCP_NOTIFICATION_SOUND` in mcp.json
- Available sounds: cosmic, fairy, gentle, pleasant, retro, random

## Configuration Files

### .taskmaster/config.json
Contains project settings, model preferences, and paths.

### MCP Configuration
Located at: `C:\Users\Аркадий\.cursor\mcp.json`
- Both servers are configured and ready to use
- Anthropic API key is already set up
- Notification sound set to "gentle"

## Getting Started
1. Write your project requirements in `.taskmaster/docs/prd.txt`
2. Ask the AI assistant to parse your PRD and generate tasks
3. Follow the generated task plan
4. Use notifications to track completion progress

## Troubleshooting
- If MCP servers don't respond, restart Cursor
- Check that Node.js and npm are available
- Verify API keys are correctly set in mcp.json
- For notification issues, ensure audio is enabled on your system

## Next Steps
- Fill out the PRD with your specific requirements
- Generate initial task breakdown
- Begin development following the structured approach
