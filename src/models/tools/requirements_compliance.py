from typing import ClassVar, Dict, Literal
from pydantic import BaseModel

class RequirementsComplianceTool(BaseModel):
    config_id: ClassVar[str] = "requirementsCompliance"
    name: Literal["requirementsCompliance"] = "requirementsCompliance"
    tool_type: Literal["local"] = "local"
    label: Literal["Requirements Compliance"] = "Requirements Compliance"
    description: str = "Generate a compliance report based on the requirements and description source."
    config: Dict = {}
    enabled: bool = False