# scene-workbench

镜头边界确认工作台的 Python 实现。

当前阶段优先交付：

- 项目骨架与 CLI 入口
- manifest / config 数据模型
- 本地视频元信息读取
- PySceneDetect 粗切
- suspicious windows 生成
- review harness 与 `apply_review_action()`
- JSON / cutlist / EDL / FFmpeg 导出
- `inspect` / `baseline` 最小评估快照与报告
- TransNetV2 refinement 真后端接入

推荐安装：

```powershell
python -m pip install ".[dev,web,refine]"
```

环境重建：

```powershell
.\scripts\rebuild-venv.ps1
```

如果只想先预览将执行什么命令，可加 `-WhatIf`：

```powershell
.\scripts\rebuild-venv.ps1 -WhatIf
```

如果你在 `cmd` 下工作，也可以直接运行：

```bat
scripts\rebuild-venv.cmd
```

最小测试命令：

```powershell
python -m scene_workbench analyze input.mp4 --output out\manifest.json
python -m scene_workbench inspect out\manifest.json
python -m scene_workbench review out\manifest.json
python -m scene_workbench export out\manifest.json --format json --output out\export.json
python -m scene_workbench baseline out\manifest.json --output-json out\baseline.json --output-md out\baseline.md
```

Review harness 当前能力：

- `scene-workbench review manifest.json` 启动本地 Web review harness
- 支持 `accept / reject / adjust / merge / insert` 五类动作
- 每次动作后自动保存 manifest，并优先跳到下一个 `unreviewed` 边界
- 默认导出策略为 reviewed-only，即只导出 `accepted / adjusted / merged / inserted`

如果你只想启动服务、不自动打开浏览器：

```powershell
python -m scene_workbench review out\manifest.json --no-open-browser
```

推荐先读一遍工作流说明：

- `WORKFLOW.md`
