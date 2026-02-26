"""
QAForge -- Test agent configuration routes.

Prefix: /api/test-agents

Endpoints:
    POST   /             — create test agent
    GET    /             — list test agents
    GET    /{id}         — get test agent detail
    PUT    /{id}         — update test agent
    DELETE /{id}         — delete test agent
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from db_models import TestAgent, User
from db_session import get_db
from dependencies import audit_log, get_client_ip, get_current_user, sanitize_string
from models import (
    MessageResponse,
    TestAgentCreate,
    TestAgentResponse,
    TestAgentUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=TestAgentResponse,
    summary="Create a test agent",
    status_code=status.HTTP_201_CREATED,
)
def create_test_agent(
    body: TestAgentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = TestAgent(
        name=sanitize_string(body.name) or body.name,
        description=sanitize_string(body.description) if body.description else None,
        domain=body.domain,
        sub_domain=body.sub_domain,
        agent_type=body.agent_type,
        system_prompt=body.system_prompt,
        config=body.config,
        connection_ids=body.connection_ids,
        template_id=body.template_id,
        created_by=current_user.id,
    )
    db.add(agent)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_test_agent",
        entity_type="test_agent",
        entity_id=str(agent.id),
        details={"name": agent.name, "agent_type": agent.agent_type},
        ip_address=get_client_ip(request),
    )

    logger.info("Test agent created: %s by %s", agent.name, current_user.email)
    return TestAgentResponse.model_validate(agent)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=list[TestAgentResponse],
    summary="List test agents",
)
def list_test_agents(
    agent_type: str | None = Query(None),
    domain: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(TestAgent)
    if agent_type:
        query = query.filter(TestAgent.agent_type == agent_type)
    if domain:
        query = query.filter(TestAgent.domain == domain)
    agents = query.order_by(TestAgent.created_at.desc()).all()
    return [TestAgentResponse.model_validate(a) for a in agents]


# ---------------------------------------------------------------------------
# GET /{id}
# ---------------------------------------------------------------------------
@router.get(
    "/{agent_id}",
    response_model=TestAgentResponse,
    summary="Get test agent detail",
)
def get_test_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(TestAgent).filter(TestAgent.id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Test agent not found")
    return TestAgentResponse.model_validate(agent)


# ---------------------------------------------------------------------------
# PUT /{id}
# ---------------------------------------------------------------------------
@router.put(
    "/{agent_id}",
    response_model=TestAgentResponse,
    summary="Update a test agent",
)
def update_test_agent(
    agent_id: uuid.UUID,
    body: TestAgentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(TestAgent).filter(TestAgent.id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Test agent not found")

    if body.name is not None:
        agent.name = sanitize_string(body.name) or body.name
    if body.description is not None:
        agent.description = sanitize_string(body.description)
    if body.system_prompt is not None:
        agent.system_prompt = body.system_prompt
    if body.config is not None:
        agent.config = body.config
    if body.connection_ids is not None:
        agent.connection_ids = body.connection_ids
    if body.template_id is not None:
        agent.template_id = body.template_id
    if body.status is not None:
        agent.status = body.status

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_test_agent",
        entity_type="test_agent",
        entity_id=str(agent.id),
        details=body.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )

    return TestAgentResponse.model_validate(agent)


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{agent_id}",
    response_model=MessageResponse,
    summary="Delete a test agent",
)
def delete_test_agent(
    agent_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(TestAgent).filter(TestAgent.id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Test agent not found")

    name = agent.name
    db.delete(agent)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_test_agent",
        entity_type="test_agent",
        entity_id=str(agent_id),
        details={"name": name},
        ip_address=get_client_ip(request),
    )

    return MessageResponse(message=f"Test agent '{name}' deleted")
