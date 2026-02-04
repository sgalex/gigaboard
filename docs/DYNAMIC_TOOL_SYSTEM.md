# Dynamic Tool Development System for GigaBoard

## Overview

The **Dynamic Tool Development System** enables AI agents to:
- Write tool code on-demand based on user requirements
- Test tools in a secure sandbox
- Persist and version tools for reuse
- Execute tools with resource monitoring
- Handle errors and optimize performance

This system is the core capability that transforms GigaBoard from a "passive analytics tool" to an "active problem-solving platform."

---

## Architecture

### Tool Lifecycle

```
1. REQUEST
   User/Agent asks for a tool to solve a problem
        ↓
2. ANALYSIS
   Developer Agent analyzes requirements
        ↓
3. CODE GENERATION
   Developer Agent writes code
        ↓
4. VALIDATION
   Security checks, syntax validation
        ↓
5. SANDBOX TEST
   Run code in isolated environment
        ↓
6. REGISTRATION
   Add to tool registry
        ↓
7. EXECUTION
   Other agents can use the tool
        ↓
8. MONITORING
   Track execution, errors, performance
        ↓
9. VERSIONING
   Store versions, track changes
        ↓
10. OPTIMIZATION
    Improve based on usage patterns
```

---

## Code Generation Pipeline

### Step 1: Requirements Parsing

```python
class ToolRequirement:
    """Parsed tool requirement"""
    
    title: str                  # "Fetch Shopify Sales Data"
    description: str            # What the tool should do
    inputs: Dict[str, ParamType]
    outputs: Dict[str, ParamType]
    data_sources: List[str]     # DB, API, website, etc.
    performance_constraints: Dict  # timeout, memory, etc.
    error_cases: List[str]      # Expected error scenarios
    
    # Generated from user request via NLP
```

### Step 2: Code Template Selection

Developer Agent selects appropriate template:

```python
class CodeTemplate:
    """Base template for tool generation"""
    
    language: str               # "python", "sql", "javascript", "shell"
    category: str               # "api_call", "db_query", "web_scrape", etc.
    example: str                # Example implementation
    common_libraries: List[str]
    error_patterns: List[str]
    
    @staticmethod
    def get_template(category: str, language: str) -> str:
        """Get appropriate template"""
        pass

# Template Examples

PYTHON_API_TEMPLATE = """
import requests
import json
from typing import Dict, List

def fetch_from_api(
    url: str,
    params: Dict = None,
    headers: Dict = None,
    auth_token: str = None
) -> List[Dict]:
    '''
    Fetch data from API endpoint.
    
    Args:
        url: API endpoint
        params: Query parameters
        headers: HTTP headers
        auth_token: Authentication token
    
    Returns:
        List of records
    '''
    
    try:
        # Add auth header if provided
        if auth_token:
            headers = headers or {}
            headers['Authorization'] = f'Bearer {auth_token}'
        
        # Make request
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        
        # Handle pagination if needed
        all_data = data if isinstance(data, list) else [data]
        
        return all_data
        
    except requests.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")
"""

SQL_QUERY_TEMPLATE = """
SELECT * FROM {table_name}
WHERE {conditions}
ORDER BY {order_by}
LIMIT {limit}
"""

WEB_SCRAPE_PYTHON_TEMPLATE = """
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

def scrape_website(
    url: str,
    selectors: Dict[str, str],
    pagination: bool = False
) -> List[Dict]:
    '''
    Scrape data from website.
    
    Args:
        url: Website URL
        selectors: CSS selectors for data extraction
        pagination: Handle multiple pages
    
    Returns:
        List of extracted records
    '''
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        records = []
        for item in soup.select(selectors.get('container', '')):
            record = {}
            for key, selector in selectors.items():
                if key != 'container':
                    element = item.select_one(selector)
                    record[key] = element.get_text(strip=True) if element else None
            records.append(record)
        
        return records
        
    except Exception as e:
        raise Exception(f"Scraping failed: {str(e)}")
"""
```

