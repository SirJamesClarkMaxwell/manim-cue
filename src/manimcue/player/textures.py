"""Trwałe zasoby OpenGL; nowy upload nie nadpisuje przypiętego snapshotu."""

from dataclasses import dataclass


@dataclass
class TextureLease:
    """Własność jednej tekstury do końca wykonania draw data obu viewportów."""

    texture: int
    width: int
    height: int
    closed: bool = False

    def close(self):
        """Zwolnij w bieżącym kontekście GL po zakończeniu renderowania."""
        from OpenGL import GL

        if not self.closed:
            GL.glDeleteTextures([self.texture])
            self.closed = True


def upload(frame) -> TextureLease:
    """Wgraj owned RGBA8 top-left do nowego zasobu zamiast mutacji starego."""
    from OpenGL import GL

    width, height, pixels = frame["width"], frame["height"], frame["rgba"]
    if width <= 0 or height <= 0 or len(pixels) != width * height * 4:
        raise ValueError("Niepoprawny bufor RGBA8")
    if frame.get("stride", 4 * width) != 4 * width:
        raise ValueError("Wymagany zwarty bufor RGBA8")
    texture = int(GL.glGenTextures(1))
    lease = TextureLease(texture, width, height)
    old = int(GL.glGetIntegerv(GL.GL_TEXTURE_BINDING_2D))
    alignment = int(GL.glGetIntegerv(GL.GL_UNPACK_ALIGNMENT))
    try:
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        for setting in (GL.GL_TEXTURE_MIN_FILTER, GL.GL_TEXTURE_MAG_FILTER):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, setting, GL.GL_LINEAR)
        for setting in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, setting, GL.GL_CLAMP_TO_EDGE)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            GL.GL_RGBA8,
            width,
            height,
            0,
            GL.GL_RGBA,
            GL.GL_UNSIGNED_BYTE,
            pixels,
        )
    except BaseException:
        lease.close()
        raise
    finally:
        GL.glBindTexture(GL.GL_TEXTURE_2D, old)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, alignment)
    return lease
