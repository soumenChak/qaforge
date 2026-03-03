#!/bin/bash
# QAForge Agent Workflow E2E Test
set -euo pipefail

BASE="https://13.233.36.18:8080/api"
C="curl -sk"

echo "=== QAForge Agent Workflow E2E Test ==="
echo ""

# 1. Login
echo "1. Logging in..."
LOGIN_RESP=$($C -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@freshgravity.com","password":"admin123"}')
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "   OK: token=${TOKEN:0:20}..."

# 2. Create project
echo "2. Creating project..."
PROJ_RESP=$($C -X POST "$BASE/projects/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Orbit E2E Validation","domain":"ai","sub_domain":"orbit","description":"E2E test of QAForge agent workflow"}')
PROJECT_ID=$(echo "$PROJ_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "   OK: project=$PROJECT_ID"

# 3. Generate agent key
echo "3. Generating agent key..."
KEY_RESP=$($C -X POST "$BASE/projects/$PROJECT_ID/agent-key" \
  -H "Authorization: Bearer $TOKEN")
AGENT_KEY=$(echo "$KEY_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")
echo "   OK: key=${AGENT_KEY:0:15}..."

# 4. Create test plan
echo "4. Creating test plan..."
PLAN_RESP=$($C -X POST "$BASE/projects/$PROJECT_ID/test-plans" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Sprint 1 SIT","plan_type":"sit","description":"Auth & RBAC validation"}')
PLAN_ID=$(echo "$PLAN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "   OK: plan=$PLAN_ID"

# 5. Start agent session
echo "5. Starting agent session..."
SESSION_RESP=$($C -X POST "$BASE/agent/sessions" \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_name":"claude-code","agent_version":"1.0","submission_mode":"realtime"}')
SESSION_ID=$(echo "$SESSION_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "   OK: session=$SESSION_ID"

# 6. Submit test cases
echo "6. Submitting test cases..."
TC_RESP=$($C -X POST "$BASE/agent/test-cases" \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"test_plan_id\":\"$PLAN_ID\",\"test_cases\":[
    {\"test_case_id\":\"TC-AUTH-001\",\"title\":\"Admin login returns JWT\",\"category\":\"functional\",\"priority\":\"P1\",\"execution_type\":\"api\",\"expected_result\":\"200 + valid JWT\"},
    {\"test_case_id\":\"TC-AUTH-002\",\"title\":\"Invalid password returns 401\",\"category\":\"functional\",\"priority\":\"P1\",\"execution_type\":\"api\",\"expected_result\":\"401 Unauthorized\"},
    {\"test_case_id\":\"TC-RBAC-001\",\"title\":\"Non-admin cannot access user list\",\"category\":\"functional\",\"priority\":\"P2\",\"execution_type\":\"api\",\"expected_result\":\"403 Forbidden\"}
  ]}")
TC_COUNT=$(echo "$TC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('created',len(d)) if isinstance(d,dict) else len(d))")
echo "   OK: $TC_COUNT test cases submitted"

# 7. Get test case UUIDs
echo "7. Fetching test cases..."
TC_LIST=$($C "$BASE/agent/test-cases?test_plan_id=$PLAN_ID" \
  -H "X-Agent-Key: $AGENT_KEY")
TC1=$(echo "$TC_LIST" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
TC2=$(echo "$TC_LIST" | python3 -c "import sys,json; print(json.load(sys.stdin)[1]['id'])")
echo "   OK: TC1=$TC1, TC2=$TC2"

# 8. Submit execution results with proof
echo "8. Submitting execution results with proof..."
EXEC_RESP=$($C -X POST "$BASE/agent/executions" \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"executions\":[
    {\"test_case_id\":\"$TC1\",\"test_plan_id\":\"$PLAN_ID\",\"status\":\"passed\",\"actual_result\":\"200 OK with valid JWT\",\"duration_ms\":245,\"environment\":{\"url\":\"http://localhost:8000\",\"method\":\"POST /auth/login\"},\"proof_artifacts\":[{\"proof_type\":\"api_response\",\"title\":\"Login response\",\"content\":{\"status\":200,\"body\":{\"access_token\":\"eyJ...\",\"token_type\":\"bearer\"}}}]},
    {\"test_case_id\":\"$TC2\",\"test_plan_id\":\"$PLAN_ID\",\"status\":\"passed\",\"actual_result\":\"401 Unauthorized returned correctly\",\"duration_ms\":89,\"environment\":{\"url\":\"http://localhost:8000\",\"method\":\"POST /auth/login\"},\"proof_artifacts\":[{\"proof_type\":\"api_response\",\"title\":\"Invalid login response\",\"content\":{\"status\":401,\"body\":{\"detail\":\"Invalid credentials\"}}}]}
  ]}")
EXEC_COUNT=$(echo "$EXEC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('created',len(d)) if isinstance(d,dict) else len(d))")
echo "   OK: $EXEC_COUNT execution results submitted"

# 9. Check summary
echo "9. Checking summary..."
SUMMARY=$($C "$BASE/agent/summary?test_plan_id=$PLAN_ID" \
  -H "X-Agent-Key: $AGENT_KEY")
echo "   Summary:"
echo "$SUMMARY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))"

echo ""
echo "=== E2E TEST COMPLETE ==="
echo "Project: $PROJECT_ID"
echo "Test Plan: $PLAN_ID"
echo "Agent Session: $SESSION_ID"