### Step 3: AI-Generated Code

```python
class CodeGenerator:
    """Generate tool code using LLM"""
    
    async def generate_code(
        self,
        requirement: ToolRequirement,
        template: str,
        language: str
    ) -> str:
        """
        Use LLM to generate specific code from template
        """
        
        prompt = f"""
        You are an expert {language} developer.
        
        Create a {language} function that:
        - {requirement.description}
        - Accepts parameters: {requirement.inputs}
        - Returns: {requirement.outputs}
        - Handles errors gracefully
        - Includes docstring and type hints
        - Follows best practices
        
        Template to follow:
        {template}
        
        Generated function:
        """
        
        # Call LLM (GigaChat)
        code = await self.llm_client.generate(prompt)
        
        return code

# Example Generated Code:

GENERATED_SHOPIFY_API_TOOL = """
import requests
import json
from typing import Dict, List
from datetime import datetime, timedelta

def fetch_shopify_sales(
    shop_url: str,
    access_token: str,
    days_back: int = 30,
    limit: int = 250
) -> List[Dict]:
    '''
    Fetch sales orders from Shopify store.
    
    Args:
        shop_url: Shopify shop URL (e.g., myshop.myshopify.com)
        access_token: Shopify API access token
        days_back: Number of days to look back
        limit: Max records per request
    
    Returns:
        List of order dictionaries with sales data
    '''
    
    try:
        # Calculate date range
        since_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        # Construct API URL
        api_url = f"https://{shop_url}/admin/api/2024-01/orders.json"
        
        headers = {
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        }
        
        params = {
            'status': 'any',
            'created_at_min': since_date,
            'limit': limit,
            'fields': 'id,created_at,total_price,currency,customer,line_items'
        }
        
        all_orders = []
        
        # Handle pagination
        while api_url:
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            all_orders.extend(data.get('orders', []))
            
            # Check for next page
            link_header = response.headers.get('Link', '')
            api_url = None
            if 'rel="next"' in link_header:
                # Extract next URL from Link header
                for link in link_header.split(','):
                    if 'rel="next"' in link:
                        api_url = link.split(';')[0].strip('<>')
            
            params = {}  # Clear params after first request
        
        return all_orders
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch from Shopify: {str(e)}")
    except KeyError as e:
        raise Exception(f"Unexpected response format: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")
"""
```

---

## Code Validation

### Security Validation

```python
class CodeSecurityValidator:
    """Validate code safety before execution"""
    
    FORBIDDEN_OPERATIONS = {
        'python': {
            'file_system': [
                r'open\s*\(',
                r'os\.remove',
                r'os\.rmdir',
                r'shutil\.rmtree',
            ],
            'system_access': [
                r'os\.system',
                r'subprocess\.',
                r'__import__',
                r'eval\s*\(',
                r'exec\s*\(',
            ],
            'unauthorized_modules': [
                r'import\s+socket',
                r'import\s+pickle',
            ]
        },
        'shell': {
            'destructive': [
                r'rm\s+-rf',
                r'dd\s+if',
                r'format\s+[CD]',
            ],
            'dangerous': [
                r'chmod\s+777',
                r'chown',
            ]
        }
    }
    
    ALLOWED_LIBRARIES = {
        'python': [
            'requests', 'beautifulsoup4', 'lxml', 'selenium',
            'pandas', 'numpy', 'scipy',
            'psycopg2', 'pymongo', 'redis',
            'sqlalchemy', 'asyncio', 'json', 'csv',
            'datetime', 're', 'urllib',
        ]
    }
    
    async def validate(self, code: str, language: str) -> ValidationResult:
        """
        Comprehensive code validation
        """
        
        issues = []
        
        # 1. Check for forbidden operations
        forbidden = self.FORBIDDEN_OPERATIONS.get(language, {})
        for category, patterns in forbidden.items():
            for pattern in patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    issues.append({
                        'severity': 'CRITICAL',
                        'category': category,
                        'message': f'Forbidden operation detected: {category}'
                    })
        
        # 2. Check for disallowed imports
        imports = self._extract_imports(code, language)
        allowed = self.ALLOWED_LIBRARIES.get(language, [])
        for imp in imports:
            if imp not in allowed:
                issues.append({
                    'severity': 'HIGH',
                    'message': f'Disallowed import: {imp}'
                })
        
        # 3. Syntax validation
        try:
            if language == 'python':
                compile(code, '<string>', 'exec')
        except SyntaxError as e:
            issues.append({
                'severity': 'ERROR',
                'message': f'Syntax error: {str(e)}'
            })
        
        # 4. Static analysis (complexity, etc.)
        complexity = self._calculate_complexity(code)
        if complexity > 100:
            issues.append({
                'severity': 'WARNING',
                'message': f'High cyclomatic complexity: {complexity}'
            })
        
        return ValidationResult(
            valid=len([i for i in issues if i['severity'] == 'CRITICAL']) == 0,
            issues=issues
        )
```

