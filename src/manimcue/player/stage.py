"""Kompozycja kadru i warstw bez adapterów platformy."""

from .geometry import clip, fit, layer_box, rect_at


def compose(manifest: dict, frames: dict, now: float) -> list[dict]:
    """Zbuduj snapshot draw commands; klatki zawierają trwałe uchwyty tekstur."""
    width, height = manifest["resolution"]
    viewport = tuple(manifest.get("viewport", (0, 0, width, height)))
    frame = viewport if manifest.get("aspect_ratio") == "ignore" else fit(width / height, viewport)
    commands = [
        {
            "type": "fill",
            "box": viewport,
            "color": manifest.get("background", [0, 0, 0, 1]),
            "clip": viewport,
        }
    ]
    slide = manifest.get("slide", manifest)
    active_key = next((key for key, source in frames.items() if source.get("active")), None)
    error_key = next(
        (
            str(index)
            for index, layer in enumerate(slide.get("layers", []))
            if layer["kind"] == "live" and frames.get(str(index), {}).get("error")
        ),
        None,
    )
    media = [("base", slide, (0, 0, 1, 1))]
    media += [
        (str(index), layer, rect_at(layer, float("inf") if manifest.get("reverse") else now))
        for index, layer in enumerate(slide.get("layers", []))
    ]
    for key, layer, rect in media:
        box = layer_box(frame, rect)
        visible = clip(box, frame)
        if visible[2] <= 0 or visible[3] <= 0:
            continue
        source = frames.get(key, {})
        image_box = box
        if layer.get("kind") != "live" and source.get("width") and source.get("height"):
            image_box = fit(source["width"] / source["height"], box)
        command = {
            "type": "image" if source.get("texture") is not None else "placeholder",
            "texture": source.get("texture"),
            "box": image_box,
            "container": box,
            "uv": (0, 0, 1, 1),
            "clip": visible,
            # Krycie tła kamery jest już zawarte w RGBA workera (D34).
            "color": [1, 1, 1, 1],
            "source": key,
        }
        commands.append(command)
        role = (
            "active"
            if key == active_key
            else "error"
            if active_key is None and key == error_key
            else None
        )
        border = layer.get(f"{role}_border") if role else None
        if border:
            color = list(border.get("color", [1, 200 / 255, 0, 1]))
            color[3] *= border.get("opacity", 1)
            thickness = min(border.get("width", 6) * frame[2] / width, box[2] / 2, box[3] / 2)
            commands.append(
                {"type": "border", "box": box, "clip": visible, "color": color, "width": thickness}
            )
    return commands


def draw(commands: list, draw_list) -> None:
    """Wyemituj geometrię z prostą alfą; clipping odbywa się w logicznych pikselach."""
    from imgui_bundle import imgui

    for command in commands:
        x, y, w, h = command["box"]
        cx, cy, cw, ch = command["clip"]
        draw_list.push_clip_rect(imgui.ImVec2(cx, cy), imgui.ImVec2(cx + cw, cy + ch), True)
        color = imgui.color_convert_float4_to_u32(imgui.ImVec4(*command["color"]))
        a, b = imgui.ImVec2(x, y), imgui.ImVec2(x + w, y + h)
        if command["type"] == "image":
            draw_list.add_image(
                imgui.ImTextureRef(command["texture"]),
                a,
                b,
                imgui.ImVec2(0, 0),
                imgui.ImVec2(1, 1),
                color,
            )
        elif command["type"] == "border":
            t = command["width"]
            for bx, by, bw, bh in [
                (x, y, w, t),
                (x, y + h - t, w, t),
                (x, y + t, t, h - 2 * t),
                (x + w - t, y + t, t, h - 2 * t),
            ]:
                draw_list.add_rect_filled(
                    imgui.ImVec2(bx, by), imgui.ImVec2(bx + bw, by + bh), color
                )
        else:
            draw_list.add_rect_filled(a, b, color if command["type"] == "fill" else 0xFF555555)
        draw_list.pop_clip_rect()
