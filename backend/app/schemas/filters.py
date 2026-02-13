from pydantic import BaseModel, Field, validator
from typing import Optional

class AnomalyFilters(BaseModel):
    severity: Optional[str] = Field(None, regex="^(low|medium|high|critical)$")
    days: int = Field(7, ge=1, le=90)
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    min_vpin: Optional[float] = Field(None, ge=0.0, le=1.0)
    has_whales: Optional[bool] = None
    min_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    ticker: Optional[str] = None
    category: Optional[str] = None
