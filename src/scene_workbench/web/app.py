from __future__ import annotations

from pathlib import Path
import webbrowser

from pydantic import ValidationError

from scene_workbench.models import BoundaryCandidate, ReviewActionCommand
from scene_workbench.review.actions import ReviewActionError, apply_review_action
from scene_workbench.review.preview import build_boundary_preview
from scene_workbench.review.store import ManifestStore


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>Scene Workbench Review</title>
    <style>
      body { font-family: sans-serif; margin: 0; background: #f4f1e8; color: #1d1d1d; }
      .layout { display: grid; grid-template-columns: 320px 1fr 340px; min-height: 100vh; }
      .panel { padding: 16px; border-right: 1px solid #d6cfbf; overflow: auto; }
      .panel:last-child { border-right: 0; }
      .boundary { padding: 10px; margin-bottom: 8px; background: #fffaf0; border: 1px solid #d6cfbf; border-radius: 8px; cursor: pointer; }
      .boundary.selected { border-color: #7c5c2b; box-shadow: 0 0 0 1px #7c5c2b inset; }
      .meta { color: #6a6255; font-size: 12px; }
      .field { margin-bottom: 10px; }
      .field-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
      label { display: block; margin-bottom: 4px; font-size: 12px; color: #6a6255; }
      input, select, textarea, button { font: inherit; }
      input, select, textarea { width: 100%; box-sizing: border-box; padding: 8px; border-radius: 8px; border: 1px solid #cdbfa6; background: #fff; }
      textarea { min-height: 72px; resize: vertical; }
      .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
      button { padding: 8px 12px; border-radius: 8px; border: 1px solid #b8ab91; background: #fff; cursor: pointer; }
      .status { min-height: 20px; margin-top: 12px; padding: 10px; border-radius: 8px; background: #fff; border: 1px solid #d6cfbf; }
      .status.ok { color: #1c5a31; border-color: #b6d6c0; background: #f2fff6; }
      .status.error { color: #8a1c1c; border-color: #e2b8b8; background: #fff2f2; }
      .hint { color: #6a6255; font-size: 12px; margin-top: 4px; }
      pre { white-space: pre-wrap; word-break: break-word; background: #fff; padding: 12px; border-radius: 8px; border: 1px solid #d6cfbf; }
    </style>
  </head>
  <body>
    <div class="layout">
      <section class="panel">
        <h2>边界列表</h2>
        <div id="boundary-list"></div>
      </section>
      <section class="panel">
        <h2>预览</h2>
        <div id="preview"></div>
        <div class="field">
          <label for="target-boundary-ids">目标边界 IDs</label>
          <input id="target-boundary-ids" type="text" />
          <div class="hint">`merge` 可填写多个 ID，用逗号分隔；其他动作默认使用当前选中边界。</div>
        </div>
        <div class="field-row">
          <div class="field">
            <label for="start-frame">start</label>
            <input id="start-frame" type="number" />
          </div>
          <div class="field">
            <label for="end-frame">end</label>
            <input id="end-frame" type="number" />
          </div>
          <div class="field">
            <label for="recommended-cut-frame">recommended</label>
            <input id="recommended-cut-frame" type="number" />
          </div>
        </div>
        <div class="field">
          <label for="boundary-type">boundary type</label>
          <select id="boundary-type">
            <option value="hard_cut">hard_cut</option>
            <option value="dissolve">dissolve</option>
            <option value="fade_in">fade_in</option>
            <option value="fade_out">fade_out</option>
            <option value="wipe">wipe</option>
            <option value="unknown">unknown</option>
          </select>
        </div>
        <div class="field">
          <label for="action-reason">备注</label>
          <textarea id="action-reason" placeholder="可选：记录人工判断原因"></textarea>
        </div>
        <div class="actions">
          <button onclick="sendAction('accept')">accept</button>
          <button onclick="sendAction('reject')">reject</button>
          <button onclick="sendAction('adjust')">adjust</button>
          <button onclick="sendAction('merge')">merge</button>
          <button onclick="sendAction('insert')">insert</button>
        </div>
        <div id="status" class="status"></div>
      </section>
      <section class="panel">
        <h2>证据</h2>
        <pre id="evidence"></pre>
      </section>
    </div>
    <script>
      let manifest = null;
      let currentBoundaryId = null;

      function sortedBoundaries() {
        return [...(manifest?.final_boundaries ?? [])].sort((left, right) => {
          const leftRank = left.review_state === 'unreviewed' ? 0 : 1;
          const rightRank = right.review_state === 'unreviewed' ? 0 : 1;
          return leftRank - rightRank
            || left.start_frame - right.start_frame
            || left.end_frame - right.end_frame
            || left.recommended_cut_frame - right.recommended_cut_frame
            || left.id.localeCompare(right.id);
        });
      }

      function setStatus(message, tone = '') {
        const status = document.getElementById('status');
        status.textContent = message ?? '';
        status.className = tone ? `status ${tone}` : 'status';
      }

      function findBoundary(boundaryId) {
        return manifest?.final_boundaries.find((boundary) => boundary.id === boundaryId) ?? null;
      }

      function clearPreview() {
        document.getElementById('preview').innerHTML = '<pre>暂无可预览边界</pre>';
        document.getElementById('evidence').textContent = '[]';
      }

      function populateActionForm(boundary) {
        document.getElementById('target-boundary-ids').value = boundary ? boundary.id : '';
        document.getElementById('start-frame').value = boundary ? boundary.start_frame : '';
        document.getElementById('end-frame').value = boundary ? boundary.end_frame : '';
        document.getElementById('recommended-cut-frame').value = boundary ? boundary.recommended_cut_frame : '';
        document.getElementById('boundary-type').value = boundary ? boundary.boundary_type : 'hard_cut';
        document.getElementById('action-reason').value = '';
      }

      function preferredBoundaryId(explicitBoundaryId = null) {
        const ordered = sortedBoundaries();
        if (!ordered.length) {
          return null;
        }
        if (explicitBoundaryId && ordered.some((boundary) => boundary.id === explicitBoundaryId)) {
          return explicitBoundaryId;
        }
        if (manifest?.next_boundary_id && ordered.some((boundary) => boundary.id === manifest.next_boundary_id)) {
          return manifest.next_boundary_id;
        }
        return ordered.find((boundary) => boundary.review_state === 'unreviewed')?.id ?? ordered[0].id;
      }

      async function loadManifest() {
        const response = await fetch('/api/manifest');
        manifest = await response.json();
        await syncSelection(manifest.next_boundary_id);
      }

      function renderBoundaryList() {
        const container = document.getElementById('boundary-list');
        container.innerHTML = '';
        sortedBoundaries().forEach((boundary) => {
          const div = document.createElement('div');
          div.className = 'boundary';
          if (boundary.id === currentBoundaryId) {
            div.classList.add('selected');
          }
          div.onclick = () => selectBoundary(boundary.id);
          div.innerHTML = `<strong>${boundary.id}</strong><div class="meta">${boundary.boundary_type} | ${boundary.review_state} | ${boundary.start_frame}-${boundary.end_frame} | conf=${boundary.confidence}</div>`;
          container.appendChild(div);
        });
      }

      async function selectBoundary(boundaryId) {
        const boundary = findBoundary(boundaryId);
        if (!boundary) {
          await syncSelection();
          return;
        }
        currentBoundaryId = boundaryId;
        populateActionForm(boundary);
        renderBoundaryList();
        const response = await fetch(`/api/preview/${boundaryId}`);
        if (!response.ok) {
          setStatus(`预览加载失败：${response.status}`, 'error');
          return;
        }
        const preview = await response.json();
        document.getElementById('preview').innerHTML = `<pre>${JSON.stringify(preview.context_frames, null, 2)}</pre>`;
        document.getElementById('evidence').textContent = JSON.stringify(preview.evidence_summary, null, 2);
      }

      async function syncSelection(explicitBoundaryId = null) {
        const nextBoundaryId = preferredBoundaryId(explicitBoundaryId);
        renderBoundaryList();
        if (!nextBoundaryId) {
          currentBoundaryId = null;
          populateActionForm(null);
          clearPreview();
          return;
        }
        await selectBoundary(nextBoundaryId);
      }

      function parseTargetBoundaryIds() {
        return document.getElementById('target-boundary-ids')
          .value
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean);
      }

      function readIntegerField(fieldId, label) {
        const rawValue = document.getElementById(fieldId).value.trim();
        if (!rawValue) {
          throw new Error(`${label} 不能为空`);
        }
        const parsedValue = Number(rawValue);
        if (!Number.isInteger(parsedValue)) {
          throw new Error(`${label} 必须是整数`);
        }
        return parsedValue;
      }

      function buildActionRequest(action) {
        const currentBoundary = findBoundary(currentBoundaryId);
        const reason = document.getElementById('action-reason').value.trim();

        if (action === 'accept' || action === 'reject') {
          if (!currentBoundary) {
            throw new Error('请先选择一个边界');
          }
          return {
            action,
            target_boundary_ids: [currentBoundary.id],
            created_by: 'local_reviewer',
            payload: reason ? { reason } : {},
          };
        }

        if (action === 'adjust') {
          if (!currentBoundary) {
            throw new Error('请先选择一个边界');
          }
          return {
            action,
            target_boundary_ids: [currentBoundary.id],
            created_by: 'local_reviewer',
            payload: {
              new_start_frame: readIntegerField('start-frame', 'new_start_frame'),
              new_end_frame: readIntegerField('end-frame', 'new_end_frame'),
              new_recommended_cut_frame: readIntegerField('recommended-cut-frame', 'new_recommended_cut_frame'),
              ...(reason ? { reason } : {}),
            },
          };
        }

        if (action === 'merge') {
          const targetBoundaryIds = parseTargetBoundaryIds();
          if (targetBoundaryIds.length < 2) {
            throw new Error('merge 至少需要 2 个目标边界 ID');
          }
          return {
            action,
            target_boundary_ids: targetBoundaryIds,
            created_by: 'local_reviewer',
            payload: {
              merged_start_frame: readIntegerField('start-frame', 'merged_start_frame'),
              merged_end_frame: readIntegerField('end-frame', 'merged_end_frame'),
              merged_recommended_cut_frame: readIntegerField('recommended-cut-frame', 'merged_recommended_cut_frame'),
              merged_boundary_type: document.getElementById('boundary-type').value,
              ...(reason ? { reason } : {}),
            },
          };
        }

        if (action === 'insert') {
          return {
            action,
            target_boundary_ids: [],
            created_by: 'local_reviewer',
            payload: {
              start_frame: readIntegerField('start-frame', 'start_frame'),
              end_frame: readIntegerField('end-frame', 'end_frame'),
              recommended_cut_frame: readIntegerField('recommended-cut-frame', 'recommended_cut_frame'),
              boundary_type: document.getElementById('boundary-type').value,
              ...(reason ? { reason } : {}),
            },
          };
        }

        throw new Error(`不支持的动作：${action}`);
      }

      async function sendAction(action) {
        try {
          const requestPayload = buildActionRequest(action);
          const response = await fetch('/api/actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestPayload)
          });
          const responsePayload = await response.json();
          if (!response.ok) {
            const detail = Array.isArray(responsePayload.detail)
              ? responsePayload.detail.map((item) => item.msg ?? JSON.stringify(item)).join('; ')
              : (responsePayload.detail ?? '未知错误');
            setStatus(`${action} 失败：${detail}`, 'error');
            return;
          }
          manifest = responsePayload;
          setStatus(`${action} 已保存`, 'ok');
          await syncSelection(responsePayload.next_boundary_id);
        } catch (error) {
          setStatus(error.message ?? String(error), 'error');
        }
      }

      loadManifest();
    </script>
  </body>
</html>
"""


def _load_fastapi():
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Web review requires optional dependencies. Install with `.[web]`."
        ) from exc
    return FastAPI, HTTPException, HTMLResponse


def _boundary_sort_key(boundary: BoundaryCandidate) -> tuple[int, int, int, int, str]:
    reviewed_rank = 0 if boundary.review_state == "unreviewed" else 1
    return (
        reviewed_rank,
        boundary.start_frame,
        boundary.end_frame,
        boundary.recommended_cut_frame,
        boundary.id,
    )


def _resolve_anchor_frame(
    manifest,
    command: ReviewActionCommand,
) -> int | None:
    if command.action == "insert":
        return command.payload.end_frame or command.payload.start_frame

    targets = [
        boundary
        for boundary in manifest.final_boundaries
        if boundary.id in command.target_boundary_ids
    ]
    if not targets:
        return None
    return max(boundary.end_frame for boundary in targets)


def _next_boundary_id(
    manifest,
    *,
    anchor_frame: int | None = None,
) -> str | None:
    ordered = sorted(manifest.final_boundaries, key=_boundary_sort_key)
    if not ordered:
        return None

    # review 动作完成后优先跳到后续未审核边界，保证人工流转连续。
    unreviewed = [boundary for boundary in ordered if boundary.review_state == "unreviewed"]
    if anchor_frame is not None:
        for boundary in unreviewed:
            if boundary.start_frame >= anchor_frame:
                return boundary.id

    return unreviewed[0].id if unreviewed else ordered[0].id


def _manifest_payload(
    manifest,
    *,
    anchor_frame: int | None = None,
) -> dict:
    payload = manifest.model_dump(mode="json")
    payload["next_boundary_id"] = _next_boundary_id(manifest, anchor_frame=anchor_frame)
    return payload


def create_review_app(manifest_path: str | Path):
    FastAPI, HTTPException, HTMLResponse = _load_fastapi()
    store = ManifestStore(manifest_path)
    app = FastAPI(title="Scene Workbench Review")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return HTML_TEMPLATE

    @app.get("/api/manifest")
    def get_manifest():
        manifest = store.load()
        return _manifest_payload(manifest)

    @app.get("/api/preview/{boundary_id}")
    def get_preview(boundary_id: str):
        manifest = store.load()
        boundary = next(
            (item for item in manifest.final_boundaries if item.id == boundary_id),
            None,
        )
        if boundary is None:
            raise HTTPException(status_code=404, detail="Boundary not found")
        return build_boundary_preview(manifest.video, boundary).model_dump(mode="json")

    @app.post("/api/actions")
    def post_action(command: dict):
        manifest = store.load()
        try:
            review_command = ReviewActionCommand.model_validate(command)
        except ValidationError as exc:
            # 前端命令格式错误时返回 4xx，避免被误判为服务端崩溃。
            raise HTTPException(status_code=422, detail=exc.errors()) from exc

        anchor_frame = _resolve_anchor_frame(manifest, review_command)

        try:
            next_manifest = apply_review_action(manifest, review_command)
        except ReviewActionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        store.save(next_manifest)
        return _manifest_payload(next_manifest, anchor_frame=anchor_frame)

    return app


def launch_review_server(
    manifest_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> str:
    app = create_review_app(manifest_path)
    url = f"http://{host}:{port}"
    if open_browser:
        webbrowser.open(url)

    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Review server requires optional web dependencies. Install with `.[web]`."
        ) from exc

    uvicorn.run(app, host=host, port=port)
    return url