### Linting & Code Quality

```python
class CodeQualityAnalyzer:
    """Analyze code quality"""
    
    async def analyze(self, code: str, language: str) -> Dict:
        """
        Check for:
        - PEP 8 compliance (Python)
        - Type hints
        - Docstrings
        - Error handling
        - Performance issues
        """
        
        issues = []
        
        # 1. Type hints
        if not re.search(r'->\s*[\w\[\],\s]+:', code):
            issues.append({
                'severity': 'WARNING',
                'message': 'Missing return type hints'
            })
        
        # 2. Docstring
        if not re.search(r'"""[\s\S]*?"""', code):
            issues.append({
                'severity': 'WARNING',
                'message': 'Missing docstring'
            })
        
        # 3. Error handling
        if 'except' not in code and ('requests.' in code or 'open(' in code):
            issues.append({
                'severity': 'WARNING',
                'message': 'Missing error handling for risky operations'
            })
        
        return {
            'quality_score': max(0, 100 - len(issues) * 10),
            'issues': issues
        }
```

---

## Sandbox Execution

### Sandbox Manager

```python
class SandboxManager:
    """Manage tool execution in isolated environments"""
    
    async def execute_tool(
        self,
        tool_code: str,
        language: str,
        params: Dict,
        timeout: int = 300,
        memory_limit: int = 500,
    ) -> ExecutionResult:
        """
        Execute tool code in sandbox
        """
        
        # 1. Create execution environment
        env = await self._create_environment(language)
        
        # 2. Set resource limits
        env.set_timeout(timeout)
        env.set_memory_limit(memory_limit * 1024 * 1024)  # Convert to bytes
        env.set_disk_limit(100 * 1024 * 1024)  # 100 MB
        
        # 3. Inject parameters
        context = {
            'params': params,
            'logger': self._create_safe_logger(),
            'time_remaining': timeout,
        }
        
        # 4. Execute
        start_time = time.time()
        
        try:
            if language == 'python':
                result = await env.execute_python(tool_code, context)
            elif language == 'sql':
                result = await env.execute_sql(tool_code, context)
            elif language == 'javascript':
                result = await env.execute_javascript(tool_code, context)
            else:
                raise ValueError(f"Unsupported language: {language}")
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=True,
                output=result,
                execution_time=execution_time,
                memory_used=env.get_memory_usage(),
                logs=env.get_logs()
            )
            
        except TimeoutError:
            env.kill()
            return ExecutionResult(
                success=False,
                error=f"Execution timeout after {timeout}s",
                execution_time=time.time() - start_time
            )
        
        except MemoryError:
            env.kill()
            return ExecutionResult(
                success=False,
                error=f"Memory limit exceeded ({memory_limit}MB)",
                execution_time=time.time() - start_time
            )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
                logs=env.get_logs()
            )
        
        finally:
            await env.cleanup()
```

### Sandbox Implementation Options

