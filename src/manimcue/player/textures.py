"""Trwałe zasoby OpenGL; nowy upload nie nadpisuje przypiętego snapshotu."""

from dataclasses import dataclass


def _gl():
    import OpenGL

    # Sprawdzanie błędów po każdym wywołaniu PyOpenGL kosztowało ok. 1,4 ms na tick;
    # działa tylko przed pierwszym importem OpenGL.GL, błąd uploadu sprawdza _check.
    OpenGL.ERROR_CHECKING = False
    from OpenGL import GL

    return GL


def _drain(GL):
    """Odrzuć błędy zgłoszone wcześniej przez inny kod w tym kontekście."""
    for _ in range(16):
        if GL.glGetError() == GL.GL_NO_ERROR:
            break


def _check(GL):
    error = GL.glGetError()
    if error != GL.GL_NO_ERROR:
        raise RuntimeError(f"Błąd OpenGL 0x{error:04x} przy uploadzie tekstury")


def _validate(frame, width, height):
    if width <= 0 or height <= 0 or len(frame["rgba"]) != width * height * 4:
        raise ValueError("Niepoprawny bufor RGBA8")
    if frame.get("stride", 4 * width) != 4 * width:
        raise ValueError("Wymagany zwarty bufor RGBA8")


@dataclass
class TextureLease:
    """Własność jednej tekstury do końca wykonania draw data obu viewportów."""

    texture: int
    width: int
    height: int
    closed: bool = False

    def close(self):
        """Zwolnij w bieżącym kontekście GL po zakończeniu renderowania."""
        GL = _gl()
        if not self.closed:
            GL.glDeleteTextures([self.texture])
            self.closed = True

    def update(self, frame) -> None:
        """Nowa treść tego samego obiektu; draw data poprzedniej iteracji jest już w GL.

        glTexImage2D, nie glTexSubImage2D: sterownik daje nową pamięć zamiast czekać na GPU,
        które jeszcze czyta poprzednią klatkę (SubImage dawało p95 14 ms przy vsync).
        """
        GL = _gl()
        if (frame["width"], frame["height"]) != (self.width, self.height):
            raise ValueError("Inny rozmiar klatki niż tekstury")
        _validate(frame, self.width, self.height)
        _drain(GL)
        old = int(GL.glGetIntegerv(GL.GL_TEXTURE_BINDING_2D))
        alignment = int(GL.glGetIntegerv(GL.GL_UNPACK_ALIGNMENT))
        try:
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D,
                0,
                GL.GL_RGBA8,
                self.width,
                self.height,
                0,
                GL.GL_RGBA,
                GL.GL_UNSIGNED_BYTE,
                frame["rgba"],
            )
            _check(GL)
        finally:
            GL.glBindTexture(GL.GL_TEXTURE_2D, old)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, alignment)


def upload(frame) -> TextureLease:
    """Wgraj owned RGBA8 top-left do nowego zasobu zamiast mutacji starego."""
    GL = _gl()
    width, height, pixels = frame["width"], frame["height"], frame["rgba"]
    _validate(frame, width, height)
    _drain(GL)
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
        _check(GL)
    except BaseException:
        lease.close()
        raise
    finally:
        GL.glBindTexture(GL.GL_TEXTURE_2D, old)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, alignment)
    return lease
