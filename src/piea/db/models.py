"""SQLAlchemy models for PIEA database.

This module defines all database tables and relationships for the
Public Information Exposure Analyzer.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class ConsentRecord(Base):
    """Records user consent for scans."""

    __tablename__ = "consent_records"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    attestation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    operator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operator_ip: Mapped[str] = mapped_column(INET, nullable=False)
    consent_text_version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    scans: Mapped[list["Scan"]] = relationship(back_populates="consent_record")


class Scan(Base):
    """Represents a single exposure scan."""

    __tablename__ = "scans"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    consent_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("consent_records.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    input_name_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_username: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    modules_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    consent_record: Mapped["ConsentRecord"] = relationship(back_populates="scans")
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    graph_nodes: Mapped[list["GraphNode"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    graph_edges: Mapped[list["GraphEdge"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class Finding(Base):
    """A discrete finding from a scan."""

    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    weight_applied: Mapped[float] = mapped_column(Float, nullable=False)
    remediation_action: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_effort: Mapped[str] = mapped_column(String(20), nullable=False)
    remediation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    scan: Mapped["Scan"] = relationship(back_populates="findings")


class GraphNode(Base):
    """A node in the identity graph."""

    __tablename__ = "graph_nodes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    scan: Mapped["Scan"] = relationship(back_populates="graph_nodes")
    outgoing_edges: Mapped[list["GraphEdge"]] = relationship(
        foreign_keys="GraphEdge.source_node_id", back_populates="source_node"
    )
    incoming_edges: Mapped[list["GraphEdge"]] = relationship(
        foreign_keys="GraphEdge.target_node_id", back_populates="target_node"
    )


class GraphEdge(Base):
    """An edge in the identity graph."""

    __tablename__ = "graph_edges"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id"), nullable=False)
    source_node_id: Mapped[UUID] = mapped_column(
        ForeignKey("graph_nodes.id"), nullable=False
    )
    target_node_id: Mapped[UUID] = mapped_column(
        ForeignKey("graph_nodes.id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    scan: Mapped["Scan"] = relationship(back_populates="graph_edges")
    source_node: Mapped["GraphNode"] = relationship(
        foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target_node: Mapped["GraphNode"] = relationship(
        foreign_keys=[target_node_id], back_populates="incoming_edges"
    )


class AuditLog(Base):
    """Audit log entries for scans."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    operator_ip: Mapped[str] = mapped_column(INET, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    scan: Mapped["Scan"] = relationship(back_populates="audit_logs")
