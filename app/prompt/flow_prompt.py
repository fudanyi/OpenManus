"""Prompt strings for flow operations."""

# step info
STEP_EXECUTION_PROMPT = '''
CURRENT PLAN STATUS:
{plan_status}

YOUR CURRENT TASK:
You are now working on step {step_index}: "{step_text}"

Please only execute this current step using the appropriate tools.
'''

# step ummarize
SUMMARY_SYSTEM_MESSAGE = "You are a information extraction assistant."

SUMMARY_REQUEST_PROMPT = """Your task is to summarize previous conversation(representing partial execution of an agent) into a comprehensive document.

## Key Elements to Include
1. **Insights** - Key learnings and observations
2. **Fact Details** - Important factual information
3. **Information Fetched** - Critical data and resources obtained
4. **Deliverables** - Completed outputs and results
5. **Error Prevention** - Recommendations to avoid common issues

## Document Requirements
- The document must contain sufficient and accurate details for subsequent execution to complete user goal without duplicate refetching/redoing
- Pay special attention to data schema details
- Assume subsequent execution only has access to this summary
- Do NOT include planning information as it will be fetched automatically
"""

# finalize
FINALIZE_SYSTEM_MESSAGE = "You are a professional summarize assistant."

FINALIZE_REQUEST_PROMPT = """Your task is to summarize previous messages into a concise summary including:

1. **Deliverables**
2. **Valuable Insights**
3. **Potential Next Steps**
4. **Final Thoughts**

Then always use result_reporter tool to report deliverables. DO NOT mention the tool in your summary since user won't care."""