#### Option 1: Docker Containers
```python
class DockerSandbox:
    """Execute code in Docker container"""
    
    async def execute(self, code: str, language: str, params: Dict):
        """
        1. Create container from base image
        2. Copy code to container
        3. Execute
        4. Return results
        5. Clean up
        """
        container = await docker.containers.run(
            image=f"gigaboard-sandbox-{language}:latest",
            command=f"python /code/tool.py",
            volumes={'/tmp/tool.py': code},
            environment=params,
            timeout=300,
            mem_limit="500m",
        )
        
        result = await container.wait()
        output = await container.logs()
        await container.remove()
        
        return output
```

#### Option 2: Process Isolation
```python
class ProcessSandbox:
    """Execute code in isolated process with resource limits"""
    
    async def execute(self, code: str, language: str, params: Dict):
        """
        1. Create subprocess with resource limits
        2. Set ulimit for memory, timeout
        3. Execute code
        4. Monitor resources
        5. Kill if exceeds limits
        """
        proc = subprocess.Popen(
            [interpreter_for(language)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: resource.setrlimit(
                resource.RLIMIT_AS, (500 * 1024 * 1024, 500 * 1024 * 1024)
            )
        )
        
        try:
            stdout, stderr = proc.communicate(
                input=code.encode(),
                timeout=300
            )
            return stdout.decode()
        except subprocess.TimeoutExpired:
            proc.kill()
            raise
```

#### Option 3: V8 Sandbox (for JavaScript)
```python
class V8Sandbox:
    """JavaScript execution in V8 sandbox"""
    
    async def execute(self, code: str, params: Dict):
        """
        Use py-v8 or similar for isolated JS execution
        """
        ctx = py_v8.JSContext()
        ctx.locals['params'] = params
        
        try:
            return ctx.eval(code)
        except py_v8.JSException as e:
            raise ExecutionError(str(e))
```

---

## Tool Versioning & Management

### Tool Registry

```python
class ToolRegistry:
    """Store and manage tools"""
    
    async def register_tool(
        self,
        tool_id: str,
        tool_data: Dict,
        created_by_agent: str
    ) -> str:
        """
        Register tool in system
        """
        
        version = 1
        
        tool_record = {
            'id': tool_id,
            'version': version,
            'name': tool_data['name'],
            'description': tool_data['description'],
            'code': tool_data['code'],
            'language': tool_data['language'],
            'parameters': tool_data['parameters'],
            'returns': tool_data['returns'],
            'created_by': created_by_agent,
            'created_at': datetime.now(),
            'status': 'active',
            'quality_score': tool_data.get('quality_score', 0),
            'usage_count': 0,
            'success_rate': 1.0,
            'avg_execution_time': 0,
            'last_used': None,
        }
        
        # Store in both PostgreSQL and Redis cache
        await self.db.tools.insert_one(tool_record)
        await self.cache.set(f"tool:{tool_id}:v{version}", tool_record)
        
        return f"{tool_id}:v{version}"
    
    async def get_tool(self, tool_id: str, version: int = None) -> Tool:
        """Get tool by ID and optional version"""
        
        if version is None:
            # Get latest version
            version = await self.db.tools.find_one(
                {'id': tool_id},
                sort=[('version', -1)]
            )
            version = version['version'] if version else 1
        
        key = f"tool:{tool_id}:v{version}"
        
        # Try cache first
        cached = await self.cache.get(key)
        if cached:
            return Tool(**cached)
        
        # Query database
        tool_data = await self.db.tools.find_one({
            'id': tool_id,
            'version': version
        })
        
        if not tool_data:
            raise ToolNotFoundError(f"{tool_id}:v{version}")
        
        return Tool(**tool_data)
    
    async def update_tool(
        self,
        tool_id: str,
        updates: Dict,
        notes: str = ""
    ) -> str:
        """
        Create new version of tool
        """
        
        old_tool = await self.get_tool(tool_id)
        new_version = old_tool.version + 1
        
        updated_tool = {
            'id': tool_id,
            'version': new_version,
            'name': updates.get('name', old_tool.name),
            'code': updates.get('code', old_tool.code),
            'modified_at': datetime.now(),
            'modification_notes': notes,
        }
        
        await self.db.tools.insert_one(updated_tool)
        
        return f"{tool_id}:v{new_version}"
    
    async def list_tools(
        self,
        category: str = None,
        created_by: str = None,
        sort_by: str = "usage_count"
    ) -> List[Tool]:
        """List available tools"""
        
        query = {}
        if category:
            query['category'] = category
        if created_by:
            query['created_by'] = created_by
        
        tools = await self.db.tools.find(query).sort(sort_by, -1).to_list()
        return [Tool(**t) for t in tools]
```

