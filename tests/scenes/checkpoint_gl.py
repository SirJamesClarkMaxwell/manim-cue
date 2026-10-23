"""Panel GL checkpointów F5g."""

from checkpoint_panel import CheckpointPanel, GraphCheckpointPanel
from manimlib import Group, Square

from manimcue.live_scene import LiveScene


class Panel(CheckpointPanel, LiveScene):
    square_type = Square


class GraphPanel(GraphCheckpointPanel, LiveScene):
    square_type = Square
    group_type = Group
