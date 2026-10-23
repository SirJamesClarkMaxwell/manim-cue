"""Geometria draw data i trwałość zasobów kompozycji."""

import pytest
from imgui_bundle import imgui

from manimcue.player.geometry import hit_test
from manimcue.player.stage import compose, draw


@pytest.fixture
def context():
    context = imgui.create_context()
    io = imgui.get_io()
    io.display_size = imgui.ImVec2(400, 400)
    io.delta_time = 1 / 60
    io.set_ini_filename(None)
    io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
    yield context
    imgui.destroy_context(context)


def fixture_manifest():
    return {
        "resolution": [200, 100],
        "viewport": [0, 0, 400, 400],
        "slide": {
            "kind": "image",
            "layers": [
                {
                    "kind": "live",
                    "rect": [-0.1, 0, 0.5, 1],
                    "active_border": {"width": 6, "color": [1, 0, 0, 0.5], "opacity": 0.5},
                }
            ],
        },
    }


def test_composition_geometry_alpha_border_hit_margin():
    commands = compose(fixture_manifest(), {"0": {"texture": 11, "active": True}}, 0)
    layer, border = commands[-2:]
    assert layer["box"] == (-40, 100, 200, 200)
    assert layer["clip"] == (0, 100, 160, 200)
    assert layer["uv"] == (0, 0, 1, 1)
    assert border["width"] == 12 and border["color"][3] == 0.25
    assert hit_test(commands, (0, 110)) == "0"
    assert hit_test(commands, (170, 110)) == "base"


def test_draw_data_vertices_uv_clip(context):
    imgui.new_frame()
    # Protokół tekstur ImGui 1.92+, bez nieistniejącego fonts.build().
    for texture in imgui.get_platform_io().textures:
        if texture.status == imgui.ImTextureStatus.want_create:
            texture.set_tex_id(99)
            texture.set_status(imgui.ImTextureStatus.ok)
    commands = compose(fixture_manifest(), {"base": {"texture": 10}, "0": {"texture": 11}}, 0)
    draw(commands, imgui.get_background_draw_list())
    imgui.render()
    data = imgui.get_draw_data()
    assert data.total_vtx_count >= 12 and data.total_idx_count >= 18
    vertices = [vertex for batch in data.cmd_lists for vertex in batch.vtx_buffer]
    assert any(vertex.pos.x == -40 and vertex.pos.y == 100 for vertex in vertices)
    assert any(vertex.uv.x == 1 and vertex.uv.y == 1 for vertex in vertices)
    clips = [tuple(command.clip_rect) for batch in data.cmd_lists for command in batch.cmd_buffer]
    assert (0, 100, 160, 300) in clips


