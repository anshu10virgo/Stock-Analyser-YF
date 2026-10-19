"""Central permission policy for every agent-visible operation."""

from stock_analyser.agents.contracts import ApprovalLevel, ToolEffect


EFFECT_APPROVAL = {
    ToolEffect.READ_ONLY: ApprovalLevel.NONE,
    ToolEffect.SESSION_MUTATION: ApprovalLevel.USER_CONFIRMATION,
    ToolEffect.EXPENSIVE_COMPUTE: ApprovalLevel.USER_CONFIRMATION,
    ToolEffect.EXTERNAL_SIDE_EFFECT: ApprovalLevel.USER_CONFIRMATION,
    ToolEffect.PRODUCTION_OPERATION: ApprovalLevel.ADMIN_CONFIRMATION,
}


def required_approval(effect: ToolEffect) -> ApprovalLevel:
    """Return the minimum approval required by the tool's declared effect."""
    return EFFECT_APPROVAL[effect]


def validate_tool_policy(effect: ToolEffect, approval: ApprovalLevel) -> None:
    """Reject definitions that weaken the central effect policy."""
    required = required_approval(effect)
    order = {
        ApprovalLevel.NONE: 0,
        ApprovalLevel.USER_CONFIRMATION: 1,
        ApprovalLevel.ADMIN_CONFIRMATION: 2,
    }
    if order[approval] < order[required]:
        raise ValueError(
            f"{effect.value} tools require at least {required.value} approval"
        )


__all__ = ["EFFECT_APPROVAL", "required_approval", "validate_tool_policy"]
