"""VideoScript contract.

The script-orchestrator writes one global TVC script, then breaks it into:
- storyboard shots: micro-shot references for rhythm, composition, and prompts
- render segments: the actual video generation units consumed by compile/render

This keeps the creative script concrete without forcing the renderer to create
one expensive video job per micro-shot.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GlobalNarrative(BaseModel):
    """One-film story spine used by all storyboard shots and render segments."""

    logline: str = Field(default="", description="One sentence creative promise")
    arc: str = Field(default="", description="Beginning -> build -> climax -> landing")
    funnel: str = Field(default="", description="Attention -> desire -> proof -> action")
    narration_spine: str = Field(default="", description="Full-film voiceover idea before splitting")
    visual_spine: str = Field(default="", description="Full-film visual continuity and motif")
    pacing: str = Field(default="two-segment-tvc", description="Pacing system, e.g. two-segment-tvc")


class Shot(BaseModel):
    """Storyboard micro-shot.

    A shot is a precise visual/narrative reference. It is not necessarily a
    separate render job. Render jobs are represented by RenderSegment.
    """

    index: int = Field(ge=0, description="Storyboard shot index, starting at 0")
    beat: str = Field(default="", description="Narrative beat name from the brief")
    duration_sec: float = Field(gt=0, description="Storyboard timing reference in seconds")
    image_prompt: str = Field(description="Concrete still/storyboard prompt")
    video_prompt: str = Field(description="Concrete motion/camera prompt for this micro-shot")
    narration: str = Field(default="", description="Local voiceover text, optional")
    on_screen_text: str = Field(default="", description="Short on-screen copy")
    transition: str = Field(default="cut", description="cut / fade / dissolve")


class RenderSegment(BaseModel):
    """Actual video generation segment.

    For a 25s TVC this should normally be two segments, e.g. 12+13 or 10+15,
    instead of five independent 5s clips. Storyboard shots remain available as
    references through shot_indices and storyboard_prompt.
    """

    index: int = Field(ge=0, description="Render segment index, starting at 0")
    name: str = Field(default="", description="Human-readable segment name")
    beat: str = Field(default="", description="Major beat covered by the segment")
    duration_sec: float = Field(gt=0, le=15, description="Requested render duration; keep <=15s")
    shot_indices: list[int] = Field(default_factory=list, description="Storyboard shots covered")
    storyboard_prompt: str = Field(default="", description="Storyboard/reference description for this segment")
    video_prompt: str = Field(description="Full segment I2V prompt with motion, camera, and continuity")
    narration: str = Field(default="", description="Segment voiceover text")
    on_screen_text: str = Field(default="", description="Short segment on-screen text")
    transition: str = Field(default="cut", description="Transition into the next segment")
    entry_state: str = Field(default="", description="Continuity state at segment start, especially for >30s films")
    exit_state: str = Field(default="", description="Continuity state at segment end, especially for >30s films")
    continuity_anchor: str = Field(
        default="",
        description="Product/character/light/location/last-frame anchor that keeps longer films coherent",
    )
    feed_storyboard_seed: bool = Field(
        default=False,
        description="Whether to feed generated storyboard as the Seedance seed. Default false.",
    )


class VideoScript(BaseModel):
    """Complete script: global story, storyboard references, and render segments."""

    title: str = Field(description="Working title")
    aspect_ratio: str = Field(default="9:16", description="Inherited from Requirement")
    global_narrative: GlobalNarrative = Field(default_factory=GlobalNarrative)
    shots: list[Shot] = Field(description="Storyboard micro-shots in timeline order")
    segments: list[RenderSegment] = Field(default_factory=list, description="Actual render units")
    bgm_direction: str = Field(default="", description="Executable music direction")

    @property
    def total_duration_sec(self) -> float:
        """Preferred total duration.

        New scripts use segments as the execution timeline; legacy scripts fall
        back to the storyboard shot durations.
        """
        if self.segments:
            return sum(s.duration_sec for s in self.segments)
        return sum(s.duration_sec for s in self.shots)
