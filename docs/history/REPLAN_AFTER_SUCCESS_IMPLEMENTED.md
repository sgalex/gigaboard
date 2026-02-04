# Replan After Success - Implementation Complete

**Date:** 2026-01-28  
**Status:** ✅ Implemented and Tested

## Summary

Replaced lightweight plan optimization (`_optimize_plan_after_step`) with full replan mechanism using `PlannerAgent.replan()` after each successful step. This allows the planner to revise the entire execution plan based on accumulated results from all previous steps.

## What Changed

### Before (Optimization Approach)
```python
if self.adaptive_planning:
    optimization = await self._optimize_plan_after_step(...)
    if optimization.get("should_update"):
        # Apply add/modify/remove actions
        plan = optimization["updated_plan"]
```

**Problems:**
- Separate GigaChat call for optimization analysis
- Limited to add/modify/remove actions
- No access to PlannerAgent's full replanning logic

### After (Full Replan Approach)
```python
if self.adaptive_planning and replan_count < MAX_REPLAN_ATTEMPTS:
    should_replan = await self._should_replan_after_step(...)
    
    if should_replan.get("replan"):
        replan_count += 1
        replan_result = await self.agents["planner"].process_task(
            task={
                "type": "replan",
                "original_plan": plan,
                "current_results": results,  # All accumulated knowledge!
                "completed_steps": i,
                "reason": should_replan.get("reason")
            },
            context=full_context
        )
        
        if replan_result.get("status") == "success":
            plan = replan_result.get("plan", {})
```

**Benefits:**
- Uses PlannerAgent's full replan capability
- Passes ALL accumulated results as context
- Leverages existing replan logic
- More intelligent plan revision

## Implementation Details

### New Method: `_should_replan_after_step()`

Located in `apps/backend/app/services/multi_agent/engine.py` (lines 178-251)

**Purpose:** Determines if replanning is needed after successful step execution

**How it works:**
1. GigaChat analyzes step result + accumulated results
2. Evaluates based on criteria:
   - New information that changes strategy
   - New data sources requiring different approach
   - Current plan is not optimal
   - Need to change step sequence/logic
   - Some steps can be skipped/merged
3. Returns decision: `{"replan": true/false, "reason": "...", "key_insights": "..."}`

**Prompt structure:**
```python
prompt = f"""Ты - AI планировщик, анализирующий результаты выполнения шагов...

ТЕКУЩАЯ СИТУАЦИЯ:
Только что успешно выполнен шаг #{step_index + 1}
Агент: {agent_name}
Статус: {step_result['status']}

ОБЩИЙ КОНТЕКСТ:
Всего шагов в плане: {total_steps}
Выполнено шагов: {step_index + 1}
Накопленные результаты: {len(all_results)} результатов

ОСТАВШИЕСЯ ШАГИ:
{remaining_steps}

КРИТЕРИИ ДЛЯ REPLAN:
1. Существенно новая информация...
2. Новые источники данных...
3. План не оптимален...
...
"""
```

### Modified: Main Execution Loop

Located in `apps/backend/app/services/multi_agent/engine.py` (lines 645-695)

**Changes:**
1. Added `_should_replan_after_step()` call after each successful step
2. Added logging of GigaChat decisions
3. Call `PlannerAgent.replan()` if decision is True
4. Track replan count with MAX_REPLAN_ATTEMPTS=2
5. Store replan info in results for analysis

**Replan tracking:**
```python
results[f"replan_{replan_count}"] = {
    "after_step": i,
    "old_steps_count": len(steps),
    "new_steps_count": len(new_steps),
    "reason": should_replan.get("reason"),
    "changes": replan_result.get("changes")
}
```

### Removed Methods

- `_optimize_plan_after_step()` - No longer needed (full replan replaces optimization)
- `_apply_plan_changes()` - No longer needed (replan handles plan changes directly)

## Testing

### Test: test_replan_demo.py

**Purpose:** Demonstrate replan mechanism with detailed logging

**Results:**
```
✅ Step 1 completed: success
🤖 GigaChat replan decision: False
   Reason: Plan is executing as expected, no strategy change needed

✅ Step 2 completed: success
🤖 GigaChat replan decision: False
   Reason: План выполняется последовательно, результаты соответствуют ожидаемым

✅ Step 3 completed: success
🤖 GigaChat replan decision: False
   Reason: План выполняется успешно, не требуется пересмотр стратегии

✅ Step 4 completed: success
🤖 GigaChat replan decision: False
   Reason: План выполняется успешно, результаты соответствуют ожидаемым
```

