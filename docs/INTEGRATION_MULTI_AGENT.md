# Integration: Multi-Agent System with Existing GigaBoard Architecture

## Overview

This document describes how the **Multi-Agent System** with **Dynamic Tool Development** integrates with the existing GigaBoard architecture, enhancing the AI Assistant Panel from a single-agent system to a sophisticated multi-agent orchestration platform.

---

## Architecture Integration Map

### Before (Single AI Agent)
```mermaid
flowchart TB
  U[User Query] --> UI[AI Assistant Panel (UI)]
  UI --> S[AIAssistantService (Single Agent)]
  S --> G[Query GigaChat]
  S --> C[Get context from board]
  S --> W[Suggest widget]
  W --> WC[Widget Creation]
```

### After (Multi-Agent System)
```mermaid
flowchart TB
  U[User Query] --> UI[AI Assistant Panel (UI)]
  UI --> O[Multi-Agent Orchestrator]
  subgraph O
    P[Planner Agent (task routing)]
    MB[Message Bus (Redis pub/sub)]
    subgraph SA[Specialized Agents]
      R[Researcher (fetch data)]
      A1[Analyst (analyze)]
      D[Developer (write tools)]
      E[Executor (run tools)]
      RPT[Reporter (visualize)]
    end
    TR[Tool Registry]
  end
  O --> W[Widget Creation]
```
- Code Sandbox
- Tool Execution Environment
- Multiple Widgets Creation
- Visualization Board Update

---

## Component Mapping

### 1. Frontend Integration (No Breaking Changes)

**UI Component**: `AIAssistantPanel.tsx` remains the same
- Same message input/output format
- Same suggested actions mechanism
- New: Show agent thinking process
- New: Display tool generation progress

**New capabilities**:
```typescript
// New message types
interface AgentMessage {
  type: 'user_query' | 'agent_thinking' | 'tool_generation' | 'execution' | 'result'
  agent?: string
  content: string
  metadata?: {
    tool_name?: string
    status?: 'pending' | 'success' | 'error'
    execution_time?: number
  }
}

// UI shows:
- "🤔 Planner thinking about your request..."
- "💻 Developer writing web scraper tool..."
- "⚡ Executor running tool (2.3s elapsed)..."
- "✅ Analysis complete. Found 3 insights."
```

**Real-time Updates**: Use existing WebSocket connection
```typescript
// Existing Socket.IO connection enhanced with agent events
socket.on('agent_thinking', (message) => { /* show thinking */ })
socket.on('tool_generated', (tool) => { /* log tool creation */ })
socket.on('tool_executed', (result) => { /* show results */ })
socket.on('widget_created', (widget) => { /* add to board */ })
```

---

### 2. Backend API Integration

**Existing Endpoints**: Remain unchanged
- All CRUD endpoints work as before
- Authentication/authorization unchanged
- Real-time events unchanged

**New Endpoints** (added to FastAPI):
```python
# All under /api/v1

# Agent management
GET    /agents
POST   /agents
GET    /agents/{agentId}
PATCH  /agents/{agentId}/config

# Tool management  
GET    /tools
GET    /tools/{toolId}
POST   /tools/{toolId}/test
GET    /tools/{toolId}/history

# Agent execution
POST   /boards/{boardId}/agents/execute
GET    /boards/{boardId}/agents/executions/{executionId}
WebSocket: /ws/agents/{boardId}/{sessionId}

# Existing AI endpoints enhanced
POST   /boards/{boardId}/ai/chat  # Enhanced to use multi-agent system
```

---

### 3. Service Layer Integration

**Existing Layer** (AIAssistantService):
```python
# OLD: Single service handles everything
class AIAssistantService:
    async def process_message(self, message: str, board_context: Dict):
        # Direct GigaChat call
        # Suggest widget
        # Done
```

**New Architecture**:
```python
# NEW: Thin wrapper delegates to orchestration
class AIAssistantService:
    def __init__(self, orchestrator: MultiAgentOrchestrator):
        self.orchestrator = orchestrator
    
    async def process_message(self, message: str, board_context: Dict):
        # Delegate to orchestrator
        execution = await self.orchestrator.execute(
            request=message,
            agents=['planner', 'analyst', 'developer'],  # Auto-selected
            board_context=board_context
        )
        
        # Return results same format
        return {
            'response': execution.results['summary'],
            'suggested_actions': execution.results['widgets'],
            'execution_id': execution.execution_id
        }
```

