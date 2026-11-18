import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class InspectionSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    zone: list[tuple[float, float]] = Field(default_factory=lambda: [(0.05, .05), (.95, .05), (.95, .95), (.05, .95)])
    confidence: float = Field(.5, ge=.1, le=.95)
    dwell_seconds: float = Field(1, ge=.1, le=60)
    priority_count: int = Field(3, ge=2, le=50)
    priority_seconds: float = Field(2, ge=.1, le=60)
    track_gap_seconds: float = Field(.6, ge=.1, le=2)

    @model_validator(mode='after')
    def valid_polygon(self):
        p = self.zone
        if not 3 <= len(p) <= 12 or any(not math.isfinite(v) or not 0 <= v <= 1 for xy in p for v in xy):
            raise ValueError('Zone requires 3–12 normalized points between 0 and 1.')
        if len(set(p)) != len(p):
            raise ValueError('Zone points must be distinct.')
        cross = lambda a,b,c: (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        # Only simple convex polygons: predictable inclusion and easy drawing.
        turns = [cross(p[i-1], p[i], p[(i+1)%len(p)]) for i in range(len(p))]
        if any(abs(t) < 1e-8 for t in turns) or not (all(t > 0 for t in turns) or all(t < 0 for t in turns)):
            raise ValueError('Draw a convex zone with no collinear corners.')
        for i in range(len(p)):
            for j in range(i+1, len(p)):
                if j == i+1 or (i == 0 and j == len(p)-1):
                    continue
                a,b,c,d = p[i],p[(i+1)%len(p)],p[j],p[(j+1)%len(p)]
                if cross(a,b,c)*cross(a,b,d) <= 0 and cross(c,d,a)*cross(c,d,b) <= 0:
                    raise ValueError('Zone edges must not intersect.')
        area = abs(sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))) / 2
        if area < .005:
            raise ValueError('Zone is too small.')
        return self


class JobRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_type: Literal['video', 'camera'] = 'video'
    upload_id: str | None = None
    camera_index: int = Field(0, ge=0, le=9)
    realtime: bool = True
    settings: InspectionSettings = Field(default_factory=InspectionSettings)

    @model_validator(mode='after')
    def has_source(self):
        if self.source_type == 'video' and not self.upload_id:
            raise ValueError('upload_id is required for a video job.')
        if self.source_type == 'camera' and self.upload_id:
            raise ValueError('Camera jobs must not contain upload_id.')
        return self
