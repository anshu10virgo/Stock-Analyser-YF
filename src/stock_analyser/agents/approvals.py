"""Approval decisions kept separate from tool discovery and execution."""

from stock_analyser.agents.contracts import ApprovalLevel


def approval_granted(
    required: ApprovalLevel,
    *,
    user_approved: bool = False,
    admin_approved: bool = False,
) -> bool:
    """Return whether the supplied authorization satisfies the requirement."""
    if required == ApprovalLevel.NONE:
        return True
    if required == ApprovalLevel.USER_CONFIRMATION:
        return user_approved
    return admin_approved


__all__ = ["approval_granted"]