**Analysis:** GigaChat correctly analyzes after each step and decides replanning is NOT needed because:
- Plan is executing successfully
- Results are predictable and expected
- No new information changes the strategy
- Remaining steps are correct and sufficient

### When Would Replan Trigger?

Based on prompt criteria, replan would trigger when:
1. **New data sources discovered:** e.g., step 1 finds 10 sources instead of expected 2 → need more parallel processing steps
2. **Strategy needs change:** e.g., data format is different than expected → need different processing approach
3. **Optimization opportunity:** e.g., some steps can be skipped or combined based on results
4. **Unexpected results:** e.g., found more comprehensive data than expected → can simplify remaining steps

**Example scenario:**
```
Step 1 (SearchAgent): Finds 10 programming languages instead of 5
GigaChat decision: replan=True
Reason: "Найдено в 2 раза больше языков. Нужно добавить параллельные шаги 
         исследования для каждого или сгруппировать в батчи."
Result: Plan updated from 4 steps to 7 steps with parallel processing
```

## Configuration

### Adaptive Planning Flag

`MultiAgentEngine(adaptive_planning=True)` - Enable/disable full replan after success

### Replan Limits

`MAX_REPLAN_ATTEMPTS = 2` - Maximum replans per workflow (prevents infinite loops)

### GigaChat Parameters

```python
temperature=0.3  # Conservative - prefer keeping plan unchanged
max_tokens=500   # Enough for decision + reasoning
```

## Logging

New log messages added:
- `🤖 GigaChat replan decision: {True/False}`
- `   Reason: {decision reasoning}`
- `🔄 Replanning based on step {i} results (attempt {n}/{max})...`
- `✅ Plan updated: {old_count} → {new_count} steps`

## Performance Considerations

### API Calls per Step (when adaptive_planning=True)
1. Step execution (agent call)
2. Replan decision analysis (GigaChat call) - **NEW**
3. If replan=True: Full replan (GigaChat call) - **CONDITIONAL**

**Impact:** +1 GigaChat call per successful step (replan analysis)

**Mitigation options:**
1. Analyze only on certain steps (e.g., after key milestones)
2. Use caching for similar scenarios
3. Batch analysis for multiple steps
4. Add frequency threshold (e.g., every 3 steps)

## Future Enhancements

### 1. Selective Replanning
Instead of analyzing after EVERY step, trigger based on conditions:
```python
if should_analyze_for_replan(step, result):
    should_replan = await self._should_replan_after_step(...)
```

Conditions:
- Step discovers new data sources
- Step result has "unexpected" flag
- After key milestone steps (search, analyst)
- Result contains more data than threshold

### 2. Replan Confidence Score
Add confidence to decision:
```python
{
    "replan": true,
    "confidence": 0.85,  # How sure GigaChat is
    "reason": "...",
    "key_insights": "..."
}
```

Only replan if confidence > threshold.

### 3. Replan History
Track replan patterns for optimization:
```python
replan_history = {
    "total_workflows": 100,
    "total_replans": 12,
    "replan_rate": 0.12,
    "most_common_reasons": ["new_sources", "optimization"]
}
```

### 4. A/B Testing
Compare workflows with/without adaptive replanning:
- Execution time
- Result quality
- API call count
- User satisfaction

## Documentation Updates Needed

- [x] ADAPTIVE_PLANNING.md - Update with replan approach
- [x] REPLAN_DECISION_LOGIC_ANALYSIS.md - Update with new logic
- [ ] MULTI_AGENT_SYSTEM.md - Add replan after success section
- [ ] API.md - Document replan tracking in results
- [ ] ROADMAP.md - Mark adaptive planning as complete

## Related Files

- `apps/backend/app/services/multi_agent/engine.py` (lines 178-251, 645-695)
- `apps/backend/app/services/multi_agent/agents/planner.py` (replan method)
- `tests/test_replan_demo.py` - Demo test
- `tests/test_adaptive_demo.py` - Complex scenario test
- `docs/ADAPTIVE_PLANNING.md` - Documentation
- `docs/REPLAN_DECISION_LOGIC_ANALYSIS.md` - Decision logic analysis

## Conclusion

✅ **Implementation Complete**  
✅ **Tested Successfully**  
✅ **Logging Verified**  
⏳ **Waiting for real-world scenarios** to trigger replan decisions

The system now has intelligent adaptive planning that can revise entire execution plans based on accumulated knowledge from previous steps. GigaChat makes conservative decisions (temperature=0.3) to avoid unnecessary replanning, but will trigger replan when significant new information changes the optimal strategy.

**Key Achievement:** Full integration between adaptive planning and PlannerAgent's replan capability, passing ALL accumulated results for knowledge-based replanning.