@pytest.mark.gpu
def test_texture_upload_owned_rgba():
    import moderngl
    from OpenGL import GL

    from manimcue.player.textures import upload

    context = moderngl.create_standalone_context()
    try:
        frame = {"width": 2, "height": 1, "rgba": bytes((255, 0, 0, 128, 0, 255, 0, 255))}
        first = upload(frame)
        second = upload({**frame, "rgba": bytes(8)})
        try:
            assert first.texture != second.texture
            GL.glBindTexture(GL.GL_TEXTURE_2D, first.texture)
            pixels = GL.glGetTexImage(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            assert bytes(pixels) == frame["rgba"]
        finally:
            second.close()
            first.close()
    finally:
        context.release()


@pytest.mark.gpu
def test_render_pixels_straight_alpha_and_clip(context):
    from array import array

    import moderngl

    gl = moderngl.create_standalone_context()
    blue = gl.texture((1, 1), 4, bytes((0, 0, 255, 255)))
    red = gl.texture((1, 1), 4, bytes((255, 0, 0, 128)))
    target = gl.simple_framebuffer((400, 400), components=4)
    program = gl.program(
        vertex_shader="""#version 330
in vec2 position; in vec2 uv; in vec4 color;
out vec2 tex_uv; out vec4 tint;
void main() { gl_Position=vec4(position.x/200.-1., 1.-position.y/200., 0., 1.); tex_uv=uv; tint=color; }
""",
        fragment_shader="""#version 330
uniform sampler2D image; in vec2 tex_uv; in vec4 tint; out vec4 pixel;
void main() { pixel=texture(image, tex_uv)*tint; }
""",
    )
    try:
        target.use()
        target.clear(0, 0, 0, 1)
        gl.enable(moderngl.BLEND)
        gl.blend_func = (
            moderngl.SRC_ALPHA,
            moderngl.ONE_MINUS_SRC_ALPHA,
            moderngl.ONE,
            moderngl.ONE_MINUS_SRC_ALPHA,
        )
        imgui.new_frame()
        for texture in imgui.get_platform_io().textures:
            if texture.status == imgui.ImTextureStatus.want_create:
                texture.set_tex_id(99999)
                texture.set_status(imgui.ImTextureStatus.ok)
        commands = compose(
            fixture_manifest(), {"base": {"texture": blue.glo}, "0": {"texture": red.glo}}, 0
        )
        draw(commands, imgui.get_background_draw_list())
        imgui.render()
        for texture in imgui.get_platform_io().textures:
            if texture.status == imgui.ImTextureStatus.want_create:
                texture.set_tex_id(99999)
                texture.set_status(imgui.ImTextureStatus.ok)
        textures = {blue.glo: blue, red.glo: red}
        for batch in imgui.get_draw_data().cmd_lists:
            for command in batch.cmd_buffer:
                texture = textures.get(command.get_tex_id())
                if texture is None:
                    continue
                values = array("f")
                indices = list(batch.idx_buffer)[
                    command.idx_offset : command.idx_offset + command.elem_count
                ]
                for index in indices:
                    vertex = batch.vtx_buffer[index + command.vtx_offset]
                    color = [(vertex.col >> shift & 255) / 255 for shift in (0, 8, 16, 24)]
                    values.extend([vertex.pos.x, vertex.pos.y, vertex.uv.x, vertex.uv.y, *color])
                buffer = gl.buffer(values.tobytes())
                vao = gl.vertex_array(program, [(buffer, "2f 2f 4f", "position", "uv", "color")])
                left, top, right, bottom = command.clip_rect
                gl.scissor = (int(left), 400 - int(bottom), int(right - left), int(bottom - top))
                texture.use()
                vao.render(moderngl.TRIANGLES)
                vao.release()
                buffer.release()
        gl.scissor = None
        pixels = target.read(components=4)

        def pixel(x, y):
            offset = ((399 - y) * 400 + x) * 4
            return pixels[offset : offset + 4]

        assert all(abs(a - b) <= 1 for a, b in zip(pixel(10, 150), (128, 0, 127, 255)))
        assert pixel(200, 150) == bytes((0, 0, 255, 255))
        assert pixel(10, 50) == bytes((0, 0, 0, 255))
    finally:
        program.release()
        target.release()
        red.release()
        blue.release()
        gl.release()


def test_previous_image_held_until_new_entry_ready():
    from itertools import count
    from types import SimpleNamespace

    from test_imgui_info import FakeSource

    from manimcue.player.app import App

    class SlowSource(FakeSource):
        released = False

        def poll(self, now, target, budget_ms):
            if self.media["file"] == "second" and not SlowSource.released:
                return {"status": "preparing"}
            return super().poll(now, target, budget_ms)

    textures, closed = count(1), set()

    def uploader(update):
        texture = next(textures)
        return SimpleNamespace(texture=texture, close=lambda: closed.add(texture))

    slides = [{"kind": "image", "file": "first"}, {"kind": "image", "file": "second"}]
    data = {"version": 1, "resolution": [100, 100], "presentations": [{"slides": slides}]}
    app = App(data, {"show_info": False}, SlowSource, uploader)
    now = app.started_at

    def shown():
        app.after_render()
        return [command["texture"] for command in app.composition if command["type"] != "fill"]

    app.tick(now)
    assert shown() == [1] and not app.state["preparing"]
    app.dispatch({"type": "next"}, now + 1)
    app.tick(now + 1.1)
    # Dekoder nowego slajdu jeszcze startuje: zamiast placeholdera ostatni obraz poprzedniego.
    assert app.state["preparing"] and shown() == [1] and not closed
    SlowSource.released = True
    app.tick(now + 1.2)
    assert not app.state["preparing"] and shown() == [2] and closed == {1}
