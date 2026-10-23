"""Panel CE checkpointów F5g."""

from checkpoint_panel import CheckpointPanel, GraphCheckpointPanel
from manim import Square, VGroup

from manimcue.live_scene_ce import LiveSceneCE


class Panel(CheckpointPanel, LiveSceneCE):
    square_type = Square


class GraphPanel(GraphCheckpointPanel, LiveSceneCE):
    square_type = Square
    group_type = VGroup