**New Layer** (MultiAgentOrchestrator):
```python
class MultiAgentOrchestrator:
    def __init__(self, 
                 tool_registry: ToolRegistry,
                 sandbox_manager: SandboxManager,
                 message_bus: MessageBus):
        self.agents = {
            'planner': PlannerAgent(),
            'researcher': ResearcherAgent(),
            'analyst': AnalystAgent(),
            'developer': DeveloperAgent(),
            'executor': ExecutorAgent(),
            'reporter': ReporterAgent(),
        }
        self.tool_registry = tool_registry
        self.sandbox_manager = sandbox_manager
        self.message_bus = message_bus
    
    async def execute(self, request: str, agents: List[str], 
                      board_context: Dict) -> ExecutionResult:
        # Orchestrate multi-agent workflow
        pass
```

---

### 4. Database Integration (Minimal Schema Changes)

**Existing Tables**: Remain unchanged
- `boards`, `widgets`, `edges`, `users`, `sessions` - all same

**New Tables**:
```sql
-- Tool Registry
CREATE TABLE tools (
    id UUID PRIMARY KEY,
    name VARCHAR,
    version INT,
    code TEXT,
    language VARCHAR,  -- 'python', 'sql', 'javascript'
    created_by_agent VARCHAR,
    created_at TIMESTAMP,
    quality_score FLOAT,
    usage_count INT,
    success_rate FLOAT,
    avg_execution_time FLOAT
);

-- Tool Execution History
CREATE TABLE tool_executions (
    id UUID PRIMARY KEY,
    tool_id UUID REFERENCES tools(id),
    execution_id UUID,
    user_id UUID,
    params JSONB,
    result JSONB,
    status VARCHAR,  -- 'success', 'error', 'timeout'
    execution_time_ms INT,
    memory_used_mb INT,
    error_message TEXT,
    created_at TIMESTAMP
);

-- Agent Executions (for audit trail)
CREATE TABLE agent_executions (
    id UUID PRIMARY KEY,
    board_id UUID REFERENCES boards(id),
    user_request TEXT,
    agents_involved TEXT[],  -- array of agent names
    status VARCHAR,
    results JSONB,
    widgets_created UUID[],  -- IDs of widgets created
    tools_created UUID[],    -- IDs of tools created
    start_time TIMESTAMP,
    end_time TIMESTAMP
);

-- Chat History (enhanced)
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY,
    board_id UUID REFERENCES boards(id),
    session_id UUID,
    role VARCHAR,  -- 'user', 'assistant', 'system'
    agent VARCHAR,  -- which agent sent message
    content TEXT,
    metadata JSONB,  -- agent_thinking, tool_info, etc.
    created_at TIMESTAMP
);
```

**No migration needed**: New tables are additive, existing queries work unchanged.

---

### 5. Real-time Integration (Redis Enhancement)

**Existing Pub/Sub Channels**:
```
gigaboard:board:{boardId}:changes    # widget updates
gigaboard:board:{boardId}:users      # user presence
```

**New Channels**:
```
gigaboard:board:{boardId}:agents     # agent activity
gigaboard:agents:message_bus         # inter-agent communication
gigaboard:tools:registry_update      # tool registration
```

**Message Flow**:
```
User → FastAPI → AIAssistantService → MultiAgentOrchestrator
                                         ↓
                                    Planner Agent
                                         ↓
                    Publish to Redis: "gigaboard:board:123:agents"
                         ↓
                    Researcher Agent (subscribed)
                         ↓
                    Fetch data, publish result
                         ↓
                    Analyst Agent (subscribed)
                         ↓
                    ... chain continues
                         ↓
                    Reporter Agent publishes final widgets
                         ↓
                    FastAPI Socket.IO broadcasts to UI
```

---

### 6. Deployment Considerations

**No additional services required initially**:
- FastAPI already running → Add agent code as new modules
- Redis already running → Use additional channels
- PostgreSQL already running → Add new tables with migration
- Docker optional → Can start with local .venv

**Scaling Strategy**:
Single Server (Phase 1):
- FastAPI service
  - FastAPI for REST/Socket.IO (existing)
  - MultiAgentOrchestrator (new module)
  - Agent runners (new module)
  - Tool sandbox (new module)

Microservices (Phase 2):
- FastAPI: REST/Socket.IO (existing)
- AgentService: Multi-agent orchestration (new)
- SandboxService: Tool execution (new, auto-scaling)
- ToolRegistry: Tool persistence (new, cache layer)
- Redis: Shared bus

---

## Feature Roadmap

### Phase 1: Single AI Agent (CURRENT - MVP)
**Status**: ✅ Documented, ready for implementation
- AI Assistant Panel in sidebar
- Context-aware responses
- Suggested widget creation

