"""CLI 入口。"""

from __future__ import annotations

from pathlib import Path
import json

import typer

from scene_workbench import __version__
from scene_workbench.api import analyze_video, save_manifest
from scene_workbench.config import WorkbenchConfig
from scene_workbench.evaluation import (
    build_baseline_report,
    build_evaluation_snapshot,
    export_baseline_report_json,
    export_baseline_report_markdown,
    load_manifests_for_report,
)
from scene_workbench.export import (
    export_cut_list,
    export_edl,
    export_ffmpeg_split,
    export_json,
)
from scene_workbench.review.store import load_manifest


app = typer.Typer(add_completion=False, no_args_is_help=True)


def version_callback(value: bool) -> None:
    """输出版本后退出。"""
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        help="输出当前版本。",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """scene-workbench 命令入口。"""


@app.command("analyze")
def analyze_command(
    video_path: Path = typer.Argument(..., exists=False, help="本地视频文件路径。"),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="输出 manifest.json 路径。",
    ),
    coarse_only: bool = typer.Option(
        False,
        "--coarse-only",
        help="仅运行 coarse 检测，跳过 refinement。",
    ),
) -> None:
    """运行最小分析链路并写出 manifest。"""
    config = WorkbenchConfig()
    if coarse_only:
        config.refinement.enabled = False
    manifest = analyze_video(video_path, config)
    output_path = save_manifest(manifest, output)
    typer.echo(f"manifest 已写出：{output_path}")


@app.command("review")
def review_command(
    manifest_path: Path = typer.Argument(..., exists=True, help="待审阅 manifest 路径。"),
    host: str = typer.Option("127.0.0.1", "--host", help="本地监听地址。"),
    port: int = typer.Option(8765, "--port", help="本地监听端口。"),
    open_browser: bool = typer.Option(True, "--open-browser/--no-open-browser", help="是否自动打开浏览器。"),
) -> None:
    """启动本地 review harness。"""
    from scene_workbench.web.app import launch_review_server

    url = f"http://{host}:{port}"
    typer.echo(f"review harness 启动中：{url}")
    launch_review_server(
        manifest_path,
        host=host,
        port=port,
        open_browser=open_browser,
    )


@app.command("export")
def export_command(
    manifest_path: Path = typer.Argument(..., exists=True, help="manifest 路径。"),
    format: str = typer.Option(..., "--format", help="导出格式：json/cutlist/edl/ffmpeg"),
    output: Path = typer.Option(..., "--output", "-o", help="导出文件路径。"),
    reviewed_only: bool = typer.Option(
        True,
        "--reviewed-only/--all-final-boundaries",
        help="默认只导出人工确认后的工作集。",
    ),
) -> None:
    """导出 final boundaries。"""
    manifest = load_manifest(manifest_path)
    format_name = format.lower()
    exporters = {
        "json": export_json,
        "cutlist": export_cut_list,
        "edl": export_edl,
        "ffmpeg": export_ffmpeg_split,
    }
    exporter = exporters.get(format_name)
    if exporter is None:
        raise typer.BadParameter("format must be one of: json, cutlist, edl, ffmpeg")
    output_path = exporter(manifest, output, reviewed_only=reviewed_only)
    typer.echo(f"导出完成：{output_path}")


@app.command("inspect")
def inspect_command(
    manifest_path: Path = typer.Argument(..., exists=True, help="manifest 路径。"),
) -> None:
    """输出 manifest 摘要和最小评估快照。"""
    manifest = load_manifest(manifest_path)
    snapshot = build_evaluation_snapshot(manifest)
    payload = {
        "manifest_id": manifest.manifest_id,
        "video": manifest.video.model_dump(mode="json"),
        "summary": manifest.summary.model_dump(mode="json") if manifest.summary else None,
        "evaluation": snapshot.model_dump(mode="json"),
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("baseline")
def baseline_command(
    manifest_paths: list[Path] = typer.Argument(..., exists=True, help="参与 baseline 的 manifest 路径列表。"),
    output_json: Path = typer.Option(..., "--output-json", help="baseline JSON 输出路径。"),
    output_md: Path = typer.Option(..., "--output-md", help="baseline Markdown 输出路径。"),
) -> None:
    """聚合多个 manifest，生成最小 baseline 报告。"""
    manifests = load_manifests_for_report(manifest_paths)
    report = build_baseline_report(manifests)
    json_path = export_baseline_report_json(report, output_json)
    md_path = export_baseline_report_markdown(report, output_md)
    typer.echo(f"baseline JSON：{json_path}")
    typer.echo(f"baseline Markdown：{md_path}")


def main() -> None:
    """运行 CLI。"""
    app()


if __name__ == "__main__":
    main()
