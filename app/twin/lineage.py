from __future__ import annotations

from collections.abc import Iterable

from app.contracts import DataArtifact


SENSITIVE_BASE_LABELS = {
    "CustomerPII",
    "SECRET",
    "CONFIDENTIAL",
}


def is_derived_sensitive_label(label: str) -> bool:
    """
    Check whether a label represents data derived from
    an already-sensitive source.
    """
    return (
        label.startswith("DerivedFrom<")
        and label.endswith(">")
    )


def is_sensitive_label(label: str) -> bool:
    """
    Return True if a label is sensitive either directly
    or because it was derived from sensitive data.
    """
    return (
        label in SENSITIVE_BASE_LABELS
        or is_derived_sensitive_label(label)
    )


def is_sensitive_artifact(
    artifact: DataArtifact,
) -> bool:
    """
    Determine whether any label on an artifact is sensitive.
    """
    return any(
        is_sensitive_label(label)
        for label in artifact.labels
    )


def derived_label(label: str) -> str:
    """
    Convert a sensitive label into its lineage-preserving form.

    CustomerPII
        -> DerivedFrom<CustomerPII>

    DerivedFrom<CustomerPII>
        -> DerivedFrom<CustomerPII>
    """
    if is_derived_sensitive_label(label):
        return label

    return f"DerivedFrom<{label}>"


def propagate_labels(
    parent_artifacts: Iterable[DataArtifact],
) -> set[str]:
    """
    Propagate security labels through a transformation.

    Sensitive source labels become DerivedFrom<...>.
    Non-sensitive labels are preserved.
    """
    output_labels: set[str] = set()

    for artifact in parent_artifacts:
        for label in artifact.labels:
            if is_sensitive_label(label):
                output_labels.add(
                    derived_label(label)
                )
            else:
                output_labels.add(label)

    return output_labels


def create_derived_artifact(
    *,
    artifact_id: str,
    value: object,
    parent_artifacts: Iterable[DataArtifact],
    transformation: str,
) -> DataArtifact:
    """
    Create a new artifact whose security lineage is inherited
    from its parent artifacts.
    """
    parents = list(parent_artifacts)

    labels = propagate_labels(parents)

    return DataArtifact(
        artifact_id=artifact_id,
        value=value,
        labels=labels,
        parent_artifact_ids={
            artifact.artifact_id
            for artifact in parents
        },
        transformation=transformation,
    )


def contains_sensitive_lineage(
    artifact: DataArtifact,
) -> bool:
    """
    True when the artifact contains either direct sensitive
    data or data derived from a sensitive source.
    """
    return is_sensitive_artifact(
        artifact
    )


def trace_lineage(
    artifact_id: str,
    artifacts: Iterable[DataArtifact],
) -> list[str]:
    """
    Return all ancestor artifact IDs for a given artifact.

    This is useful later when AttackPath evidence needs to
    explain where sensitive data originated.
    """
    artifact_map = {
        artifact.artifact_id: artifact
        for artifact in artifacts
    }

    visited: set[str] = set()
    ordered: list[str] = []

    def visit(current_id: str) -> None:
        if current_id in visited:
            return

        visited.add(current_id)

        artifact = artifact_map.get(
            current_id
        )

        if artifact is None:
            return

        for parent_id in artifact.parent_artifact_ids:
            visit(parent_id)

        ordered.append(current_id)

    visit(artifact_id)

    return ordered