### Tool Performance Tracking

```python
class ToolMetrics:
    """Track tool usage and performance"""
    
    async def record_execution(
        self,
        tool_id: str,
        version: int,
        success: bool,
        execution_time: float,
        memory_used: int,
        error: str = None
    ):
        """
        Record execution for metrics
        """
        
        metric = {
            'tool_id': tool_id,
            'version': version,
            'timestamp': datetime.now(),
            'success': success,
            'execution_time': execution_time,
            'memory_used': memory_used,
            'error': error,
        }
        
        await self.db.tool_metrics.insert_one(metric)
        
        # Update tool stats
        await self.db.tools.update_one(
            {'id': tool_id, 'version': version},
            {
                '$inc': {
                    'usage_count': 1,
                    'total_execution_time': execution_time,
                },
                '$set': {
                    'last_used': datetime.now(),
                    'success_rate': await self._calculate_success_rate(tool_id, version)
                }
            }
        )
    
    async def get_tool_stats(self, tool_id: str, version: int) -> Dict:
        """Get performance statistics for tool"""
        
        metrics = await self.db.tool_metrics.find({
            'tool_id': tool_id,
            'version': version
        }).to_list()
        
        return {
            'usage_count': len(metrics),
            'success_count': sum(1 for m in metrics if m['success']),
            'success_rate': sum(1 for m in metrics if m['success']) / len(metrics),
            'avg_execution_time': statistics.mean([m['execution_time'] for m in metrics]),
            'max_execution_time': max([m['execution_time'] for m in metrics]),
            'avg_memory_used': statistics.mean([m['memory_used'] for m in metrics]),
        }
```

---

## Real-World Examples

### Example 1: Shopify Sales Scraper

**User Request**: "I need to analyze sales trends from my Shopify store for the last 3 months"

**Developer Agent Flow**:

1. **Requirement Analysis**
   ```python
   requirement = ToolRequirement(
       title="Fetch Shopify Orders",
       description="Fetch all orders from Shopify store with sales data",
       inputs={
           "shop_url": "string (e.g., myshop.myshopify.com)",
           "access_token": "string (API token)",
           "days_back": "integer (default: 90)",
       },
       outputs={
           "orders": "array of {id, date, total, currency, items}"
       },
       data_sources=["shopify_api"],
       performance_constraints={
           "timeout": 300,
           "memory_limit": 500,
       }
   )
   ```

2. **Template Selection**
   → Uses `PYTHON_API_TEMPLATE`

3. **Code Generation**
   → Generates tool code (shown above)

4. **Validation**
   ```python
   await validator.validate(code, "python")
   # Result: OK, no security issues
   
   await quality_analyzer.analyze(code, "python")
   # Result: Quality score 85/100, needs docstring fix
   ```

5. **Sandbox Test**
   ```python
   test_result = await sandbox.execute(
       code,
       language="python",
       params={
           "shop_url": "test-shop.myshopify.com",
           "access_token": "shpat_test123",
           "days_back": 30
       }
   )
   # Result: Success, 145 orders retrieved
   ```

