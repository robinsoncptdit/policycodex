## FEATURE:

Diocese Policy Review Management System - A comprehensive AI-powered SaaS application for orchestrating the review, update, and approval of all governing documents (policies, procedures, by-laws) across diocesan departments. The system implements a Seven-Gate approval workflow with AI-enhanced capabilities at each stage, leveraging Dify.ai's visual orchestration platform with MCP (Model Context Protocol) integration for multi-LLM consensus reviews and automated document processing.

Key capabilities:

- Automated policy discovery and gap analysis using AI
- Multi-LLM consensus review (Claude, GPT-4, Gemini) for policy evaluation
- Seven-Gate approval workflow with human-in-the-loop at critical stages
- SharePoint integration for centralized document management
- Real-time progress tracking and automated notifications
- AI-generated training materials and policy summaries
- Multilingual support for diverse parish needs

## EXAMPLES:

In the `examples/` folder, you'll find reference implementations demonstrating key integration patterns:

- `examples/dify_workflow_export.json` - Sample Seven-Gate workflow configuration showing how to structure complex approval chains with conditional branching
- `examples/mcp_policy_reviewer/` - MCP server implementation for policy review tools including:
    - `compliance_checker.py` - Checks policies against regulatory frameworks
    - `readability_scorer.py` - Analyzes policy clarity using multiple metrics
    - `gap_analyzer.py` - Identifies missing policy coverage areas
- `examples/sharepoint_sync/` - SharePoint integration patterns for:
    - `policy_tracker_sync.py` - Bi-directional sync with Policy Tracker spreadsheet
    - `document_discovery.py` - Automated scanning for policy documents
- `examples/multi_llm_consensus/` - Orchestration patterns for multi-model reviews:
    - `consensus_manager.py` - Manages parallel LLM calls and score aggregation
    - `prompt_templates.yaml` - Specialized prompts for each LLM's strengths
- `examples/seven_gate_automation/` - Gate-specific automation examples:
    - `gate3_committee_router.py` - Routes policies to appropriate committee members
    - `gate6_board_packet_generator.py` - Compiles board review materials

## DOCUMENTATION:

Primary Dify.ai references:

- Getting Started: https://docs.dify.ai/en/introduction
- Plugin Development: https://docs.dify.ai/plugin-dev-en/0111-getting-started-dify-plugin
- Workflow API: https://docs.dify.ai/api-reference/workflow-execution/execute-workflow
- Agent Configuration: https://docs.dify.ai/en/guides/application-orchestrate/agent
- MCP Integration: https://docs.dify.ai/en/learn-more/extended-reading/dify-docs-mcp
- Tool Development: https://docs.dify.ai/en/guides/tools

MCP Protocol references:

- MCP Specification: https://modelcontextprotocol.io/docs
- mcp-agent framework: https://github.com/lastmile-ai/mcp-agent
- MCP Server examples: https://github.com/modelcontextprotocol/servers

SharePoint Integration:

- SharePoint REST API: https://docs.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-lists-and-list-items-with-rest
- Microsoft Graph API: https://docs.microsoft.com/en-us/graph/api/resources/sharepoint

AI Model Documentation:

- Claude API: https://docs.anthropic.com/claude/reference
- OpenAI API: https://platform.openai.com/docs
- Google Gemini API: https://ai.google.dev/api/rest

## OTHER CONSIDERATIONS:

**Architecture Requirements:**

- Deploy Dify Professional tier ($59/month) for managed hosting during summer timeline
- Use Dify's visual workflow builder for Seven-Gate orchestration
- Implement custom MCP servers for diocese-specific policy tools
- Leverage Dify's built-in RAG for document analysis
- Configure multi-LLM setup through Dify's model management

**Security & Compliance:**

- All policy documents remain in diocese-controlled SharePoint
- Use Dify's role-based access control for gate-level permissions
- Implement audit logging for all policy changes and approvals
- Configure SSO integration with diocese Active Directory
- Ensure HTTPS for all API communications

**Integration Points:**

- SharePoint Online for document storage and Policy Tracker spreadsheet
- Email notifications via diocese SMTP server
- Calendar integration for synchronization meetings
- PDF generation for board packets and final policies
- Backup export to diocese file servers

**Development Considerations:**

- Start with Dify visual workflows, extend with custom plugins only where needed
- Use Dify's built-in versioning for policy document control
- Implement graceful degradation if LLM APIs are unavailable
- Design for 200 policies but architect for 500+ future growth
- Include manual override capabilities at each gate
- Build comprehensive error handling for external API failures

**User Experience:**

- Three builder accounts for IT/Policy team (Dify team members)
- Unlimited end users via published app URLs
- Mobile-responsive interface for field review
- Bulk operations for department-wide updates
- Export capabilities for offline review

**Timeline Constraints:**

- 12-week summer implementation window
- Bi-weekly synchronization meetings requiring progress dashboards
- Must support parallel department reviews
- Critical path: SharePoint integration must be completed by Week 2

**Specific Gotchas:**

- Dify's MCP support currently requires community plugins - plan for native support migration
- SharePoint API rate limits may affect initial document discovery
- LLM context windows limit policy size - implement chunking strategy
- Multi-LLM costs can escalate - implement caching and result reuse
- Workflow state persistence is critical - don't rely on session storage
- Gate 6 (Board) notifications may require special email security configuration