### Phase 2: Multi-Agent System (NEXT)
**Effort**: ~4-6 weeks development
- Deploy 6 agent types
- Inter-agent communication
- Message bus infrastructure
- Agent persistence/logging
**Deliverable**: FR-7 complete

### Phase 3: Dynamic Tool Development (AFTER Phase 2)
**Effort**: ~3-4 weeks development
- Code generation pipeline
- Security validation system
- Sandbox environment
- Tool registry with versioning
**Deliverable**: FR-8 complete

### Phase 4: Advanced Workflows (FUTURE)
**Ideas**:
- Scheduled agent executions
- Multi-user agent collaboration
- Custom agent creation by users
- Agent learning from feedback
- Tool marketplace
- Cost tracking and optimization

---

## Risk Mitigation

### Security Risks

**Risk**: Arbitrary code execution from LLM
**Mitigation**:
- Code validation before execution (forbidden operations)
- Sandbox with resource limits
- Audit trail of all executions
- Whitelist of allowed libraries

**Risk**: Data exposure through tool execution
**Mitigation**:
- Validate connection strings before use
- Encrypt sensitive params
- Rate limiting per user
- Execution logging for compliance

### Performance Risks

**Risk**: Slow agent orchestration delays UI
**Mitigation**:
- Async agent execution
- Real-time progress updates to UI
- Timeout on agent tasks
- Caching of tool results

**Risk**: Tool sandbox becomes bottleneck
**Mitigation**:
- Auto-scaling sandbox containers
- Result caching
- Tool optimization recommendations
- Performance monitoring

### Reliability Risks

**Risk**: Agent failure breaks request processing
**Mitigation**:
- Fallback to direct GigaChat for simple queries
- Agent health checks
- Automatic restart on failure
- Error logging and alerting

---

## Migration Strategy (from Single to Multi-Agent)

### Step 1: Deploy Infrastructure
1. Create new database tables (non-breaking)
2. Add Redis channels (non-breaking)
3. Add new API endpoints (non-breaking)

### Step 2: Implement Agent Framework
1. Write base Agent class
2. Implement Planner agent (router)
3. Test agent communication

### Step 3: Deploy Agents (One at a time)
1. Researcher Agent (data fetching)
2. Executor Agent (tool running)
3. Developer Agent (tool generation)
4. Analyst Agent (analysis)
5. Reporter Agent (visualization)

### Step 4: Redirect Traffic
1. Update AIAssistantService to use orchestrator
2. Run A/B testing (10% → 50% → 100% traffic)
3. Monitor metrics and errors
4. Rollback plan ready

### Rollback Plan
- If issues detected, switch back to single agent (AIAssistantService)
- All new tables remain (for data collection)
- No data loss

---

## Testing Strategy

### Unit Tests
- Each agent independently
- Tool validation/security
- Sandbox execution limits

### Integration Tests
- Multi-agent workflows
- Message bus communication
- Database persistence
- Sandbox integration

### End-to-End Tests
- User query → widget creation
- Tool generation → execution
- Error handling and fallbacks

### Load Tests
- 100 concurrent agent executions
- Tool sandbox under load
- Message bus throughput

---

## Success Metrics

### Performance
- Agent execution < 5 minutes (P95)
- Tool generation < 30 seconds (P95)
- Message latency < 500ms (P95)

### Reliability
- Agent success rate > 95%
- Tool execution success > 95%
- Sandbox availability > 99.5%

### User Experience
- AI correctly understands 90% of requests
- Generated tools work on first try > 85%
- Users find insights in < 2 minutes

### System Health
- Message bus latency < 100ms
- No tool execution timeouts
- No memory leaks in sandbox

---

## Documentation Artifacts

All integration details documented in:
- [MULTI_AGENT_SYSTEM.md](./MULTI_AGENT_SYSTEM.md) - Architecture & agents
- [DYNAMIC_TOOL_SYSTEM.md](./DYNAMIC_TOOL_SYSTEM.md) - Tool generation & sandbox
- [MULTI_AGENT_USE_CASES.md](./MULTI_AGENT_USE_CASES.md) - Real-world examples
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Updated system architecture
- [API.md](./API.md) - Updated API endpoints
- [SPECIFICATIONS.md](./SPECIFICATIONS.md) - FR-7 & FR-8 requirements

---

**Status**: Integration Plan Complete
**Ready for**: Phase 1 implementation & Phase 2 planning
**Next Step**: Begin backend development on Multi-Agent infrastructure
