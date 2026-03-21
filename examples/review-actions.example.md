# review-actions.example

## 目标

本文件用于说明：

- `apply_review_action()` 的职责
- `ReviewActionCommand` 输入结构
- 五类动作的行为规范
- 伪代码
- `recompute_summary()` 规则

## 1. apply_review_action() 的职责定义

`apply_review_action()` 应作为 review 层唯一的状态变更入口。

它的职责包括：

- 接收当前 `ProjectManifest`
- 接收一个 `ReviewActionCommand`
- 更新 `final_boundaries`
- 追加一条 `review_actions`
- 重算 `summary`
- 返回新的 manifest

重要约定：

- 不直接修改 `coarse_boundaries`
- 不直接修改 `refined_boundaries`
- 人工动作只作用于 `final_boundaries`

## 2. 输入命令对象：ReviewActionCommand

### JSON 请求样例

```json
{
  "action": "adjust",
  "target_boundary_ids": ["f_0002"],
  "created_by": "reviewer_01",
  "payload": {
    "new_start_frame": 982,
    "new_end_frame": 982,
    "new_recommended_cut_frame": 982,
    "reason": "move cut to first clean reverse-shot frame"
  }
}
```

### 建议结构

- `action`
- `target_boundary_ids`
- `created_by`
- `payload`

## 3. 核心行为约定

- `final_boundaries` 是当前工作集
- `review_actions` 是完整审计日志
- `source_boundary_ids` 表示血缘关系
- `target_boundary_ids` 表示动作发生当时工作集中的边界 ID；对于后续被 `merge` 或 `reject` 移除的边界，它们不一定继续出现在最终快照的 `final_boundaries` 中
- 所有内部逻辑以 `frame` 为主时基

## 4. 每个动作的行为规范

### accept

- 目标：确认边界有效
- 输入：1 个 `target_boundary_id`
- 输出：边界保留在 `final_boundaries` 中，`review_state = accepted`

### reject

- 目标：移除碎切 / 误检
- 输入：1 个 `target_boundary_id`
- 输出：从 `final_boundaries` 中删除该边界

### adjust

- 目标：微调边界位置
- 输入：1 个 `target_boundary_id`
- 要求提供：
  - `new_start_frame`
  - `new_end_frame`
  - `new_recommended_cut_frame`
- 输出：更新同一边界对象，`review_state = adjusted`

### merge

- 目标：将多个边界合并成一个
- 输入：至少 2 个 `target_boundary_ids`
- 输出：移除原边界，新增一个 merged 边界

### insert

- 目标：手动补漏切
- 输入：`target_boundary_ids` 为空
- 要求提供：
  - `start_frame`
  - `end_frame`
  - `recommended_cut_frame`
  - `boundary_type`
- 输出：新增一个 inserted 边界

## 5. JSON 响应样例

响应直接返回新的完整 manifest，或至少返回：

```json
{
  "ok": true,
  "result_boundary_id": "f_0002",
  "summary": {
    "counts": {
      "coarse_boundaries": 5,
      "suspicious_windows": 3,
      "refined_boundaries": 2,
      "final_boundaries": 4,
      "accepted": 1,
      "adjusted": 1,
      "merged": 1,
      "inserted": 1,
      "rejected": 1
    }
  }
}
```

## 6. apply_review_action() 伪代码

```python
def apply_review_action(manifest, command):
    next_manifest = deep_copy(manifest)

    boundary_map = {b.id: b for b in next_manifest.final_boundaries}
    validate_command(command, boundary_map)

    if command.action == "accept":
        b = boundary_map[command.target_boundary_ids[0]]
        b.review_state = "accepted"
        b.detector_evidence.manual_review = {
            "triggered": True,
            "decision": "accept",
            "reason": command.payload.get("reason")
        }
        result_boundary_id = b.id

    elif command.action == "reject":
        target_id = command.target_boundary_ids[0]
        next_manifest.final_boundaries = [
            b for b in next_manifest.final_boundaries if b.id != target_id
        ]
        result_boundary_id = None

    elif command.action == "adjust":
        b = boundary_map[command.target_boundary_ids[0]]
        b.start_frame = command.payload["new_start_frame"]
        b.end_frame = command.payload["new_end_frame"]
        b.recommended_cut_frame = command.payload["new_recommended_cut_frame"]
        b.review_state = "adjusted"
        result_boundary_id = b.id

    elif command.action == "merge":
        targets = [boundary_map[i] for i in command.target_boundary_ids]
        merged = build_merged_boundary(targets, command.payload)
        next_manifest.final_boundaries = remove_targets_and_append_merged(
            next_manifest.final_boundaries,
            command.target_boundary_ids,
            merged,
        )
        result_boundary_id = merged.id

    elif command.action == "insert":
        inserted = build_inserted_boundary(command.payload)
        next_manifest.final_boundaries.append(inserted)
        next_manifest.final_boundaries = sort_boundaries(next_manifest.final_boundaries)
        result_boundary_id = inserted.id

    review_log = build_review_log(command, result_boundary_id)
    next_manifest.review_actions.append(review_log)
    next_manifest.summary = recompute_summary(next_manifest)

    return next_manifest
```

## 7. recompute_summary() 建议规则

建议重算这些统计：

- `coarse_boundaries`
- `suspicious_windows`
- `refined_boundaries`
- `final_boundaries`
- `accepted`
- `adjusted`
- `merged`
- `inserted`
- `rejected`

建议规则：

- `accepted/adjusted/merged/inserted` 从当前 `final_boundaries` 状态统计
- `rejected` 从 `review_actions` 中 `action == reject` 统计

## 8. 为什么这样设计

这样设计的好处是：

- 所有人工行为都有结构化日志
- `final_boundaries` 永远表示当前可导出的工作集
- 可以支持后续 undo/redo、回放、协作审阅和行为分析
