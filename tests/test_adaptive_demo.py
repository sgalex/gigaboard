"""
Quick adaptive planning demonstration (ASCII-only for Windows compatibility).
"""
import asyncio
import sys
import os
from pathlib import Path

# Setup
backend_dir = Path(__file__).parent.parent / "apps" / "backend"
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

from app.services.multi_agent import MultiAgentEngine


async def demo():
    print("\n" + "=" * 80)
    print("ADAPTIVE PLANNING DEMO")
    print("=" * 80 + "\n")
    
    engine = MultiAgentEngine(adaptive_planning=True)
    
    try:
        await engine.initialize()
        print("[OK] Engine initialized with adaptive_planning=True\n")
        
        request = """
        Find the top 5 programming languages of 2026.
        For each language, find recent news and trends.
        Create a comparative analysis and visualization.
        """
        
        print("REQUEST:")
        print(request)
        print("\n" + "-" * 80)
        print("EXPECTATION: After finding 5 languages, plan should adapt")
        print("             to add separate research steps for each language")
        print("-" * 80 + "\n")
        
        result = await engine.process_request(
            user_request=request,
            board_id="demo",
            session_id="adaptive_demo"
        )
        
        # Results
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80 + "\n")
        
        initial_plan = result["plan"].get("plan", {})
        initial_steps = len(initial_plan.get("steps", []))
        
        executed_steps = len([k for k in result["results"] if k.startswith("step_")])
        optimizations = [k for k in result["results"] if k.startswith("optimization_")]
        errors = [k for k, v in result["results"].items() 
                  if k.startswith("step_") and v.get("status") == "error"]
        
        print(f"Initial plan: {initial_steps} steps")
        print(f"Executed: {executed_steps} steps")
        print(f"Added steps: {executed_steps - initial_steps}")
        print(f"Optimizations: {len(optimizations)}")
        print(f"Errors: {len(errors)}")
        print(f"Time: {result.get('execution_time', 0):.2f}s")
        print(f"Status: {result.get('status')}\n")
        
        if optimizations:
            print("="  * 80)
            print("PLAN ADAPTATIONS DETECTED!")
            print("=" * 80 + "\n")
            for opt_key in sorted(optimizations):
                opt = result["results"][opt_key]
                print(f"{opt_key}:")
                print(f"  After step: {opt.get('after_step')}")
                print(f"  Changes: {opt.get('changes')}")
                
                opt_data = opt.get("optimization_data", {})
                if opt_data.get("changes"):
                    print(f"  Actions:")
                    for change in opt_data["changes"]:
                        action = change.get("action")
                        if action == "add_step":
                            agent = change.get("step", {}).get("agent", "N/A")
                            print(f"    + Add step: {agent}")
                        elif action == "modify_step":
                            print(f"    * Modify step: {change.get('step_id')}")
                        elif action == "remove_step":
                            print(f"    - Remove step: {change.get('step_id')}")
                print()
        else:
            print("[INFO] No optimizations were made")
            print("       GigaChat decided the initial plan was optimal\n")
        
        # Show step breakdown
        print("=" * 80)
        print("STEP BREAKDOWN")
        print("=" * 80 + "\n")
        
        for key in sorted([k for k in result["results"] if k.startswith("step_")]):
            step_result = result["results"][key]
            agent = step_result.get("agent", "N/A")
            status = step_result.get("status", "N/A")
            task_type = step_result.get("task", {}).get("type", "N/A") if isinstance(step_result.get("task"), dict) else "N/A"
            
            status_mark = "[OK]" if status == "success" else "[FAIL]" if status == "error" else "[PART]"
            print(f"{key}: {status_mark} {agent} - {task_type}")
        
        print("\n" + "=" * 80)
        print("DEMO COMPLETE")
        print("=" * 80 + "\n")
        
    finally:
        await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(demo())
