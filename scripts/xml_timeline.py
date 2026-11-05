"""Write a montage plan as an FCP7 XML (xmeml) timeline.

Premiere Pro: File > Import > the .xml file.
DaVinci Resolve: File > Import > Timeline > the .xml file.

The timeline holds the CUTS (which clip, which part, where) plus the song, and a marker
everywhere an effect was baked into the MP4 (zoom punch, flash, shake, slow-mo), so the
editor can rebuild those effects with the app's own tools. Slow-mo and velocity-ramp
segments are placed at normal speed with a marker: apply the speed change in the app.
"""

import urllib.parse
from pathlib import Path
from xml.sax.saxutils import escape

from common import probe


def _url(path):
    p = Path(path).resolve().as_posix()
    if not p.startswith("/"):
        p = "/" + p  # Windows drive paths: /C:/Users/...
    return "file://localhost" + urllib.parse.quote(p, safe="/:")


def _rate(fps):
    return f"<rate><timebase>{int(round(fps))}</timebase><ntsc>FALSE</ntsc></rate>"


def write_xmeml(plan, out_path):
    fps = int(round(plan["fps"]))
    W, H = plan["width"], plan["height"]
    files = {}

    def file_ref(path, with_audio=True, audio_only=False):
        if path in files:
            return f'<file id="{files[path]}"/>'
        fid = f"file-{len(files) + 1}"
        files[path] = fid
        info = probe(path)
        dur = int(info["duration"] * fps)
        media = ""
        if not audio_only and info["has_video"]:
            media += (
                f"<video><samplecharacteristics><width>{info['width']}</width>"
                f"<height>{info['height']}</height></samplecharacteristics></video>"
            )
        if info["has_audio"] and with_audio:
            media += "<audio><channelcount>2</channelcount></audio>"
        return (
            f'<file id="{fid}"><name>{escape(Path(path).name)}</name>'
            f"<pathurl>{_url(path)}</pathurl>{_rate(fps)}<duration>{dur}</duration>"
            f"<media>{media}</media></file>"
        )

    clips = []
    markers = []
    for i, s in enumerate(plan["segments"], 1):
        start, end = s["tl_start_frame"], s["tl_end_frame"]
        n = end - start
        src_in = int(round(s["src_in"] * fps))
        clips.append(
            f'<clipitem id="clip-{i}"><name>{escape(Path(s["source"]).name)}</name>'
            f"<enabled>TRUE</enabled>{_rate(fps)}<start>{start}</start><end>{end}</end>"
            f"<in>{src_in}</in><out>{src_in + n}</out>{file_ref(s['source'])}</clipitem>"
        )
        labels = {
            "zoom": "zoom punch",
            "rgb": "RGB split",
            "velocity": "velocity ramp (fast>slow)",
            "rewind": "rewind (reverse, fast)",
            "loop-end": "loop: flows into the first shot",
        }
        fx = [labels.get(e, e) for e in s["effects"] if e != "grade"]
        if s["speed"] != 1 and "rewind" not in s["effects"]:
            fx.append(f"{'slowmo' if s['speed'] < 1 else 'speed'} {s['speed']}x")
        if fx:
            markers.append(
                f"<marker><name>{escape(', '.join(fx))}</name><comment></comment><in>{start}</in><out>-1</out></marker>"
            )

    total = plan["segments"][-1]["tl_end_frame"] if plan["segments"] else 0
    song = plan.get("song")
    audio = ""
    if song:
        sin = int(round(plan.get("song_start", 0) * fps))
        audio = (
            f'<track><clipitem id="song-1"><name>{escape(Path(song).name)}</name>'
            f"<enabled>TRUE</enabled>{_rate(fps)}<start>0</start><end>{total}</end>"
            f"<in>{sin}</in><out>{sin + total}</out>{file_ref(song, audio_only=True)}"
            f"<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>"
            f"</clipitem></track>"
        )
    if plan.get("source_audio"):
        # the clips' own sound (talking videos): one audio clip under every video clip
        items = []
        for i, s in enumerate(plan["segments"], 1):
            start, end = s["tl_start_frame"], s["tl_end_frame"]
            src_in = int(round(s["src_in"] * fps))
            items.append(
                f'<clipitem id="aclip-{i}"><name>{escape(Path(s["source"]).name)}</name>'
                f"<enabled>TRUE</enabled>{_rate(fps)}<start>{start}</start><end>{end}</end>"
                f"<in>{src_in}</in><out>{src_in + end - start}</out>{file_ref(s['source'])}"
                f"<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>"
                f"</clipitem>"
            )
        audio += f"<track>{''.join(items)}</track>"

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="5">'
        f'<sequence id="seq-1"><name>{escape(plan.get("name", "montage"))}</name>'
        f"<duration>{total}</duration>{_rate(fps)}"
        f"{''.join(markers)}"
        "<media><video><format><samplecharacteristics>"
        f"{_rate(fps)}<width>{W}</width><height>{H}</height>"
        "<pixelaspectratio>square</pixelaspectratio></samplecharacteristics></format>"
        f"<track>{''.join(clips)}</track></video>"
        f"<audio>{audio}</audio></media></sequence></xmeml>\n"
    )
    Path(out_path).write_text(xml, encoding="utf-8")
    return str(out_path)
