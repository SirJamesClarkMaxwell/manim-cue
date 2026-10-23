import json
import math
import mimetypes
import shutil
from collections.abc import Callable
from enum import Enum
from functools import wraps
from itertools import pairwise
from inspect import Parameter, signature
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Any, Literal

import rtoml
from pydantic import (
    BaseModel,
    Field,
    FilePath,
    PositiveInt,
    PrivateAttr,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_extra_types.color import Color

from .logger import logger

Receiver = Callable[..., Any]


class SlideType(Enum):
    """Enumeration of slide types."""

    Video = "video"
    Image = "image"


class Signal(BaseModel):
    __receivers: list[Receiver] = PrivateAttr(default_factory=list)

    def connect(self, receiver: Receiver) -> None:
        self.__receivers.append(receiver)

    def disconnect(self, receiver: Receiver) -> None:
        self.__receivers.remove(receiver)

    def emit(self, *args: Any) -> None:
        for receiver in self.__receivers:
            receiver(*args)


def key_id(name: str) -> PositiveInt:
    """Avoid importing Qt too early; default keys resolve without Qt."""
    from manimcue.player.keys import QT_KEYS

    if name in QT_KEYS:
        return QT_KEYS[name]
    from qtpy.QtCore import Qt

    return getattr(Qt, f"Key_{name}")


class Key(BaseModel):
    """Represents a list of key codes, with optionally a name."""

    ids: Annotated[set[PositiveInt], Field(min_length=1)]
    name: str | None = None

    __signal: Signal = PrivateAttr(default_factory=Signal)

    def set_ids(self, *ids: int) -> None:
        self.ids = set(ids)

    def match(self, key_id: int) -> bool:
        m = key_id in self.ids

        if m:
            logger.debug(f"Pressed key: {self.name}")

        return m

    @property
    def signal(self) -> Signal:
        return self.__signal

    def connect(self, function: Receiver) -> None:
        self.__signal.connect(function)

    @field_serializer("ids")
    def serialize_dt(self, ids: set[int]) -> list[int]:
        return list(self.ids)


class Keys(BaseModel):
    QUIT: Key = Field(default_factory=lambda: Key(ids=[key_id("Q")], name="QUIT"))
    PLAY_PAUSE: Key = Field(
        default_factory=lambda: Key(ids=[key_id("Space")], name="PLAY / PAUSE")
    )
    NEXT: Key = Field(default_factory=lambda: Key(ids=[key_id("Right")], name="NEXT"))
    PREVIOUS: Key = Field(
        default_factory=lambda: Key(ids=[key_id("Left")], name="PREVIOUS")
    )
    REVERSE: Key = Field(default_factory=lambda: Key(ids=[key_id("V")], name="REVERSE"))
    REPLAY: Key = Field(default_factory=lambda: Key(ids=[key_id("R")], name="REPLAY"))
    FULL_SCREEN: Key = Field(
        default_factory=lambda: Key(ids=[key_id("F")], name="TOGGLE FULL SCREEN")
    )
    HIDE_MOUSE: Key = Field(
        default_factory=lambda: Key(ids=[key_id("H")], name="HIDE / SHOW MOUSE")
    )

    PRESENTER_STATE: Key = Field(
        default_factory=lambda: Key(ids=[key_id("S")], name="PRESENTER STATE")
    )

    @model_validator(mode="after")
    def effective_ids_are_unique(self):
        """Sprawdza także domyślne klawisze pominięte w pliku użytkownika."""
        seen = set()
        for _, key in self:
            if seen.intersection(key.ids):
                raise ValueError("Two or more keys share a common key code")
            seen.update(key.ids)
        return self

    @model_validator(mode="before")
    @classmethod
    def ids_are_unique_across_keys(
        cls, values: dict[str, "Key | dict[str, Any]"]
    ) -> dict[str, "Key | dict[str, Any]"]:
        ids: set[int] = set()

        for key in values.values():
            key_ids = key.ids if isinstance(key, Key) else key["ids"]

            if len(ids.intersection(key_ids)) != 0:
                raise ValueError(
                    "Two or more keys share a common key code: please make sure each key has distinct key codes"
                )
            ids.update(key_ids)

        return values

    def merge_with(self, other: "Keys") -> "Keys":
        merged = self.model_copy(deep=True)
        for key_name, key in merged:
            other_key = getattr(other, key_name)
            key.ids = list(set(key.ids).union(other_key.ids))
            key.name = other_key.name or key.name

        merged.effective_ids_are_unique()
        for key_name, key in merged:
            getattr(self, key_name).ids = set(key.ids)
            getattr(self, key_name).name = key.name
        return self

    def dispatch_key_function(self) -> Callable[[PositiveInt], None]:
        _dispatch = {}

        for _, key in self:
            for _id in key.ids:
                _dispatch[_id] = key.signal

        def dispatch(key: PositiveInt) -> None:
            if signal := _dispatch.get(key, None):
                signal.emit()

        return dispatch


class Config(BaseModel):
    """General Manim Slides config."""

    keys: Keys = Field(default_factory=Keys)

    @classmethod
    def from_file(cls, path: Path) -> "Config":
        """Read a configuration from a file."""
        return cls.model_validate(rtoml.load(path))

    def to_file(self, path: Path) -> None:
        """Dump the configuration to a file."""
        rtoml.dump(self.model_dump(), path, pretty=True)

    def merge_with(self, other: "Config") -> "Config":
        """Merge with another config."""
        self.keys = self.keys.merge_with(other.keys)
        return self


FORMAT_VERSION = 4
"""Wersja formatu JSON: 1 — upstream 5.7.0 bez pola, 2 — warstwy live (F3, D24),
3 — warstwy z plików, `kind` i klatki kluczowe (F5, D29), 4 — jawny silnik live (D36)."""

Rect = tuple[float, float, float, float]
"""(x, y, szerokość, wysokość) jako ułamki kadru slajdu, (0, 0) w lewym górnym rogu."""


def check_rect(rect: Rect, inside: bool) -> Rect:
    """Skończony prostokąt o dodatnich wymiarach; ``inside`` — dodatkowo cały w kadrze."""
    x, y, w, h = rect
    eps = 1e-9
    if not all(map(math.isfinite, rect)) or w <= 0 or h <= 0:
        raise ValueError(f"rect {rect} musi mieć skończone liczby i dodatnie wymiary")
    if inside and (x < 0 or y < 0 or x + w > 1 + eps or y + h > 1 + eps):
        raise ValueError(f"rect {rect} musi leżeć w kadrze (ułamki 0..1)")
    return rect


class Keyframe(BaseModel):
    """Prostokąt warstwy w chwili ``t`` aktywnego czasu slajdu (F5, D30); poza kadrem wolno."""

    t: float
    rect: Rect

    @field_validator("t")
    @classmethod
    def t_is_time(cls, t: float) -> float:
        if not math.isfinite(t) or t < 0:
            raise ValueError(f"t={t} musi być skończone i nieujemne")
        return t

    @field_validator("rect")
    @classmethod
    def rect_is_valid(cls, rect: Rect) -> Rect:
        return check_rect(rect, inside=False)


class LayerBase(BaseModel):
    """Wspólne dla warstw: klatki kluczowe ruchu (D30), ściśle rosnące w czasie."""

    keyframes: list[Keyframe] = []

    @field_validator("keyframes")
    @classmethod
    def keyframes_increase(cls, keyframes: list[Keyframe]) -> list[Keyframe]:
        if any(b.t <= a.t for a, b in pairwise(keyframes)):
            raise ValueError("czasy klatek kluczowych muszą ściśle rosnąć")
        return keyframes

    def rect_at(self, t: float) -> Rect:
        """Prostokąt w chwili ``t``: liniowo między klatkami kluczowymi, poza nimi — stały."""
        frames = [Keyframe(t=0, rect=self.rect)] if not self.keyframes else self.keyframes
        if t <= frames[0].t:
            return frames[0].rect
        for a, b in pairwise(frames):
            if t <= b.t:
                k = (t - a.t) / (b.t - a.t)
                return tuple(p + k * (q - p) for p, q in zip(a.rect, b.rect, strict=True))
        return frames[-1].rect

    def describe(self) -> str:
        raise NotImplementedError


class BorderStyle(BaseModel):
    """Styl jednej obwódki; alfa koloru mnoży się przez krycie."""

    color: Color = Color("#ffc800")
    width: float = Field(default=6.0, gt=0, allow_inf_nan=False)
    opacity: float = Field(default=1.0, ge=0, le=1, allow_inf_nan=False)


class LiveLayer(LayerBase):
    """Warstwa live slajdu (F3, D24): scena `LiveScene` w prostokącie kadru.

    ``rect`` wyznacza rozdzielczość renderu, więc leży w kadrze; ruch (``keyframes``) tylko
    skaluje obraz. ``thumbnail`` wypełnia render: pierwsza klatka sceny.
    """

    kind: Literal["live"] = "live"
    scene_file: FilePath
    scene_name: str
    rect: Rect = (0.0, 0.0, 1.0, 1.0)
    fps: PositiveInt = 60
    session_id: str | None = None
    background_opacity: float = Field(default=1.0, ge=0, le=1, allow_inf_nan=False)
    active_border: BorderStyle | None = BorderStyle()
    error_border: BorderStyle | None = BorderStyle(color="#dc2828")
    engine: Literal["manimgl", "ce-cairo"] = "manimgl"
    enter_cue: str | None = None
    thumbnail: FilePath | None = None

    @field_validator("enter_cue")
    @classmethod
    def cue_is_line(cls, cue: str | None) -> str | None:
        if cue is not None and (not cue.strip() or "\n" in cue or "\r" in cue):
            raise ValueError("enter_cue musi być niepustą pojedynczą linią")
        return cue

    @field_validator("rect")
    @classmethod
    def rect_inside_frame(cls, rect: Rect) -> Rect:
        return check_rect(rect, inside=True)

    def size(self, resolution: tuple[int, int]) -> tuple[int, int]:
        """Rozdzielczość procesu live: prostokąt warstwy w pikselach prezentacji."""
        width, height = resolution
        return max(1, round(self.rect[2] * width)), max(1, round(self.rect[3] * height))

    def describe(self) -> str:
        return self.scene_name


class ClipLayer(LayerBase):
    """Warstwa z pliku (F5, D29): klip wideo albo obraz, np. render innej sceny.

    Prostokąt może wychodzić poza kadr (wjazd). ``thumbnail`` i ``end_thumbnail`` — pierwsza
    i ostatnia klatka z renderu (podgląd, reverse); dla obrazu to sam plik.
    """

    kind: Literal["clip"] = "clip"
    file: FilePath
    rect: Rect = (0.0, 0.0, 1.0, 1.0)
    loop: bool = False
    playback_rate: float = 1.0
    thumbnail: FilePath | None = None
    end_thumbnail: FilePath | None = None

    @field_validator("rect")
    @classmethod
    def rect_is_valid(cls, rect: Rect) -> Rect:
        return check_rect(rect, inside=False)

    @field_validator("playback_rate")
    @classmethod
    def rate_is_positive(cls, rate: float) -> float:
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError(f"playback_rate={rate} musi być skończone i dodatnie")
        return rate

    @property
    def is_video(self) -> bool:
        """Wideo grające w grupie; GIF i obrazy są statyczne (GIF — pierwsza klatka)."""
        guessed = mimetypes.guess_type(self.file)[0] or ""
        return guessed.startswith("video")

    def describe(self) -> str:
        return Path(self.file).name


Layer = Annotated[LiveLayer | ClipLayer, Field(discriminator="kind")]


class BaseSlideConfig(BaseModel):
    """Base class for slide config."""

    loop: bool = False
    auto_next: bool = False
    playback_rate: float = 1.0
    reversed_playback_rate: float = 1.0
    notes: str = ""
    dedent_notes: bool = True
    skip_animations: bool = False
    src: FilePath | None = None
    type: SlideType = SlideType.Video
    direction: Literal["horizontal", "vertical"] = "horizontal"
    # Zwykła wartość domyślna, nie default_factory: wrapper wpisuje `default` do sygnatury
    # next_slide, a pydantic i tak kopiuje listę dla każdej instancji.
    layers: list[Layer] = []

    @model_validator(mode="after")
    def determine_slide_type(self) -> "BaseSlideConfig":
        """Determine the type of src."""
        if self.src is not None:
            guessed_typed = mimetypes.guess_type(self.src)[0]
            if guessed_typed is None:
                logger.warning(
                    f"The file type of 'src' ({str(self.src)!r}) could not be guessed. Defaulting to video type.",
                )
                self.type = SlideType.Video
            elif guessed_typed.startswith("image"):
                self.type = SlideType.Image
            elif guessed_typed.startswith("video"):
                self.type = SlideType.Video
            else:
                logger.warning(
                    f"The file type of 'src' ({str(self.src)!r}) is guessed as {guessed_typed!r}, which is not recognized or currently supported. Defaulting to video type.",
                )
                self.type = SlideType.Video
        return self

    @classmethod
    def wrapper(cls, arg_name: str) -> Callable[..., Any]:
        """
        Wrap a function to transform keyword argument into an instance of this class.

        The function signature is updated to reflect the new keyword-only arguments.

        The wrapped function must follow two criteria:
        - its last parameter must be ``**kwargs`` (or equivalent);
        - and its second last parameter must be ``<arg_name>``.
        """

        def _wrapper_(fun: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(fun)
            def __wrapper__(*args: Any, **kwargs: Any) -> Any:  # noqa: N807
                fun_kwargs = {
                    key: value
                    for key, value in kwargs.items()
                    if key not in cls.model_fields
                }
                fun_kwargs[arg_name] = cls(**kwargs)
                return fun(*args, **fun_kwargs)

            sig = signature(fun)
            parameters = list(sig.parameters.values())
            parameters[-2:-1] = [
                Parameter(
                    field_name,
                    Parameter.KEYWORD_ONLY,
                    default=field_info.default,
                    annotation=field_info.annotation,
                )
                for field_name, field_info in cls.model_fields.items()
            ]

            sig = sig.replace(parameters=parameters)
            __wrapper__.__signature__ = sig  # ty: ignore[unresolved-attribute]

            return __wrapper__

        return _wrapper_

    @model_validator(mode="after")
    def apply_dedent_notes(
        self,
    ) -> "BaseSlideConfig":
        if self.dedent_notes:
            self.notes = dedent(self.notes)

        return self


class PreSlideConfig(BaseSlideConfig):
    """Slide config to be used prior to rendering."""

    start_animation: int
    end_animation: int

    @classmethod
    def from_base_slide_config_and_animation_indices(
        cls,
        base_slide_config: BaseSlideConfig,
        start_animation: int,
        end_animation: int,
    ) -> "PreSlideConfig":
        return cls(
            start_animation=start_animation,
            end_animation=end_animation,
            **base_slide_config.model_dump(),
        )

    @field_validator("start_animation", "end_animation")
    @classmethod
    def index_is_posint(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Animation index (start or end) cannot be negative")
        return v

    @model_validator(mode="after")
    def start_animation_is_before_end(
        self,
    ) -> "PreSlideConfig":
        if self.start_animation > self.end_animation:
            raise ValueError(
                "Start animation index must be strictly lower than end animation index"
            )
        return self

    @model_validator(mode="after")
    def has_src_or_more_than_zero_animations(
        self,
    ) -> "PreSlideConfig":
        if self.src is not None and self.start_animation != self.end_animation:
            raise ValueError(
                "A slide cannot have 'src=...' and more than zero animations at the same time."
            )
        elif self.src is None and self.start_animation == self.end_animation:
            raise ValueError(
                "You have to play at least one animation (e.g., 'self.wait()') "
                "before pausing. If you want to start paused, use the appropriate "
                "command-line option when presenting. "
                "IMPORTANT: when using ManimGL, 'self.wait()' is not considered "
                "to be an animation, so prefer to directly use 'self.play(...)'."
            )

        return self

    @property
    def slides_slice(self) -> slice:
        return slice(self.start_animation, self.end_animation)


class SlideConfig(BaseSlideConfig):
    """Slide config to be used after rendering."""

    file: FilePath
    rev_file: FilePath

    @classmethod
    def from_pre_slide_config_and_files(
        cls, pre_slide_config: PreSlideConfig, file: Path, rev_file: Path
    ) -> "SlideConfig":
        return cls(file=file, rev_file=rev_file, **pre_slide_config.model_dump())


def check_no_layers(presentation_configs: list["PresentationConfig"]) -> None:
    """D23: warstwy (live i z plików) nie mają odpowiednika w eksporcie — błąd, nie cicha utrata.

    Prezentację wskazuje numer: ``convert`` bez nazw scen wybiera je z promptu.
    """
    for number, presentation_config in enumerate(presentation_configs, start=1):
        for index, slide_config in enumerate(presentation_config.slides, start=1):
            if slide_config.layers:
                names = ", ".join(layer.describe() for layer in slide_config.layers)
                raise ValueError(
                    f"Prezentacja {number}, slajd {index}: warstwy ({names}); "
                    "eksport do plików nie obsługuje warstw"
                )


def slide_file(json_path: Path | str, index: int) -> Path:
    """Plik bazowy slajdu ``index`` (od 0) innego, wcześniej wyrenderowanego decku (D29).

    Nazwy klipów to hashe, więc warstwa-render innej sceny wskazuje je przez JSON; bez warstw
    tamtego slajdu. Ponowny render źródłowego decku może zmienić wynik.
    """
    return PresentationConfig.from_file(Path(json_path)).slides[index].file.resolve()


class PresentationConfig(BaseModel):
    version: int = FORMAT_VERSION
    slides: list[SlideConfig] = Field(min_length=1)
    resolution: tuple[PositiveInt, PositiveInt] = (1920, 1080)
    background_color: Color = Color("black")

    @model_validator(mode="after")
    def validate_live_runs(self) -> "PresentationConfig":
        """Spójność sąsiednich wystąpień sesji; przerwa otwiera nową generację."""
        previous = {}
        for index, slide in enumerate(self.slides, start=1):
            current = {}
            for layer in slide.layers:
                if not isinstance(layer, LiveLayer) or layer.session_id is None:
                    continue
                session_id = layer.session_id
                if session_id in current:
                    raise ValueError(f"slajd {index}: duplikat session_id={session_id!r}")
                identity = (layer.scene_file.resolve(), layer.scene_name, layer.fps,
                            layer.size(self.resolution), layer.background_opacity, layer.engine)
                if session_id in previous and previous[session_id][1] != identity:
                    raise ValueError(
                        f"slajdy {index - 1}, {index}: niespójna sesja {session_id!r}"
                    )
                current[session_id] = (index, identity)
            previous = current
        return self

    @field_validator("version")
    @classmethod
    def version_is_known(cls, version: int) -> int:
        # Starszy fork zignorowałby nieznane pola po cichu, więc nowszy format to błąd.
        if version > FORMAT_VERSION:
            raise ValueError(
                f"Plik w formacie {version}, nowszym niż obsługiwany ({FORMAT_VERSION}); "
                "zaktualizuj manim-cue"
            )
        return version

    @classmethod
    def from_file(cls, path: Path) -> "PresentationConfig":
        """Read a presentation configuration from a file."""
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)

            slides = obj.setdefault("slides", [])
            parent = path.parent.parent  # Never fails, but parents[1] can fail

            for slide in slides:
                if file := slide.get("file", None):
                    slide["file"] = parent / file

                if rev_file := slide.get("rev_file", None):
                    slide["rev_file"] = parent / rev_file

                # F3: ścieżki warstw względem tego samego katalogu co klipy. F5: plik v2 nie
                # ma `kind`, a unia dyskryminowana go wymaga — warstwy v2 to zawsze live.
                for layer in slide.get("layers", []):
                    layer.setdefault("kind", "live")
                    if obj.get("version", 2) < 4 and layer["kind"] == "live":
                        layer["engine"] = "manimgl"
                    for key in ("scene_file", "thumbnail", "file", "end_thumbnail"):
                        if value := layer.get(key):
                            layer[key] = parent / value

            return cls.model_validate(obj)

    def to_file(self, path: Path) -> None:
        """Dump the presentation configuration to a file."""
        # F5: zawsze bieżąca wersja — dokument v2 rozszerzony o klip nie może zostać „v2”.
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_copy(update={"version": FORMAT_VERSION}).model_dump_json(indent=2))

    def copy_to(
        self,
        folder: Path,
        use_cached: bool = True,
        include_reversed: bool = True,
        prefix: str = "",
    ) -> None:
        """Copy the files to a given directory."""
        # Runda 8: kopia samych klipów zgubiłaby scenę i miniaturę warstwy.
        check_no_layers([self])
        for slide_config in self.slides:
            file = slide_config.file
            rev_file = slide_config.rev_file

            dest = folder / f"{prefix}{file.name}"
            rev_dest = folder / f"{prefix}{rev_file.name}"

            if not use_cached or not dest.exists():
                shutil.copy(file, dest)

            if include_reversed and (not use_cached or not rev_dest.exists()):
                shutil.copy(rev_file, rev_dest)