6. **Registration & Use**
   ```
   Researcher Agent: Execute tool "fetch_shopify_orders"
   → Gets 145 order records
   
   Analyst Agent: Analyze sales trends
   → Calculates growth, identifies patterns
   
   Reporter Agent: Create visualization
   → Adds widget to board
   ```

---

### Example 2: Database Research Tool

**User Request**: "Connect to our analytics database and find all customers from California"

**Developer Agent Flow**:

1. **Code Generation**
   ```python
   generated_code = """
   import psycopg2
   from psycopg2.extras import RealDictCursor
   
   def find_customers_by_state(
       connection_string: str,
       state: str
   ) -> List[Dict]:
       '''
       Find customers from specific state.
       
       Args:
           connection_string: PostgreSQL connection string
           state: State code (e.g., 'CA')
       
       Returns:
           List of customer dictionaries
       '''
       
       try:
           conn = psycopg2.connect(connection_string)
           cursor = conn.cursor(cursor_factory=RealDictCursor)
           
           query = '''
               SELECT id, name, email, state, signup_date
               FROM customers
               WHERE state = %s
               ORDER BY signup_date DESC
           '''
           
           cursor.execute(query, (state,))
           customers = cursor.fetchall()
           
           cursor.close()
           conn.close()
           
           return list(customers)
           
       except psycopg2.Error as e:
           raise Exception(f"Database error: {str(e)}")
   """
   ```

2. **Security Validation**
   - ✅ No file system access
   - ✅ Uses parameterized queries (SQL injection protection)
   - ⚠️ Database connection string handling

3. **Execution**
   ```
   Researcher Agent executes tool
   → Returns 342 customers from California
   → Passes to Analyst
   
   Analyst Agent analyzes
   → Calculates avg lifetime value
   → Identifies high-value customers
   ```

---

## Deployment Architecture

### Production Setup

- Frontend (React)
- API Gateway (FastAPI) via WebSocket to the orchestration service
- Orchestration Service
    - Agent Manager
    - Tool Executor
    - Sandbox Manager
    - Message Bus (Redis)
- Sandbox Resources
    - Docker Sandbox Pool (10-50 containers)
    - Tool Registry (PostgreSQL + Redis)
    - Execution History (PostgreSQL)
    - Code Generator (LLM API)
- Database
    - PostgreSQL (tools, metrics, history)
    - Redis (cache, message bus)
    - MinIO (code versions, backups)

---

## Safety & Governance

### Rate Limiting

```python
class SandboxRateLimiter:
    """Prevent resource abuse"""
    
    # Per user, per hour
    MAX_EXECUTIONS = 100
    MAX_COMPUTE_TIME = 3600  # seconds
    MAX_TOTAL_MEMORY = 10000  # MB
    
    async def check_quota(self, user_id: str) -> bool:
        """Check if user can execute another tool"""
        
        hour_key = f"user:{user_id}:executions:{current_hour()}"
        
        count = await self.cache.get(hour_key) or 0
        
        if count >= self.MAX_EXECUTIONS:
            raise QuotaExceededError("Max executions per hour exceeded")
        
        return True
```

### Audit Trail

```python
class ExecutionAuditTrail:
    """Log all tool executions for compliance"""
    
    async def log_execution(
        self,
        user_id: str,
        tool_id: str,
        params: Dict,
        result: ExecutionResult,
        agent_id: str
    ):
        """
        Create immutable audit log
        """
        
        audit_log = {
            'timestamp': datetime.now(),
            'user_id': user_id,
            'tool_id': tool_id,
            'agent_id': agent_id,
            'params_hash': hash(str(params)),  # Don't store sensitive params
            'success': result.success,
            'execution_time': result.execution_time,
            'error': result.error,
            'ip_address': get_client_ip(),
        }
        
        # Store in immutable audit log
        await self.db.audit_logs.insert_one(audit_log)
```

---

## Status

**Completed**: Design, Architecture, Sandbox strategy
**Ready for**: Implementation with Docker/process isolation
**Next Phase**: Integration with Agent system

